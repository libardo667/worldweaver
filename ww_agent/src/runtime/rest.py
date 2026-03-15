from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from src.identity.loader import LoopTuning
from src.world.client import WorldWeaverClient

logger = logging.getLogger(__name__)

_REST_WORDS = re.compile(
    r"\b(rest|resting|sleep|sleeping|quiet|stillness|pause|break|breathe|"
    r"step away|stepped away|needed air|need air|solitude|alone|withdraw|"
    r"withdrawing|exhausted|tired|fatigue|go quiet|lie down|offstage)\b",
    re.IGNORECASE,
)
_SLEEP_WORDS = re.compile(
    r"\b(sleep|sleeping|asleep|bed|night|overnight|lie down|crash)\b",
    re.IGNORECASE,
)


def _parse_dt(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass
class RestSnapshot:
    state: str = "active"
    until: datetime | None = None
    started_at: datetime | None = None
    location: str = ""
    reason: str = ""


class RestState:
    def __init__(
        self,
        ww_client: WorldWeaverClient,
        session_id: str,
        tuning: LoopTuning,
    ):
        self._ww = ww_client
        self._session_id = session_id
        self._tuning = tuning
        self._snapshot = RestSnapshot()
        self._lock = asyncio.Lock()
        self._last_sync_mono = 0.0

    async def sync(self, force: bool = False) -> RestSnapshot:
        if not force and (time.monotonic() - self._last_sync_mono) < self._tuning.rest_sync_seconds:
            return self._snapshot
        try:
            payload = await self._ww.get_session_vars(self._session_id)
        except Exception as exc:
            logger.debug("[%s:rest] sync failed: %s", self._session_id, exc)
            return self._snapshot

        vars_ = payload.get("vars", {})
        async with self._lock:
            self._snapshot.state = str(vars_.get("_rest_state") or "active").strip() or "active"
            self._snapshot.until = _parse_dt(vars_.get("_rest_until"))
            self._snapshot.started_at = _parse_dt(vars_.get("_rest_started_at"))
            self._snapshot.location = str(vars_.get("_rest_location") or "").strip()
            self._snapshot.reason = str(vars_.get("_rest_reason") or "").strip()
            self._last_sync_mono = time.monotonic()
            return self._snapshot

    async def is_resting(self) -> bool:
        await self._maybe_wake()
        async with self._lock:
            return self._snapshot.state == "resting" and self._snapshot.until is not None

    async def sleep_while_resting(self, max_seconds: float) -> bool:
        await self._maybe_wake()
        async with self._lock:
            if self._snapshot.state != "resting" or self._snapshot.until is None:
                return False
            remaining = max(5.0, (self._snapshot.until - datetime.now(timezone.utc)).total_seconds())
        await asyncio.sleep(min(max_seconds, remaining))
        return True

    async def maybe_trigger_from_reflection(
        self,
        reflection: str,
        subconscious_reading: str,
        location: str,
    ) -> bool:
        if not self._tuning.rest_enabled:
            return False
        if await self.is_resting():
            return False
        text = f"{reflection}\n{subconscious_reading}".strip()
        if not _REST_WORDS.search(text):
            return False
        duration_seconds = self._rest_duration_seconds(text)
        reason = self._rest_reason(text)
        await self.begin_rest(reason=reason, location=location, duration_seconds=duration_seconds)
        return True

    async def begin_rest(self, reason: str, location: str, duration_seconds: float) -> None:
        now = datetime.now(timezone.utc)
        until = now + timedelta(seconds=max(300.0, duration_seconds))
        updates = {
            "_rest_state": "resting",
            "_rest_until": until.isoformat(),
            "_rest_started_at": now.isoformat(),
            "_rest_location": location,
            "_rest_reason": reason,
            "_dormant_state": "dormant",
        }
        await self._ww.update_session_vars(self._session_id, updates)
        async with self._lock:
            self._snapshot = RestSnapshot(
                state="resting",
                until=until,
                started_at=now,
                location=location,
                reason=reason,
            )
            self._last_sync_mono = time.monotonic()
        logger.info(
            "[%s:rest] resting for %.0f minutes at %s (%s)",
            self._session_id,
            duration_seconds / 60.0,
            location or "unknown",
            reason,
        )

    async def set_active(self, reason: str = "") -> None:
        updates = {
            "_rest_state": "active",
            "_rest_until": None,
            "_dormant_state": "active",
            "_rest_reason": reason,
        }
        await self._ww.update_session_vars(self._session_id, updates)
        async with self._lock:
            self._snapshot = RestSnapshot(state="active", reason=reason)
            self._last_sync_mono = time.monotonic()
        logger.info("[%s:rest] returned to active state", self._session_id)

    async def _maybe_wake(self) -> None:
        await self.sync()
        async with self._lock:
            until = self._snapshot.until
            state = self._snapshot.state
        if state == "resting" and until is not None and until <= datetime.now(timezone.utc):
            await self.set_active(reason="rest complete")

    def _rest_duration_seconds(self, text: str) -> float:
        if _SLEEP_WORDS.search(text):
            return self._tuning.rest_sleep_hours * 3600.0
        local_hour = datetime.now().hour
        if local_hour >= 22 or local_hour < 6:
            return self._tuning.rest_sleep_hours * 3600.0
        return self._tuning.rest_break_minutes * 60.0

    def _rest_reason(self, text: str) -> str:
        for line in text.splitlines():
            cleaned = line.strip()
            if cleaned and _REST_WORDS.search(cleaned):
                return cleaned[:180]
        return "needed quiet"
