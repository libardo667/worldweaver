from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.identity.loader import LoopTuning
from src.world.client import WorldWeaverClient

logger = logging.getLogger(__name__)
_REPO_ROOT = Path(__file__).resolve().parents[3]

_REST_WORDS = re.compile(
    r"\b(rest|resting|sleep|sleeping|stillness|pause|break|breathe|"
    r"step away|stepped away|needed air|need air|solitude|alone|withdraw|"
    r"withdrawing|exhausted|tired|fatigue|go quiet|lie down|offstage)\b",
    re.IGNORECASE,
)
_SLEEP_WORDS = re.compile(
    r"\b(sleep|sleeping|asleep|bed|overnight|lie down|crash)\b",
    re.IGNORECASE,
)


def _city_timezone_name(city_id: str) -> str | None:
    city = str(city_id or "").strip()
    if not city:
        return None
    config_path = _REPO_ROOT / "worldweaver_engine" / "data" / "cities" / city / "weather_config.json"
    if not config_path.exists():
        return None
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.debug("Failed reading city weather config for timezone: %s", config_path)
        return None
    timezone_name = str(payload.get("timezone") or "").strip()
    return timezone_name or None


def _resolve_rest_timezone() -> ZoneInfo:
    timezone_name = (
        str(os.environ.get("WW_CITY_TIMEZONE") or "").strip()
        or _city_timezone_name(str(os.environ.get("CITY_ID") or "").strip())
        or "UTC"
    )
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown rest timezone %r; falling back to UTC", timezone_name)
        return ZoneInfo("UTC")


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
    pending_since: datetime | None = None
    pending_reason: str = ""
    pending_location: str = ""
    pending_hits: int = 0
    last_completed_at: datetime | None = None


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
        self._rest_timezone = _resolve_rest_timezone()
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
            self._snapshot.pending_since = _parse_dt(vars_.get("_rest_pending_since"))
            self._snapshot.pending_reason = str(vars_.get("_rest_pending_reason") or "").strip()
            self._snapshot.pending_location = str(vars_.get("_rest_pending_location") or "").strip()
            self._snapshot.pending_hits = int(vars_.get("_rest_pending_hits") or 0)
            self._snapshot.last_completed_at = _parse_dt(vars_.get("_rest_last_completed_at"))
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
            await self._clear_pending_rest()
            return False
        await self.sync()
        duration_seconds = self._rest_duration_seconds(text)
        reason = self._rest_reason(text)
        now = datetime.now(timezone.utc)
        async with self._lock:
            last_completed_at = self._snapshot.last_completed_at
            pending_since = self._snapshot.pending_since
            pending_hits = self._snapshot.pending_hits

        if self._in_wake_grace(now, last_completed_at):
            await self._clear_pending_rest()
            logger.info("[%s:rest] rest impulse ignored during wake grace (%s)", self._session_id, reason)
            return False

        if self._is_pending_confirmation_valid(now, pending_since):
            next_hits = pending_hits + 1
        else:
            next_hits = 1

        if next_hits < max(1, int(self._tuning.rest_confirmations_required)):
            await self._stage_pending_rest(reason=reason, location=location, started_at=now, hits=next_hits)
            logger.info(
                "[%s:rest] staged rest confirmation %d/%d (%s)",
                self._session_id,
                next_hits,
                max(1, int(self._tuning.rest_confirmations_required)),
                reason,
            )
            return False

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
            "_rest_pending_since": None,
            "_rest_pending_reason": None,
            "_rest_pending_location": None,
            "_rest_pending_hits": None,
        }
        await self._ww.update_session_vars(self._session_id, updates)
        async with self._lock:
            self._snapshot = RestSnapshot(
                state="resting",
                until=until,
                started_at=now,
                location=location,
                reason=reason,
                last_completed_at=self._snapshot.last_completed_at,
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
        now = datetime.now(timezone.utc)
        async with self._lock:
            was_resting = self._snapshot.state == "resting"
            last_completed_at = now if was_resting else self._snapshot.last_completed_at
        updates = {
            "_rest_state": "active",
            "_rest_until": None,
            "_dormant_state": "active",
            "_rest_reason": reason,
            "_rest_pending_since": None,
            "_rest_pending_reason": None,
            "_rest_pending_location": None,
            "_rest_pending_hits": None,
            "_rest_last_completed_at": last_completed_at.isoformat() if last_completed_at else None,
        }
        await self._ww.update_session_vars(self._session_id, updates)
        async with self._lock:
            self._snapshot = RestSnapshot(
                state="active",
                reason=reason,
                last_completed_at=last_completed_at,
            )
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
        local_hour = datetime.now(self._rest_timezone).hour
        if local_hour >= 22 or local_hour < 6:
            return self._tuning.rest_sleep_hours * 3600.0
        return self._tuning.rest_break_minutes * 60.0

    def _rest_reason(self, text: str) -> str:
        for line in text.splitlines():
            cleaned = line.strip()
            if cleaned and _REST_WORDS.search(cleaned):
                return cleaned[:180]
        return "needed quiet"

    def _is_pending_confirmation_valid(
        self,
        now: datetime,
        pending_since: datetime | None,
    ) -> bool:
        if pending_since is None:
            return False
        elapsed = (now - pending_since).total_seconds()
        return elapsed <= (self._tuning.rest_confirmation_window_minutes * 60.0)

    def _in_wake_grace(
        self,
        now: datetime,
        last_completed_at: datetime | None,
    ) -> bool:
        if last_completed_at is None:
            return False
        elapsed = (now - last_completed_at).total_seconds()
        return elapsed < (self._tuning.rest_wake_grace_minutes * 60.0)

    async def _stage_pending_rest(
        self,
        *,
        reason: str,
        location: str,
        started_at: datetime,
        hits: int,
    ) -> None:
        updates = {
            "_rest_pending_since": started_at.isoformat(),
            "_rest_pending_reason": reason,
            "_rest_pending_location": location,
            "_rest_pending_hits": hits,
        }
        await self._ww.update_session_vars(self._session_id, updates)
        async with self._lock:
            self._snapshot.pending_since = started_at
            self._snapshot.pending_reason = reason
            self._snapshot.pending_location = location
            self._snapshot.pending_hits = hits
            self._last_sync_mono = time.monotonic()

    async def _clear_pending_rest(self) -> None:
        async with self._lock:
            has_pending = (
                self._snapshot.pending_since is not None
                or self._snapshot.pending_hits > 0
                or bool(self._snapshot.pending_reason)
            )
        if not has_pending:
            return
        updates = {
            "_rest_pending_since": None,
            "_rest_pending_reason": None,
            "_rest_pending_location": None,
            "_rest_pending_hits": None,
        }
        await self._ww.update_session_vars(self._session_id, updates)
        async with self._lock:
            self._snapshot.pending_since = None
            self._snapshot.pending_reason = ""
            self._snapshot.pending_location = ""
            self._snapshot.pending_hits = 0
            self._last_sync_mono = time.monotonic()
