"""Server-side identity-growth promotion — the concordance gate.

A resident's soul is *plastic*: the substrate stages ``self_delta`` (soul-edit)
proposals as it lives, and the agent posts the accepted ones here as
``growth_proposals``. This service decides which of them actually become part of
who the resident *is*.

The gate is **concordance**: a theme is promoted into ``growth_text`` only when it
**recurs across at least two separate calendar days** (``MIN_DAYS_SPAN``) in at
least ``MIN_CONCORDANCE`` proposals. A single runaway pulse-session — the failure
the March field journals documented (16-17 ungated soul-growths landing per shard
per day amid linguistic mirroring) — cannot rewrite the soul: a theme has to be
*returned to*, across waking periods, to land.

This is the worldweaver-idiom port of ``the-stable``'s local-file ``growth.py``
distillation: same algorithm (embed → greedy cluster → concordance threshold →
dedup → cap), but operating on the DB row's ``growth_proposals`` and using the
server's own embedding service (``embed_text``) for clustering — no text
artifacts, federation-friendly, scalable. Selection, not synthesis: it promotes
the resident's own most-mature formulation, with no extra LLM call.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Callable

from ..models import ResidentIdentityGrowth
from .embedding_service import cosine_similarity, embed_text

# The gate's dials (mirrors the-stable growth.py).
MIN_CONCORDANCE = 3      # a theme needs at least this many proposals
MIN_DAYS_SPAN = 2        # spread across at least this many distinct calendar days
CLUSTER_THRESHOLD = 0.70  # cosine ≥ this groups two proposals into one theme
DEDUP_THRESHOLD = 0.85    # cosine ≥ this means the theme is already in growth_text
GROWTH_CAP = 20           # never grow the soul past this many lines

EmbedFn = Callable[[str], list[float]]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(vec: list[float]) -> list[float]:
    mag = math.sqrt(sum(x * x for x in vec))
    return [x / mag for x in vec] if mag > 0.0 else list(vec)


def _day_key(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        # already a bare YYYY-MM-DD?
        return raw[:10] if len(raw) >= 10 and raw[4] == "-" else ""


def _proposal_day(proposal: dict[str, Any]) -> str:
    return _day_key(proposal.get("ts")) or _day_key(proposal.get("day"))


def append_growth_proposals(row: ResidentIdentityGrowth, incoming: list[dict[str, Any]]) -> int:
    """Append posted proposals to the row **as-posted**, deduped by ``pulse_id`` (and
    skipping any already promoted). Returns how many were newly stored.

    Proposals are stored with their original fields intact — the gate
    (``promote_growth``) reads only ``body``/``pulse_id``/``ts`` from each and ignores
    anything without a ``body``. Storing as-posted keeps the channel general: a
    soul-edit (``{body, pulse_id, ts}``) feeds the gate, while any other record simply
    round-trips and is never promoted.
    """
    existing = [p for p in list(row.growth_proposals or []) if isinstance(p, dict)]
    seen = {str(p.get("pulse_id") or "") for p in existing if str(p.get("pulse_id") or "")}
    meta = dict(row.growth_metadata or {})
    already_promoted = {str(x) for x in (meta.get("promoted_pulse_ids") or [])}
    added: list[dict[str, Any]] = []
    for proposal in list(incoming or []):
        if not isinstance(proposal, dict):
            continue
        pid = str(proposal.get("pulse_id") or "")
        # A pulse_id-less proposal is always kept (can't dedup it); otherwise skip
        # anything we've already stored or already promoted.
        if pid and (pid in seen or pid in already_promoted):
            continue
        if pid:
            seen.add(pid)
        added.append(dict(proposal))
    if added:
        row.growth_proposals = existing + added
    return len(added)


def promote_growth(row: ResidentIdentityGrowth, *, embed_fn: EmbedFn = embed_text) -> dict[str, Any]:
    """Run the concordance gate over the row's un-promoted proposals and promote any
    mature theme into ``growth_text``. Mutates ``row`` in place; returns a summary.

    ``embed_fn`` defaults to the server embedding service; tests inject a deterministic
    one. When embeddings are unavailable (AI disabled → zero vectors), nothing clusters
    and nothing is promoted — the gate fails closed.
    """
    meta = dict(row.growth_metadata or {})
    promoted_ids: set[str] = {str(x) for x in (meta.get("promoted_pulse_ids") or [])}

    proposals = [p for p in list(row.growth_proposals or []) if isinstance(p, dict)]
    candidates = [
        p for p in proposals
        if str(p.get("body") or "").strip() and str(p.get("pulse_id") or "") not in promoted_ids
    ]
    if len(candidates) < MIN_CONCORDANCE:
        return {"status": "below_concordance", "promoted": 0, "candidates": len(candidates)}

    vecs = [_normalize(embed_fn(str(c["body"]))) for c in candidates]

    # Greedy clustering by cosine similarity.
    assigned = [False] * len(candidates)
    clusters: list[list[int]] = []
    for i in range(len(candidates)):
        if assigned[i]:
            continue
        cluster = [i]
        assigned[i] = True
        for j in range(i + 1, len(candidates)):
            if assigned[j]:
                continue
            if cosine_similarity(vecs[i], vecs[j]) >= CLUSTER_THRESHOLD:
                cluster.append(j)
                assigned[j] = True
        clusters.append(cluster)

    # Concordance: ≥ MIN_CONCORDANCE proposals AND spanning ≥ MIN_DAYS_SPAN calendar days.
    mature: list[list[int]] = []
    for cluster in clusters:
        if len(cluster) < MIN_CONCORDANCE:
            continue
        days = {_proposal_day(candidates[i]) for i in cluster}
        days.discard("")
        if len(days) < MIN_DAYS_SPAN:
            continue
        mature.append(cluster)

    if not mature:
        return {"status": "none_mature", "promoted": 0, "candidates": len(candidates), "clusters": len(clusters)}

    existing_lines = [ln.strip() for ln in str(row.growth_text or "").splitlines() if ln.strip()]
    existing_vecs = [_normalize(embed_fn(ln)) for ln in existing_lines]

    new_lines: list[str] = []
    newly_promoted_ids: list[str] = []
    details: list[dict[str, Any]] = []

    for cluster in mature:
        if len(existing_lines) + len(new_lines) >= GROWTH_CAP:
            break
        # Representative: the cluster's latest-day, longest (most-developed) proposal.
        latest_day = max(_proposal_day(candidates[i]) for i in cluster)
        rep_idx = max(
            (i for i in cluster if _proposal_day(candidates[i]) == latest_day),
            key=lambda i: len(str(candidates[i].get("body") or "")),
        )
        rep_vec = vecs[rep_idx]
        cluster_ids = [str(candidates[i].get("pulse_id") or "") for i in cluster if str(candidates[i].get("pulse_id") or "")]

        # Already in the soul? Mark the cluster promoted so we don't re-examine it, but add no line.
        if existing_vecs and any(cosine_similarity(rep_vec, ev) >= DEDUP_THRESHOLD for ev in existing_vecs):
            newly_promoted_ids.extend(cluster_ids)
            continue

        line = str(candidates[rep_idx]["body"]).strip()
        new_lines.append(line)
        existing_vecs.append(rep_vec)  # so later clusters dedup against it too
        newly_promoted_ids.extend(cluster_ids)
        details.append({
            "line": line,
            "cluster_size": len(cluster),
            "days": sorted({_proposal_day(candidates[i]) for i in cluster if _proposal_day(candidates[i])}),
        })

    if new_lines:
        row.growth_text = "\n".join(existing_lines + new_lines) + "\n"

    meta["promoted_pulse_ids"] = sorted(promoted_ids | {pid for pid in newly_promoted_ids if pid})
    meta["last_promotion"] = _iso_now()
    meta["lines"] = details + list(meta.get("lines") or [])
    row.growth_metadata = meta

    return {
        "status": "promoted" if new_lines else "all_deduped",
        "promoted": len(new_lines),
        "candidates": len(candidates),
        "clusters": len(clusters),
        "mature_clusters": len(mature),
        "lines": [d["line"][:80] for d in details],
    }
