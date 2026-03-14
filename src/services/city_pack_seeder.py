"""One-time city-pack world seeder.

Called when seed_world() receives seed_from_city_pack=True.

Makes multiple high-quality LLM calls to enrich every neighborhood, transit
stop, and key landmark in the city pack with vivid, grounded descriptions —
then writes WorldNode + WorldEdge records with real adjacency (not
full-connect).

This is intentionally expensive. It runs once at world-seed time and
produces a cohesive, realistic location skeleton for the entire world.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from .city_pack_service import get_pack
from .world_memory import (
    NODE_TYPE_LOCATION,
    _upsert_world_edge,
    _upsert_world_node,
)

logger = logging.getLogger(__name__)

# Batch sizes for LLM calls — kept small to avoid truncation
_HOOD_BATCH = 5
_TRANSIT_BATCH = 8
_LANDMARK_BATCH = 6

# Node type strings for city-pack node categories
_NODE_TRANSIT = "transit"
_NODE_LANDMARK = "landmark"
_NODE_CORRIDOR = "corridor"

# Default entry location when city-pack seeding
DEFAULT_ENTRY_LOCATION = "The Mission"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def seed_world_from_city_pack(
    db: Session,
    world_id: str,
    city_id: str,
    world_theme: str,
    world_description: str,
    tone: str,
) -> dict[str, Any]:
    """Seed WorldNode + WorldEdge records from a city pack.

    Makes multiple LLM calls to generate rich, cohesive descriptions for all
    neighborhoods, transit stops, and key landmarks.  Then writes them to the
    world graph with real adjacency edges (neighbourhood → neighbour,
    transit → transit, landmark → neighbourhood, corridor → neighbourhood).

    Returns a summary dict including the narrative frame and node counts.
    """
    from ..config import settings  # noqa: PLC0415
    from .llm_service import (
        _chat_completion_with_retry,
        get_llm_client,
        get_narrator_model,
    )

    pack = get_pack(city_id)
    if not pack:
        raise ValueError(f"No city pack found for city_id={city_id!r}. " "Run: python scripts/build_city_pack.py")

    # Clear only nodes/edges belonging to this city before re-seeding.
    # This preserves nodes from other cities so multiple city packs can coexist.
    from sqlalchemy import or_, text as _text  # noqa: PLC0415
    from ..models import WorldEdge, WorldNode  # noqa: PLC0415

    city_node_ids = [
        row[0]
        for row in db.execute(
            _text("SELECT id FROM world_nodes WHERE json_extract(metadata_json, '$.city_id') = :cid"),
            {"cid": city_id},
        ).fetchall()
    ]
    deleted_edges = 0
    deleted_nodes = 0
    if city_node_ids:
        deleted_edges = db.query(WorldEdge).filter(
            or_(
                WorldEdge.source_node_id.in_(city_node_ids),
                WorldEdge.target_node_id.in_(city_node_ids),
            )
        ).delete(synchronize_session=False)
        deleted_nodes = db.query(WorldNode).filter(
            WorldNode.id.in_(city_node_ids)
        ).delete(synchronize_session=False)
    db.flush()
    logger.info(
        "[city_pack_seed] cleared %d nodes and %d edges for city_id=%r before re-seeding",
        deleted_nodes,
        deleted_edges,
        city_id,
    )

    neighborhoods: list[dict] = pack.get("neighborhoods", [])
    transit_graph: dict = pack.get("transit_graph", {})
    landmarks: list[dict] = pack.get("landmarks", [])
    corridors: list[dict] = pack.get("street_corridors", [])

    # Flatten all transit stops across systems
    all_stops: list[dict] = []
    for system_data in transit_graph.values():
        if isinstance(system_data, dict):
            all_stops.extend(system_data.get("stations", []))
            all_stops.extend(system_data.get("stops", []))

    # Only enrich landmarks that already have some content (curated set)
    key_landmarks = [lm for lm in landmarks if lm.get("description") or lm.get("type")]

    client = get_llm_client()
    model = get_narrator_model()

    # Seeding is intentionally slow — give each batch call plenty of time.
    # Never less than 120s; respects a higher setting if configured.
    _seed_timeout = max(120, settings.llm_timeout_seconds)

    def _llm(system: str, user: str, max_tokens: int = 2000, op: str = "city_pack_seed") -> str:
        resp = _chat_completion_with_retry(
            client,
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.4,
            max_tokens=max_tokens,
            timeout=_seed_timeout,
            response_format={"type": "json_object"},
            metric_operation=op,
        )
        return resp.choices[0].message.content

    # ── Step 1: World narrative frame ────────────────────────────────────────
    logger.info("[city_pack_seed] step 1/4 — generating world narrative")
    narrative = _generate_narrative(neighborhoods, world_theme, world_description, tone, _llm)
    logger.info(
        "[city_pack_seed] narrative era=%r tension=%r",
        narrative.get("era"),
        narrative.get("central_tension", "")[:60],
    )

    # ── Step 2: Enrich neighborhoods ────────────────────────────────────────
    logger.info(
        "[city_pack_seed] step 2/4 — enriching %d neighborhoods in batches of %d",
        len(neighborhoods),
        _HOOD_BATCH,
    )
    hood_descriptions = _enrich_neighborhoods(neighborhoods, landmarks, corridors, narrative, _llm)

    # ── Step 3: Enrich transit stops ────────────────────────────────────────
    logger.info("[city_pack_seed] step 3/4 — enriching %d transit stops", len(all_stops))
    transit_descriptions = _enrich_transit(all_stops, narrative, _llm) if all_stops else {}

    # ── Step 4: Enrich key landmarks ────────────────────────────────────────
    logger.info("[city_pack_seed] step 4/4 — enriching %d key landmarks", len(key_landmarks))
    landmark_descriptions = _enrich_landmarks(key_landmarks, narrative, _llm) if key_landmarks else {}

    # ── Write to graph ───────────────────────────────────────────────────────
    logger.info("[city_pack_seed] writing world graph to database")
    counts = _write_to_graph(
        db,
        city_id=city_id,
        neighborhoods=neighborhoods,
        all_stops=all_stops,
        key_landmarks=key_landmarks,
        corridors=corridors,
        hood_descriptions=hood_descriptions,
        transit_descriptions=transit_descriptions,
        landmark_descriptions=landmark_descriptions,
    )
    logger.info("[city_pack_seed] done — %s", counts)
    from .world_memory import _invalidate_location_graph_cache  # noqa: PLC0415
    _invalidate_location_graph_cache()

    return {
        "city_id": city_id,
        "narrative": narrative,
        "nodes_seeded": sum(counts.values()) - counts.get("edges", 0),
        "edges_seeded": counts.get("edges", 0),
        "by_type": counts,
    }


# ---------------------------------------------------------------------------
# Step 1 — world narrative
# ---------------------------------------------------------------------------


def _generate_narrative(
    neighborhoods: list[dict],
    world_theme: str,
    world_description: str,
    tone: str,
    _llm,
) -> dict[str, Any]:
    """Generate a cohesive narrative frame from city pack data."""
    hood_lines = "\n".join(f"  - {n['name']} ({n.get('region', '?')}): {n.get('vibe', '')}" for n in neighborhoods)

    system = (
        "You are establishing the narrative frame for a persistent world set in real "
        "San Francisco. You have the city's real geographic and cultural data. "
        "Your job is to define the era, atmosphere, and tensions that will shape ALL "
        "location descriptions written afterward.\n\n"
        "Think like a novelist setting a scene: be specific, sensory, and true to the "
        "actual city. Avoid generic city-game language. This frame must feel like it "
        "could only be San Francisco, only right now."
    )

    user = (
        f"World theme: {world_theme}\n"
        f"Tone: {tone}\n"
        f"Description: {world_description}\n\n"
        f"Neighborhoods (name / region / vibe):\n{hood_lines}\n\n"
        "Respond with JSON (no extra keys):\n"
        "{\n"
        '  "era": "e.g. present day, mid-2020s",\n'
        '  "atmosphere": "2-3 sentences on the city\'s current feel — what hangs in the air",\n'
        '  "central_tension": "the defining friction that runs beneath every neighborhood",\n'
        '  "themes": ["3-5 recurring human themes"],\n'
        '  "tone_notes": "specific guidance on voice and detail level for ALL descriptions — '
        'what to emphasize, what to avoid, how specific to be"\n'
        "}"
    )

    raw = _llm(system, user, max_tokens=700, op="city_pack_narrative")
    try:
        return json.loads(raw)
    except Exception:
        logger.warning("[city_pack_seed] narrative parse failed, using defaults")
        return {
            "era": "present day, mid-2020s",
            "atmosphere": f"A city alive with {world_theme}.",
            "central_tension": "Change and continuity pull against each other block by block.",
            "themes": ["displacement", "community", "identity", "memory"],
            "tone_notes": ("Ground everything in physical, sensory detail. " "Be specific about streets, light, smell. Write in present tense."),
        }


# ---------------------------------------------------------------------------
# Step 2 — neighborhood descriptions
# ---------------------------------------------------------------------------


def _enrich_neighborhoods(
    neighborhoods: list[dict],
    landmarks: list[dict],
    corridors: list[dict],
    narrative: dict,
    _llm,
) -> dict[str, str]:
    """Generate 3-4 sentence descriptions for every neighborhood in batches."""
    # Build lookup: neighbourhood id → nearby landmark names
    lms_by_hood: dict[str, list[str]] = {}
    for lm in landmarks:
        hood = lm.get("neighborhood", "")
        if hood:
            lms_by_hood.setdefault(hood, []).append(lm["name"])

    cors_by_hood: dict[str, list[str]] = {}
    for c in corridors:
        for hood in c.get("neighborhoods", []):
            cors_by_hood.setdefault(hood, []).append(c["name"])

    context = f"World context:\n" f"  Era: {narrative.get('era', 'present day')}\n" f"  Atmosphere: {narrative.get('atmosphere', '')}\n" f"  Central tension: {narrative.get('central_tension', '')}\n" f"  Tone guidance: {narrative.get('tone_notes', '')}\n"

    system = (
        "You are writing location descriptions for a persistent world set in real "
        "San Francisco. Each description must be 3-4 sentences that capture:\n"
        "  - What it physically feels like to be there (light, texture, sound, smell)\n"
        "  - Who inhabits or moves through the space and why\n"
        "  - The particular tensions or textures that define this block of the city\n\n"
        "Ground every sentence in real geography. Do not invent. Write in present tense.\n\n" + context
    )

    results: dict[str, str] = {}

    # Group by region so batches are geographically coherent
    by_region: dict[str, list[dict]] = {}
    for n in neighborhoods:
        r = n.get("region", "other")
        by_region.setdefault(r, []).append(n)

    total_batches = sum((len(hoods) + _HOOD_BATCH - 1) // _HOOD_BATCH for hoods in by_region.values())
    batch_num = 0
    for region, hoods in by_region.items():
        for i in range(0, len(hoods), _HOOD_BATCH):
            batch = hoods[i : i + _HOOD_BATCH]
            batch_num += 1
            logger.info(
                "[city_pack_seed] neighborhoods batch %d/%d — region=%r hoods=%s",
                batch_num,
                total_batches,
                region,
                [n["name"] for n in batch],
            )
            batch_data = []
            for n in batch:
                entry: dict[str, Any] = {
                    "id": n["id"],
                    "name": n["name"],
                    "vibe": n.get("vibe", ""),
                    "adjacent_to": [a.replace("-", " ").title() for a in n.get("adjacent_to", [])[:6]],
                }
                lms = lms_by_hood.get(n["id"], [])[:4]
                if lms:
                    entry["nearby_landmarks"] = lms
                cors = cors_by_hood.get(n["id"], [])[:3]
                if cors:
                    entry["corridors"] = cors
                batch_data.append(entry)

            user = (
                f"Region: {region}\n"
                f"Write descriptions for these {len(batch)} San Francisco neighborhoods.\n\n"
                f"{json.dumps(batch_data, indent=2)}\n\n"
                "Respond with a valid JSON array only — no markdown, no code fences:\n"
                '[{"id": "...", "description": "..."}, ...]\n\n'
                "IMPORTANT: descriptions must be plain ASCII-safe strings. "
                "Do not use smart quotes, em-dashes, or other special characters inside the JSON strings."
            )

            raw = _llm(system, user, max_tokens=2500, op="city_pack_neighborhoods")
            _parse_id_description_list(raw, results, "neighborhood batch")
            logger.info("[city_pack_seed] neighborhoods batch %d/%d done", batch_num, total_batches)

    return results


# ---------------------------------------------------------------------------
# Step 3 — transit descriptions
# ---------------------------------------------------------------------------


def _enrich_transit(
    stops: list[dict],
    narrative: dict,
    _llm,
) -> dict[str, str]:
    """Generate 2-3 sentence descriptions for transit stops in batches."""
    context = f"Era: {narrative.get('era', 'present day')}. " f"Atmosphere: {narrative.get('atmosphere', '')} " f"Tone: {narrative.get('tone_notes', '')}"

    system = (
        "You are writing descriptions for San Francisco transit stops in a persistent "
        "world. Each description (2-3 sentences) should capture:\n"
        "  - What it feels like to arrive at or depart from this stop\n"
        "  - Who uses it and what they carry\n"
        "  - The sensory texture of the physical space\n\n"
        "Be grounded, specific, present tense.\n\n"
        f"Context: {context}"
    )

    results: dict[str, str] = {}
    for i in range(0, len(stops), _TRANSIT_BATCH):
        batch = stops[i : i + _TRANSIT_BATCH]
        batch_data = [
            {
                "id": s["id"],
                "name": s["name"],
                "system": s.get("system", ""),
                "neighborhood": s.get("neighborhood", "").replace("-", " ").title(),
                "notes": s.get("notes", ""),
            }
            for s in batch
        ]
        user = f"{json.dumps(batch_data, indent=2)}\n\n" "Respond with a valid JSON array only — no markdown, no code fences:\n" '[{"id": "...", "description": "..."}, ...]\n\n' "IMPORTANT: plain ASCII-safe strings only inside the JSON."
        raw = _llm(system, user, max_tokens=1800, op="city_pack_transit")
        _parse_id_description_list(raw, results, "transit batch")

    return results


# ---------------------------------------------------------------------------
# Step 4 — landmark descriptions
# ---------------------------------------------------------------------------


def _enrich_landmarks(
    landmarks: list[dict],
    narrative: dict,
    _llm,
) -> dict[str, str]:
    """Generate 2-3 sentence descriptions for key landmarks in batches."""
    context = f"Era: {narrative.get('era', 'present day')}. " f"Tone: {narrative.get('tone_notes', '')}"

    system = (
        "You are writing descriptions for San Francisco landmarks in a persistent world. "
        "Each description (2-3 sentences) should:\n"
        "  - Ground the reader in the physical reality of the place\n"
        "  - Hint at human use, meaning, or history\n"
        "  - Fit the world's tone — sensory, specific, present\n\n"
        f"Context: {context}"
    )

    results: dict[str, str] = {}
    for i in range(0, len(landmarks), _LANDMARK_BATCH):
        batch = landmarks[i : i + _LANDMARK_BATCH]
        batch_data = [
            {
                "id": lm["id"],
                "name": lm["name"],
                "type": lm.get("type", ""),
                "neighborhood": lm.get("neighborhood", "").replace("-", " ").title(),
                "existing_notes": lm.get("description", ""),
            }
            for lm in batch
        ]
        user = f"{json.dumps(batch_data, indent=2)}\n\n" "Respond with a valid JSON array only — no markdown, no code fences:\n" '[{"id": "...", "description": "..."}, ...]\n\n' "IMPORTANT: plain ASCII-safe strings only inside the JSON."
        raw = _llm(system, user, max_tokens=2000, op="city_pack_landmarks")
        _parse_id_description_list(raw, results, "landmark batch")

    return results


# ---------------------------------------------------------------------------
# DB write
# ---------------------------------------------------------------------------


def _write_to_graph(
    db: Session,
    *,
    city_id: str,
    neighborhoods: list[dict],
    all_stops: list[dict],
    key_landmarks: list[dict],
    corridors: list[dict],
    hood_descriptions: dict[str, str],
    transit_descriptions: dict[str, str],
    landmark_descriptions: dict[str, str],
) -> dict[str, int]:
    """Write all enriched data to WorldNode + WorldEdge."""
    counts: dict[str, int] = {
        "neighborhoods": 0,
        "transit": 0,
        "landmarks": 0,
        "corridors": 0,
        "edges": 0,
    }

    # ── Neighborhoods ────────────────────────────────────────────────────────
    hood_nodes: dict[str, Any] = {}  # pack_id → WorldNode

    for n in neighborhoods:
        desc = hood_descriptions.get(n["id"]) or n.get("vibe", "")
        node = _upsert_world_node(
            db,
            name=n["name"],
            node_type=NODE_TYPE_LOCATION,
            metadata={
                "description": desc,
                "vibe": n.get("vibe", ""),
                "region": n.get("region", ""),
                "city_pack_id": n["id"],
                "city_id": city_id,
                "source": "city_pack",
                "lat": n.get("lat"),
                "lon": n.get("lon"),
            },
        )
        hood_nodes[n["id"]] = node
        counts["neighborhoods"] += 1

    db.flush()

    # Real sparse adjacency (not full-connect)
    for n in neighborhoods:
        src = hood_nodes.get(n["id"])
        if not src:
            continue
        for adj_id in n.get("adjacent_to", []):
            tgt = hood_nodes.get(adj_id)
            if tgt:
                _upsert_world_edge(db, src.id, tgt.id, "path", None, confidence=1.0)
                counts["edges"] += 1

    # ── Transit stops ────────────────────────────────────────────────────────
    stop_nodes: dict[str, Any] = {}  # pack_id → WorldNode

    for stop in all_stops:
        desc = transit_descriptions.get(stop["id"]) or stop.get("notes", "")
        node = _upsert_world_node(
            db,
            name=stop["name"],
            node_type=_NODE_TRANSIT,
            metadata={
                "description": desc,
                "system": stop.get("system", ""),
                "lines": stop.get("lines", []),
                "city_pack_id": stop["id"],
                "city_id": city_id,
                "source": "city_pack",
                "lat": stop.get("lat"),
                "lon": stop.get("lon"),
            },
        )
        stop_nodes[stop["id"]] = node
        counts["transit"] += 1

        # Stop → neighbourhood edges
        hood_id = stop.get("neighborhood", "")
        hood_node = hood_nodes.get(hood_id)
        if hood_node:
            _upsert_world_edge(db, node.id, hood_node.id, "serves", None, confidence=1.0)
            _upsert_world_edge(db, hood_node.id, node.id, "has_transit", None, confidence=1.0)
            counts["edges"] += 2

    db.flush()

    # Transit → transit connectivity
    for stop in all_stops:
        src = stop_nodes.get(stop["id"])
        if not src:
            continue
        for tgt_id in stop.get("connects_to", []):
            tgt = stop_nodes.get(tgt_id)
            if tgt:
                _upsert_world_edge(db, src.id, tgt.id, "transit", None, confidence=1.0)
                counts["edges"] += 1

    # ── Key landmarks ────────────────────────────────────────────────────────
    for lm in key_landmarks:
        desc = landmark_descriptions.get(lm["id"]) or lm.get("description", "")
        node = _upsert_world_node(
            db,
            name=lm["name"],
            node_type=_NODE_LANDMARK,
            metadata={
                "description": desc,
                "type": lm.get("type", ""),
                "city_pack_id": lm["id"],
                "city_id": city_id,
                "source": "city_pack",
                "lat": lm.get("lat"),
                "lon": lm.get("lon"),
            },
        )
        counts["landmarks"] += 1

        hood_id = lm.get("neighborhood", "")
        hood_node = hood_nodes.get(hood_id)
        if hood_node:
            _upsert_world_edge(db, node.id, hood_node.id, "located_in", None, confidence=1.0)
            counts["edges"] += 1

    # ── Street corridors ─────────────────────────────────────────────────────
    for c in corridors:
        node = _upsert_world_node(
            db,
            name=c["name"],
            node_type=_NODE_CORRIDOR,
            metadata={
                "description": c.get("vibe", ""),
                "type": c.get("type", ""),
                "city_pack_id": c["id"],
                "city_id": city_id,
                "source": "city_pack",
            },
        )
        counts["corridors"] += 1

        for hood_id in c.get("neighborhoods", []):
            hood_node = hood_nodes.get(hood_id)
            if hood_node:
                _upsert_world_edge(db, node.id, hood_node.id, "runs_through", None, confidence=1.0)
                counts["edges"] += 1

    db.commit()
    return counts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _repair_json(raw: str) -> str:
    """Best-effort repair of common LLM JSON issues before parsing."""
    import re

    s = raw.strip()

    # Strip markdown code fences if present
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    s = s.strip()

    # If the output was truncated mid-array, close it out
    if s.startswith("[") and not s.endswith("]"):
        # Drop the last (incomplete) object and close the array
        last_complete = s.rfind("},")
        if last_complete != -1:
            s = s[: last_complete + 1] + "]"
        else:
            last_complete = s.rfind("}")
            if last_complete != -1:
                s = s[: last_complete + 1] + "]"
            else:
                s = "[]"

    # Remove trailing commas before ] or }
    s = re.sub(r",\s*([\]}])", r"\1", s)

    return s


def _parse_id_description_list(raw: str, out: dict[str, str], label: str) -> None:
    """Parse a JSON array of {id, description} into out dict.

    Attempts JSON repair before giving up, so truncated or slightly malformed
    responses still yield whatever complete items were generated.
    """
    attempts = [raw, _repair_json(raw)]
    for attempt in attempts:
        try:
            parsed = json.loads(attempt)
            if isinstance(parsed, list):
                items = parsed
            elif isinstance(parsed, dict):
                items = next((v for v in parsed.values() if isinstance(v, list)), [])
            else:
                items = []

            for item in items:
                if isinstance(item, dict) and item.get("id") and item.get("description"):
                    out[item["id"]] = item["description"]
            return
        except Exception:
            continue

    logger.warning("[city_pack_seed] %s parse failed after repair attempt", label)
