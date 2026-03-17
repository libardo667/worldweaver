from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from src.runtime.ledger import build_runtime_mirror_payload, load_runtime_events, reduce_runtime_events
from src.world.client import WorldWeaverClient

logger = logging.getLogger(__name__)


class ResidentRuntimeMirror:
    """Best-effort shard-backed mirror of resident reduced state."""

    def __init__(
        self,
        *,
        resident_dir: Path,
        ww_client: WorldWeaverClient,
        session_id: str,
        interval_seconds: float = 60.0,
    ) -> None:
        self._resident_dir = resident_dir
        self._ww = ww_client
        self._session_id = session_id
        self._interval_seconds = max(15.0, float(interval_seconds))

    async def run(self) -> None:
        while True:
            await self.sync_once()
            await asyncio.sleep(self._interval_seconds)

    async def sync_once(self) -> None:
        memory_dir = self._resident_dir / "memory"
        try:
            reduced = reduce_runtime_events(load_runtime_events(memory_dir))
            payload = build_runtime_mirror_payload(reduced)
            await self._ww.update_session_vars(self._session_id, payload)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug("[%s:mirror] runtime sync failed: %s", self._resident_dir.name, exc)
