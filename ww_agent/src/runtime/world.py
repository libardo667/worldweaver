# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

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
    async def get_location_chat(self, location: str, since: Any = None, session_id: str | None = None) -> list[Any]: ...
    async def get_inbox(self, agent_name: str) -> list[Any]: ...
    async def access_information(self, *, kind: str, source: str, query: str = "") -> dict[str, Any]: ...

    # situational grounding (optional, Major 70 / the-stable Minor 65). A world reports VERIFIABLE
    # facts about the entity's circumstances; the substrate renders them (identity.render_situational_
    # briefing) into the system prompt, stating what is true and withholding every verdict about what
    # it means. The world supplies switches, not prose, so the one rendering site is the only place a
    # claim is phrased. The recognised keys (all optional; omit what doesn't apply):
    #   solo:        bool — the entity is the only resident; no peers, no transient visitors
    #   peers:       bool — other resident agents live here too (a populated world)
    #   players:     bool — humans tether to characters, present while attending
    #   keeper:      str  — name of who tends it ("" if none, e.g. a city resident)
    #   place:       str  — where it is ("the hearth", a city location)
    #   local_only:  bool — it runs on this one machine and nowhere else
    #   human_wake:  bool — people leave durable traces (chat, letters, world-changes) after they go.
    #                The briefing frames these as an AFTERIMAGE you may respond to/form — the person
    #                stays undischargeable (no act summons them). See ../the-stable/docs/grief-and-coupling.md.
    #   world_legible: bool — what it says/does is seen by those present and persists (the public seam)
    #   inner_private: bool — its inner state (felt_sense, predictions) is read by no one (the private seam)
    #   private_making_space: bool — what it makes stays private; only what it says/does crosses out
    #   read_roots:  list[str] — display names of exactly what it may read ([] if nothing)
    #   writes_only_workshop: bool — its sole write capability is its own workshop (a hearth fact)
    #   mobile:      bool — it can move through the world (a city affordance)
    #   mail:        bool — it can send word that waits for an absent recipient (a city affordance)
    #   travel:      str  — where it can travel between worlds (hearth ↔ city) and the phrase to use
    #   egress:      bool — anything it does can leave the machine (a tool marked so)
    #   recorded:    bool — its words/acts are written where they can be read back
    #   no_reward:   bool — the substrate holds no reward/goal for it (the Dwarf Fortress law)
    #   suspendable: bool — it can be stopped and woken with its record kept
    #   runs_on_model: bool — its cognition is produced by a language model
    # The recognised keys are exactly identity.BRIEFING_FACT_KEYS (one source of truth, checked by test).
    # EVERY line of the rendered briefing is gated on a fact: a key absent → its line absent. There are
    # no venue defaults, so a world reports its OWN truth at full resolution and inherits none of
    # another's (a city resident is not told it has a keeper or a hearth; a hearth familiar is not told
    # it has peers). A key the renderer does not know is logged loudly by the core (drift). A world that
    # does not implement this at all yields no briefing — silence beats a borrowed story. The method is
    # sync: it reads standing switches, not the world (dynamic place/peers/players ride the per-tick scene).
    def situational_facts(self) -> dict[str, Any]: ...

    # effector writes
    async def post_action(self, session_id: str, action: str) -> Any: ...
    async def post_location_chat(
        self,
        location: str,
        session_id: str,
        message: str,
        display_name: str | None = None,
    ) -> dict[str, Any]: ...
    async def post_map_move(self, session_id: str, destination: str) -> dict[str, Any]: ...
    async def post_world_trace(self, session_id: str, body: str, target: str = "") -> dict[str, Any]: ...
    async def send_letter(
        self,
        from_name: str,
        to_agent: str,
        body: str,
        session_id: str,
        *,
        recipient_type: str = "agent",
    ) -> dict[str, Any]: ...

    # lifecycle
    async def close(self) -> None: ...


# Historical name still used in type hints across the runtime; the substrate depends on
# the Protocol, never on any concrete client.
WorldWeaverClient = WorldClient
