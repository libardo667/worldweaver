"""
ground.py — Real-world grounding loop.

Fires every ~35 minutes (configurable). Fetches current SF time and weather
from the worldweaver backend, then generates a brief naturalistic observation
that the agent "experiences" — glancing at a phone, noticing the fog, feeling
the afternoon heat. The observation lands in working memory as a grounding
impression so every other loop naturally incorporates it without needing to
know anything about the grounding data structure.

Also consumes one item from the agent's research queue per cycle: fetches a
compact result packet from the web, distills it to prose, and writes it to
working memory as type="research" so the next fast loop cycle can react to it.

The LLM never sees raw API fields. It sees: who the agent is, where they are,
and a one-line real-world fact. It produces prose. That's it.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import httpx

from src.identity.loader import ResidentIdentity
from src.inference.client import InferenceClient
from src.loops.base import BaseLoop
from src.memory.research_queue import ResearchQueue
from src.memory.working import WorkingMemory
from src.runtime.ledger import append_runtime_event
from src.runtime.rest import RestState
from src.runtime.signals import StimulusPacketQueue
from src.world.client import WorldWeaverClient

logger = logging.getLogger(__name__)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CITY_PACK_DIR = _REPO_ROOT / "worldweaver_engine" / "data" / "cities"


def _city_id() -> str:
    return str(os.environ.get("CITY_ID") or "").strip() or "san_francisco"


def _load_neighborhood_rows() -> list[dict]:
    path = _CITY_PACK_DIR / _city_id() / "neighborhoods.json"
    if not path.exists():
        return []
    try:
        import json

        rows = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _normalize_place_key(value: str) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _resolve_neighborhood_context(location: str, vitality_rows: dict[str, dict]) -> dict[str, object]:
    normalized_location = str(location or "").strip()
    if not normalized_location:
        return {}

    by_name = {
        _normalize_place_key(str(row.get("name") or "")): row
        for row in _load_neighborhood_rows()
        if str(row.get("name") or "").strip()
    }
    key = _normalize_place_key(normalized_location)
    matched = by_name.get(key)
    if matched is None:
        for candidate_key, row in by_name.items():
            if key and (key in candidate_key or candidate_key in key):
                matched = row
                break

    neighborhood_name = str((matched or {}).get("name") or normalized_location).strip()
    vitality = {}
    if neighborhood_name:
        vitality = vitality_rows.get(neighborhood_name) or {}
    if not vitality and key:
        for candidate_name, row in vitality_rows.items():
            candidate_key = _normalize_place_key(candidate_name)
            if candidate_key and (candidate_key == key or candidate_key in key or key in candidate_key):
                vitality = row
                if not neighborhood_name:
                    neighborhood_name = str(candidate_name).strip()
                break

    context: dict[str, object] = {}
    if neighborhood_name:
        context["name"] = neighborhood_name
    if matched is not None:
        vibe = str(matched.get("vibe") or "").strip()
        region = str(matched.get("region") or "").strip()
        if vibe:
            context["vibe"] = vibe
        if region:
            context["region"] = region
    for field in (
        "vitality_score",
        "current_present",
        "current_agents",
        "current_humans",
        "chat_messages_recent",
        "unique_chat_speakers_recent",
        "recent_event_count",
    ):
        value = vitality.get(field)
        if value is not None:
            context[field] = value
    return context


def _weather_signal(weather_desc: str) -> tuple[str, str, float] | None:
    text = str(weather_desc or "").strip().lower()
    if not text:
        return None
    if any(token in text for token in ("storm", "thunder", "downpour", "hail")):
        return ("bad_weather", "rough weather pressing in", 0.85)
    if any(token in text for token in ("rain", "drizzle", "shower")):
        return ("bad_weather", "rain pressing against the day", 0.72)
    if any(token in text for token in ("fog", "mist")):
        return ("bad_weather", "fog muting the edges of the neighborhood", 0.58)
    if any(token in text for token in ("wind", "gust")):
        return ("bad_weather", "wind making movement feel exposed", 0.55)
    if any(token in text for token in ("heat", "hot", "swelter")):
        return ("bad_weather", "heat making the city feel heavy", 0.62)
    return None


def _derive_ambient_pressure(
    *,
    grounding: dict,
    location: str,
    scene_present_count: int,
    scene_event_count: int,
    neighborhood: dict[str, object],
    news: list[str],
) -> dict[str, object] | None:
    signals: list[dict[str, object]] = []
    raw: dict[str, object] = {}
    context: dict[str, object] = {}

    def add_signal(kind: str, label: str, level: float) -> None:
        normalized = max(0.0, min(float(level), 1.0))
        if normalized < 0.3:
            return
        signals.append({"kind": kind, "label": label, "level": round(normalized, 3)})

    time_of_day = str(grounding.get("time_of_day") or "").strip()
    weather = str(grounding.get("weather_description") or grounding.get("weather") or "").strip()
    headline = str(news[0] if news else "").strip()
    neighborhood_name = str(neighborhood.get("name") or "").strip()
    neighborhood_vibe = str(neighborhood.get("vibe") or "").strip()
    region = str(neighborhood.get("region") or "").strip()

    vitality_score = 0.0
    try:
        vitality_score = float(neighborhood.get("vitality_score") or 0.0)
    except (TypeError, ValueError):
        vitality_score = 0.0
    recent_event_count = 0
    try:
        recent_event_count = int(neighborhood.get("recent_event_count") or scene_event_count or 0)
    except (TypeError, ValueError):
        recent_event_count = scene_event_count
    current_present = 0
    try:
        current_present = int(neighborhood.get("current_present") or scene_present_count or 0)
    except (TypeError, ValueError):
        current_present = scene_present_count
    current_present = max(current_present, scene_present_count)

    raw["scene_present_count"] = scene_present_count
    raw["scene_event_count"] = scene_event_count
    raw["current_present"] = current_present
    raw["recent_event_count"] = recent_event_count
    raw["vitality_score"] = round(vitality_score, 3)

    if time_of_day:
        context["time_of_day"] = time_of_day
    if weather:
        context["weather"] = weather
    if headline:
        context["headline"] = headline
    if location:
        context["location"] = location
    if neighborhood_name:
        context["neighborhood"] = neighborhood_name
    if neighborhood_vibe:
        context["neighborhood_vibe"] = neighborhood_vibe[:240]
    if region:
        context["region"] = region

    weather_signal = _weather_signal(weather)
    if weather_signal is not None:
        add_signal(*weather_signal)

    if current_present >= 5 or vitality_score >= 4.5:
        add_signal("crowding", "the neighborhood feels unusually busy", max(0.45, min(1.0, 0.35 + (0.08 * current_present) + (0.06 * vitality_score))))
    elif current_present <= 1 and recent_event_count <= 1 and vitality_score <= 1.2:
        add_signal("quiet", "the neighborhood feels unusually quiet", 0.72)

    if recent_event_count >= 5 or vitality_score >= 3.2:
        add_signal("event_pull", "there is a live current running through nearby streets", max(0.45, min(0.9, 0.25 + (0.09 * recent_event_count) + (0.05 * vitality_score))))

    if not signals and not context and not raw:
        return None
    return {"source": "ambient", "signals": signals, "raw": raw, "context": context}


class GroundLoop(BaseLoop):
    """
    Ambient awareness loop. Injects real SF time and weather into working
    memory as naturalistic prose impressions.

    The agent doesn't receive a structured payload — it experiences a moment:
    "Rosa glances at her phone. 9:47 AM, Thursday. The fog is sitting heavy
    on Valencia this morning."

    If the agent has pending research queries, one is consumed per cycle:
    fetched from the web, distilled, and written to working memory.
    """

    def __init__(
        self,
        identity: ResidentIdentity,
        resident_dir: Path,
        ww_client: WorldWeaverClient,
        llm: InferenceClient,
        session_id: str,
        working_memory: WorkingMemory,
        research_queue: ResearchQueue | None = None,
        rest_state: RestState | None = None,
        packet_queue: StimulusPacketQueue | None = None,
    ):
        super().__init__(identity.name, resident_dir)
        self._identity = identity
        self._ww = ww_client
        self._llm = llm
        self._session_id = session_id
        self._working = working_memory
        self._tuning = identity.tuning
        self._research_queue = research_queue
        self._rest = rest_state
        self._packets = packet_queue

    # ------------------------------------------------------------------
    # Trigger: real-time interval (~35 minutes with ±15% jitter)
    # ------------------------------------------------------------------

    async def _wait_for_trigger(self) -> None:
        if self._rest and await self._rest.sleep_while_resting(max_seconds=300.0):
            return
        minutes = self._tuning.ground_minutes
        jitter = random.uniform(-minutes * 0.15, minutes * 0.15)
        await asyncio.sleep((minutes + jitter) * 60)

    # ------------------------------------------------------------------
    # Context: grounding data + current location
    # ------------------------------------------------------------------

    async def _gather_context(self) -> dict:
        grounding: dict = {}
        location = "somewhere in the city"
        news: list[str] = []
        scene = None
        vitality: dict[str, dict] = {}

        try:
            grounding = await self._ww.get_grounding()
        except Exception as e:
            logger.warning("[%s:ground] grounding fetch failed: %s", self.name, e)

        try:
            scene = await self._ww.get_scene(self._session_id)
            location = scene.location
        except Exception as e:
            logger.warning("[%s:ground] scene fetch failed: %s", self.name, e)

        try:
            news = await self._ww.get_news()
        except Exception as e:
            logger.debug("[%s:ground] news fetch failed: %s", self.name, e)

        try:
            vitality = await self._ww.get_neighborhood_vitality(hours=6)
        except Exception as e:
            logger.debug("[%s:ground] neighborhood vitality fetch failed: %s", self.name, e)

        neighborhood = _resolve_neighborhood_context(location, vitality)
        scene_present_count = len(getattr(scene, "present", []) or []) + (1 if location else 0)
        scene_event_count = len(getattr(scene, "recent_events_here", []) or [])
        ambient_pressure = _derive_ambient_pressure(
            grounding=grounding,
            location=location,
            scene_present_count=scene_present_count,
            scene_event_count=scene_event_count,
            neighborhood=neighborhood,
            news=news,
        )

        return {
            "grounding": grounding,
            "location": location,
            "news": news,
            "scene": scene,
            "neighborhood": neighborhood,
            "ambient_pressure": ambient_pressure,
        }

    async def _should_act(self, context: dict) -> bool:
        if self._rest and await self._rest.is_resting():
            return False
        return bool(context.get("grounding"))

    # ------------------------------------------------------------------
    # Generate grounding moment + consume one research item if queued
    # ------------------------------------------------------------------

    async def _decide_and_execute(self, context: dict) -> None:
        grounding = context["grounding"]
        location = context["location"]
        news = context.get("news", [])
        neighborhood = context.get("neighborhood") if isinstance(context.get("neighborhood"), dict) else {}
        ambient_pressure = context.get("ambient_pressure") if isinstance(context.get("ambient_pressure"), dict) else None
        name = self._identity.name

        datetime_str = grounding.get("datetime_str", "")
        weather_desc = grounding.get("weather_description") or grounding.get(
            "weather", ""
        )
        neighborhood_name = str(neighborhood.get("name") or "").strip()
        neighborhood_vibe = str(neighborhood.get("vibe") or "").strip()
        current_present = int((ambient_pressure or {}).get("raw", {}).get("current_present") or 0)
        recent_event_count = int((ambient_pressure or {}).get("raw", {}).get("recent_event_count") or 0)
        ambient_presence = [
            item for item in list(getattr(context.get("scene"), "ambient_presence", []) or [])
            if getattr(item, "label", "")
        ]

        world_line = datetime_str
        if weather_desc:
            world_line += f". Weather: {weather_desc}"
        if neighborhood_name:
            world_line += f". Neighborhood: {neighborhood_name}"

        # Include at most one headline — enough to make the world feel alive
        # without overwhelming a sensory grounding moment.
        news_line = ""
        if news:
            news_line = f"\n\nIn the news today: {news[0]}."
        ambient_line = ""
        if neighborhood_vibe:
            ambient_line += f"\n\nThis part of the city feels like: {neighborhood_vibe[:220]}."
        if current_present or recent_event_count:
            ambient_line += (
                f"\n\nAround you right now: about {current_present} people present here, "
                f"with {recent_event_count} recent happenings nearby."
            )
        if ambient_presence:
            labels = "; ".join(str(item.label).strip() for item in ambient_presence[:3] if str(item.label).strip())
            if labels:
                ambient_line += f"\n\nAt the edges of the scene: {labels}."

        user_prompt = (
            f"You are {name}, currently at {location}.\n\n"
            f"Right now in San Francisco: {world_line}.{news_line}{ambient_line}\n\n"
            f"In one or two sentences, describe what {name} briefly notices about "
            f"the world at this moment — a glance at a phone, a look out the window, "
            f"a feeling in the air, the quality of light. "
            f"Be specific and sensory. No drama. Just what's there."
        )

        try:
            response = await self._llm.complete(
                system_prompt=self._identity.soul_with_context,
                user_prompt=user_prompt,
                model=self._tuning.fast_model,
                temperature=self._tuning.ground_temperature,
                max_tokens=80,
            )
        except Exception as e:
            logger.warning("[%s:ground] LLM call failed: %s", self.name, e)
            return

        observation = response.strip()
        if not observation:
            return

        logger.info("[%s:ground] %s", self.name, observation[:100])

        self._working.append(
            {
                "type": "grounding",
                "text": observation,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )
        if self._packets:
            dedupe_key = "|".join(
                [
                    str(grounding.get("datetime_str") or "").strip(),
                    str(grounding.get("weather_description") or grounding.get("weather") or "").strip(),
                    str(news[0] if news else "").strip(),
                ]
            )
            self._packets.emit_once(
                packet_type="grounding_update",
                source_loop="ground",
                dedupe_key=dedupe_key or observation[:80],
                location=location,
                salience=0.45,
                payload={
                    "observation": observation,
                    "datetime_str": grounding.get("datetime_str"),
                    "weather": grounding.get("weather_description") or grounding.get("weather"),
                    "headline": news[0] if news else "",
                },
            )
        append_runtime_event(
            self.resident_dir / "memory",
            event_type="grounding_observed",
            payload={
                "observation": observation,
                "location": location,
                "time_of_day": grounding.get("time_of_day"),
                "weather": grounding.get("weather_description") or grounding.get("weather"),
                "headline": news[0] if news else "",
                "neighborhood": neighborhood_name,
                "neighborhood_vibe": neighborhood_vibe[:240] if neighborhood_vibe else "",
            },
        )
        if ambient_pressure is not None:
            append_runtime_event(
                self.resident_dir / "memory",
                event_type="ambient_pressure_observed",
                payload=ambient_pressure,
            )

        # Consume one research item if the queue has anything pending
        if self._research_queue and len(self._research_queue) > 0:
            item = self._research_queue.pop_next()
            if item:
                await self._fetch_research(item)

    # ------------------------------------------------------------------
    # Research: pop one queued item, fetch, distil, write to working mem
    # ------------------------------------------------------------------

    async def _fetch_research(self, item: dict) -> None:
        """Fetch a web result for the queued query and write it to working memory."""
        query = item["query"]
        logger.info("[%s:ground] researching: %s", self.name, query)

        raw_text = await self._search_web(query)
        if not raw_text:
            logger.debug("[%s:ground] research: no result for %r", self.name, query)
            return

        try:
            distilled = await self._llm.complete(
                system_prompt=self._identity.soul_with_context,
                user_prompt=(
                    f"You just looked something up: {query}\n\n"
                    f"What you found:\n{raw_text[:1200]}\n\n"
                    f"In 1-3 sentences, note what's relevant or interesting to you as {self._identity.name}. "
                    f"Be specific. No editorializing."
                ),
                model=self._tuning.fast_model,
                temperature=0.4,
                max_tokens=100,
            )
        except Exception as e:
            logger.warning("[%s:ground] research distillation failed: %s", self.name, e)
            return

        distilled = distilled.strip()
        if distilled:
            self._working.append({
                "type": "research",
                "query": query,
                "result": distilled,
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            if self._packets:
                self._packets.emit_once(
                    packet_type="research_result",
                    source_loop="ground",
                    dedupe_key=f"{query}|{distilled[:80]}",
                    salience=0.4,
                    payload={"query": query, "result": distilled},
                )
            logger.info("[%s:ground] research: %s", self.name, distilled[:120])
            append_runtime_event(
                self.resident_dir / "memory",
                event_type="research_result_observed",
                payload={"query": query, "result": distilled[:200]},
            )

    async def _search_web(self, query: str) -> str:
        """
        Fetch a compact text result for query via DuckDuckGo Instant Answers.
        Falls back to top RelatedTopics snippets if AbstractText is empty.
        Returns empty string if nothing useful is found.
        """
        url = (
            "https://api.duckduckgo.com/?"
            + urllib.parse.urlencode({
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1",
                "t": "worldweaver",
            })
        )
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, follow_redirects=True)
                data = resp.json()

            text = data.get("AbstractText") or ""
            if not text:
                topics = data.get("RelatedTopics", [])
                snippets = [
                    t["Text"] for t in topics[:4]
                    if isinstance(t, dict) and t.get("Text")
                ]
                text = " ".join(snippets)
            return text.strip()
        except Exception as e:
            logger.debug("[%s:ground] web search failed for %r: %s", self.name, query, e)
            return ""

    async def _cooldown(self) -> None:
        pass  # interval handled entirely in _wait_for_trigger
