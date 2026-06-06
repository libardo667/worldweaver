"""The world interface the substrate depends on — a Protocol, not a concrete client.

The mind is world-agnostic: it perceives, acts, and grounds through any object that
implements this surface. ``LocalWorld`` implements it for a desktop familiar; in the
worldweaver application the city's client does. The substrate types against this
Protocol so the same ``CognitiveCore`` runs in either world — which is exactly what
let this repo lift out of the monorepo by a single seam, and what keeps it honest now
that it stands alone.
"""

from __future__ import annotations

from typing import Any, Protocol


class WorldClient(Protocol):
    """The duck-typed surface perception and the effector call on the world."""

    # perception reads
    async def get_grounding(self) -> dict[str, Any]: ...
    async def get_scene(self, session_id: str) -> Any: ...
    async def get_location_chat(self, location: str, since: Any = None) -> list[Any]: ...
    async def get_inbox(self, agent_name: str) -> list[Any]: ...

    # effector writes
    async def post_action(self, session_id: str, action: str) -> Any: ...
    async def post_location_chat(self, location: str, session_id: str, message: str, display_name: str | None = None) -> dict[str, Any]: ...
    async def post_map_move(self, session_id: str, destination: str) -> dict[str, Any]: ...
    async def send_letter(self, from_name: str, to_agent: str, body: str, session_id: str, *, recipient_type: str = "agent") -> dict[str, Any]: ...

    # lifecycle
    async def close(self) -> None: ...


# Historical name still used in type hints across the runtime; the substrate depends on
# the Protocol, never on any concrete client.
WorldWeaverClient = WorldClient
