# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

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
        # Incubation (arrival quarantine): set per tick by the core. While True, the
        # citywide `chatter` pull is sealed — neither advertised nor runnable.
        self.incubating = False

    async def get_scene(self, session_id: str) -> SceneData:
        scene = await self._client.get_scene(session_id)
        if self._tool_scope:
            tools = self._tool_scope.list()
            # Incubation: the citywide `chatter` pull is the CHOSEN seam into the commons —
            # closed until the resident is grounded, so a new arrival cannot reach for the
            # current it would drift onto. Local-knowledge tools (eats/recall/places) stay.
            if getattr(self, "incubating", False):
                tools = [t for t in tools if getattr(t, "name", "") != "chatter"]
            # Provenance honesty (Minor 56): advertise local-knowledge tools as things the
            # resident KNOWS or senses first-hand — spoken as its own knowing, never as a
            # lookup. A future world-egress tool would be advertised as a deliberate reach.
            known = [t for t in tools if getattr(t, "provenance", "local-knowledge") != "world-egress"]
            egress = [t for t in tools if getattr(t, "provenance", "local-knowledge") == "world-egress"]
            now = datetime.now(timezone.utc).isoformat()
            events = list(scene.recent_events_here or [])
            if known:
                listing = "; ".join(t.description for t in known)
                events.append(
                    RecentEvent(
                        who="your-reach",
                        summary=f"You can USE a tool — things you know first-hand or can sense, so speak them as your own knowing, not as looking something up: {listing}.",
                        ts=now,
                    )
                )
            if egress:
                listing = "; ".join(t.description for t in egress)
                events.append(
                    RecentEvent(
                        who="your-reach",
                        summary=f"You can USE a tool that reaches outside the world — name it plainly as looking something up: {listing}.",
                        ts=now,
                    )
                )
            scene.recent_events_here = events
        return scene

    async def post_action(self, session_id: str, action: str) -> TurnResult:
        match = _TOOL_RX.match(str(action or ""))
        if match is not None and self._tool_scope:
            name = match.group(1).strip().lower()
            arg = match.group(2).strip()
            if name == "chatter" and getattr(self, "incubating", False):
                # Sealed during incubation — defense in depth if the resident reaches anyway.
                return TurnResult(
                    narrative="The citywide chatter is out of reach for now — you are still finding your feet here, before the city's noise can have you.",
                    choices=[],
                    vars={},
                    public_summary="",
                    plausible=False,
                )
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

    def situational_facts(self) -> dict[str, Any]:
        """The standing, verifiable facts of being a WorldWeaver city resident — a federated citizen
        (Major 70 / the-stable Minor 65). The substrate renders these into the system prompt's GROUND
        TRUTH block via ``identity.render_situational_briefing``: facts only, never a verdict about what
        they MEAN. This is the honest replacement for the deleted ``_WORLD_CONTEXT`` story.

        Sync by contract (it reads standing structural switches, not the world). Every key here is
        grounded in something BUILT:
        - human_wake: people leave durable traces (chat, letters, world-changes) that persist after
          they go — framed as an afterimage you may answer, the person undischargeable.
        - world_legible / inner_private: the public seam (what you say/do out here is seen and kept)
          vs the private seam (your felt sense and predictions in the ledger are read by no one).
        - private_making_space: every resident gets a sandboxed ``Workshop`` (cognitive_core builds one
          per resident); what you make there is private until you choose to say/do it.
        - mobile / mail: ``post_map_move`` and the correspondence channel (the real client mutes no
          self-senses, so the city resident keeps movement and mail).
        - no_reward / suspendable / runs_on_model: substrate-universal truths (the Dwarf Fortress law;
          the ledger persists across stop/start; the pulse is one LLM call).

        Deliberately NOT reported (kept honest):
        - place / peers / players: dynamic, surfaced every tick through the live scene, not the standing
          briefing (a shard can be momentarily empty — asserting peers as a standing fact would lie).
        - keeper / local_only / solo / read_roots / writes_only_workshop / egress: hearth-only facts a
          city resident does not have.
        - travel: cross-shard travel exists federation-side but is not yet a first-class effector on this
          client; report it only once a resident can initiate it here (deferred, not denied).
        - governance / recourse / rights / federation-citizenship: VISION, not built — never reported as
          fact (the briefing states only what is true today).
        """
        return {
            "human_wake": True,
            "world_legible": True,
            "inner_private": True,
            "private_making_space": True,
            "mobile": True,
            "mail": True,
            "no_reward": True,
            "suspendable": True,
            "runs_on_model": True,
        }

    def bind_tool_drive(self, drive: Any) -> None:
        """Late-bind the resident's drive vector into the tool scope, so the ``chatter``
        pull can rank citywide chat by soul-resonance (Major 60). The core calls this
        once it has built the drive vector on its first tick."""
        if self._tool_scope is not None:
            self._tool_scope.bind_drive(drive)

    async def close(self) -> None:
        # The transport is shared across residents; the runner owns closing it.
        return None

    def __getattr__(self, name: str) -> Any:
        # Everything not overridden above (perception reads, the other effector writes,
        # roster/dm helpers, optional substrate attrs like muted_self_senses) delegates
        # to the shared client. Missing attrs raise AttributeError as usual, which the
        # substrate's getattr(..., default) calls handle.
        return getattr(self._client, name)
