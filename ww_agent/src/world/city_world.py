"""CityWorld — a per-resident world body that gives a city resident its tools.

The city analog of ``the-stable``'s ``LocalWorld``: it wraps the shared
``WorldWeaverClient`` (one connection pool, all residents) and layers a *per-resident*
tool scope on top, so each resident can carry its own vocations. It implements the same
``WorldClient`` Protocol the substrate depends on, so ``CognitiveCore`` runs against it
unchanged — it just delegates the transport to the shared client.

Two methods do the work, mirroring ``LocalWorld`` exactly:
- ``get_scene`` injects a synthetic recent-event advertising the resident's tools, so the
  pulse prompt tells it "you can USE a tool: …".
- ``post_action`` intercepts a ``use <tool> <input>`` act, runs the tool locally, and
  returns its result as the narrative — without touching the server. Anything else is a
  real world action and is delegated to the client's ``post_action`` as before.

Everything else falls through to the shared client via ``__getattr__``; ``close`` is a
no-op here because the transport is shared and the runner owns its lifecycle.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from src.world.city_tools import CityToolScope
from src.world.client import RecentEvent, SceneData, TurnResult, WorldWeaverClient

# "use <tool> <input>" — the resident's act body for reaching a tool (matches LocalWorld).
_TOOL_RX = re.compile(r"^\s*use\s+([a-z][a-z0-9_]*)\b\s*(.*)$", re.IGNORECASE | re.DOTALL)


class CityWorld:
    """Wraps the shared client with one resident's tool scope; implements WorldClient."""

    def __init__(self, client: WorldWeaverClient, tool_scope: CityToolScope | None):
        self._client = client
        self._tool_scope = tool_scope

    async def get_scene(self, session_id: str) -> SceneData:
        scene = await self._client.get_scene(session_id)
        if self._tool_scope:
            listing = "; ".join(t.description for t in self._tool_scope.list())
            if listing:
                scene.recent_events_here = list(scene.recent_events_here or []) + [
                    RecentEvent(
                        who="your-reach",
                        summary=f"You can USE a tool: {listing}.",
                        ts=datetime.now(timezone.utc).isoformat(),
                    )
                ]
        return scene

    async def post_action(self, session_id: str, action: str) -> TurnResult:
        match = _TOOL_RX.match(str(action or ""))
        if match is not None and self._tool_scope:
            name = match.group(1).strip().lower()
            arg = match.group(2).strip()
            if name in self._tool_scope.names:
                res = await self._tool_scope.call(name, arg)
                return TurnResult(
                    narrative=str(res.get("result") or ""),
                    choices=[],
                    vars={},
                    public_summary="",
                    plausible=bool(res.get("ok", True)),
                )
        # not a known tool use — a real action in the world
        return await self._client.post_action(session_id, action)

    async def close(self) -> None:
        # The transport is shared across residents; the runner owns closing it.
        return None

    def __getattr__(self, name: str) -> Any:
        # Everything not overridden above (perception reads, the other effector writes,
        # roster/dm helpers, optional substrate attrs like muted_self_senses) delegates
        # to the shared client. Missing attrs raise AttributeError as usual, which the
        # substrate's getattr(..., default) calls handle.
        return getattr(self._client, name)
