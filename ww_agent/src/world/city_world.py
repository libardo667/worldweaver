# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""CityWorld — a per-resident body with named elective information sources.

The city analog of ``the-stable``'s ``LocalWorld``: it wraps the shared
``WorldWeaverClient`` (one connection pool, all residents) and layers a *per-resident*
source registry on top. It implements the same
``WorldClient`` Protocol the substrate depends on, so ``CognitiveCore`` runs against it
unchanged — it just delegates the transport to the shared client.

Two methods do the work, mirroring ``LocalWorld`` exactly:
- ``get_scene`` adds typed affordances for the resident's sources. Capabilities are not
  disguised as things that recently happened in the world.
- ``access_information`` resolves a typed private reach against the source registry.
- ``post_action`` recognizes attachment travel and otherwise declines unsupported prose.
  Concrete outward acts have typed effectors; unknown ``do`` text must not buy a second
  model call or let generated prose pretend that world state changed.

Everything else falls through to the shared client via ``__getattr__``; ``close`` is a
no-op here because the transport is shared and the runner owns its lifecycle.
"""

from __future__ import annotations

import re
from typing import Any

from src.runtime.information import InformationSourceRegistry
from src.runtime.travel import TravelRequest, looks_like_city_travel, parse_city_travel, parse_world_travel
from src.world.client import SceneData, TurnResult, WorldAffordance, WorldWeaverClient

# Legacy "use <source> <input>" detector: known sources are declined on the physical
# action path so an old-form pulse cannot silently rejoin narration.
_LEGACY_USE_RX = re.compile(r"^\s*use\s+([a-z][a-z0-9_]*)\b\s*(.*)$", re.IGNORECASE | re.DOTALL)


class CityWorld:
    """Wraps the shared client with one resident's source registry."""

    def __init__(
        self,
        client: WorldWeaverClient,
        source_registry: InformationSourceRegistry | None,
        *,
        hearth_available: bool = True,
    ):
        self._client = client
        self._sources = source_registry
        # Incubation (arrival quarantine): set per tick by the core. While True, the
        # citywide `chatter` pull is sealed — neither advertised nor runnable.
        self.incubating = False
        self._hearth_available = bool(hearth_available)
        self._pending_travel: TravelRequest | None = None

    async def get_scene(self, session_id: str) -> SceneData:
        scene = await self._client.get_scene(session_id)
        if self._sources:
            sources = self._sources.list()
            # Incubation: the citywide `chatter` pull is the CHOSEN seam into the commons —
            # closed until the resident is grounded, so a new arrival cannot reach for the
            # current it would drift onto. Local-knowledge sources (eats/recall/places) stay.
            if getattr(self, "incubating", False):
                sources = [source for source in sources if getattr(source, "name", "") != "chatter"]
            # Provenance honesty (Minor 56): advertise local-knowledge sources as things the
            # resident KNOWS or senses first-hand — spoken as its own knowing, never as a
            # lookup. A future world-egress source would be advertised as a deliberate reach.
            known = [source for source in sources if source.provenance != "world-egress"]
            egress = [source for source in sources if source.provenance == "world-egress"]
            scene.affordances = list(getattr(scene, "affordances", []) or []) + [
                WorldAffordance(
                    source_id=f"source:{source.name}",
                    name=str(source.name or "").strip(),
                    description=str(source.description or "").strip(),
                    provenance=str(source.provenance or "local-knowledge"),
                    freshness=str(source.freshness or "unknown"),
                    locality=str(source.locality or "unknown"),
                    visibility=str(source.visibility or "private"),
                    selection_mode=str(source.selection_mode or "query"),
                )
                for source in [*known, *egress]
            ]
        return scene

    async def post_action(self, session_id: str, action: str) -> TurnResult:
        travel = parse_world_travel(
            action,
            allow_hearth=self._hearth_available,
        )
        if travel is None:
            travel = await self._resolve_city_travel(action)
        if travel is not None:
            self._pending_travel = travel
            return TurnResult(
                narrative=("You make ready to withdraw to your hearth." if travel.destination_kind == "hearth" else f"You make ready to travel to {travel.destination_name}."),
                choices=[],
                vars={},
                travel_pending=True,
            )
        match = _LEGACY_USE_RX.match(str(action or ""))
        if match is not None and self._sources:
            name = match.group(1).strip().lower()
            if name in self._sources.names:
                return TurnResult(
                    narrative=f"{name} is an information source, not a physical action. Reach it privately instead.",
                    choices=[],
                    vars={},
                    public_summary="",
                    plausible=False,
                )
        return TurnResult(
            narrative=(
                "That is not an available world action. Use a concrete ability "
                "the current place actually offers."
            ),
            choices=[],
            vars={},
            public_summary="",
            plausible=False,
        )

    async def post_map_move(
        self,
        session_id: str,
        destination: str,
    ) -> dict[str, Any]:
        travel = parse_world_travel(
            destination,
            allow_hearth=self._hearth_available,
        )
        if travel is None:
            travel = await self._resolve_city_travel(destination)
        if travel is not None:
            self._pending_travel = travel
            return {
                "moved": True,
                "to_location": "your hearth" if travel.destination_kind == "hearth" else travel.destination_name,
                "route_remaining": [],
                "travel_pending": True,
            }
        # The city may recognize a bounded within-place destination and install
        # it beneath the current canonical node. Human map traversal leaves this
        # off by default; resident prose movement opts into the narrower fallback.
        return await self._client.post_map_move(
            session_id,
            destination,
            allow_sublocation_create=True,
        )

    async def _resolve_city_travel(self, text: str) -> TravelRequest | None:
        if not looks_like_city_travel(text):
            return None
        try:
            payload = await self._client.get_travel_destinations()
        except Exception:
            return None
        destinations = payload.get("destinations") if isinstance(payload, dict) else None
        return parse_city_travel(text, destinations if isinstance(destinations, list) else [])

    def take_pending_travel(self) -> TravelRequest | None:
        """Return and clear the world change requested during the last tick."""
        pending = self._pending_travel
        self._pending_travel = None
        return pending

    async def access_information(self, *, kind: str, source: str, query: str = "") -> dict[str, Any]:
        """Resolve one private reach without touching the world action endpoint."""
        name = str(source or "").strip().lower()
        if not self._sources or name not in self._sources.names:
            return {"ok": False, "reason": "unknown_source", "records": []}
        if name == "chatter" and getattr(self, "incubating", False):
            return {"ok": False, "reason": "incubating", "records": []}
        return await self._sources.read(name, str(query or "").strip())

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
          the ledger persists across stop/start; model calls produce each activation episode).

        Deliberately NOT reported (kept honest):
        - place / peers / players: dynamic, surfaced every tick through the live scene, not the standing
          briefing (a shard can be momentarily empty — asserting peers as a standing fact would lie).
        - keeper / local_only / solo / read_roots / writes_only_workshop / egress: hearth-only facts a
          city resident does not have.
        - travel is reported because residents can inspect live federation routes; residents with
          a hearth can also withdraw home through the same host.
        - governance / recourse / rights / federation-citizenship: VISION, not built — never reported as
          fact (the briefing states only what is true today).
        """
        facts: dict[str, Any] = {
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
        facts["travel"] = "inspect live routes to other city nodes"
        if self._hearth_available:
            facts["travel"] += "; move home to withdraw to your private hearth"
        return facts

    def bind_source_drive(self, drive: Any) -> None:
        """Late-bind the resident's drive vector into the source registry, so ``chatter``
        pull can rank citywide chat by soul-resonance (Major 60). The core calls this
        once it has built the drive vector on its first tick."""
        bind = getattr(self._sources, "bind_drive", None)
        if callable(bind):
            bind(drive)

    async def close(self) -> None:
        # The transport is shared across residents; the runner owns closing it.
        return None

    def __getattr__(self, name: str) -> Any:
        # Everything not overridden above (perception reads, the other effector writes,
        # roster/dm helpers, optional substrate attrs like muted_self_senses) delegates
        # to the shared client. Missing attrs raise AttributeError as usual, which the
        # substrate's getattr(..., default) calls handle.
        return getattr(self._client, name)
