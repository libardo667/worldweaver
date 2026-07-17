# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Effectors: carry one routed pulse ``act`` to the world (Major 49, Phase 3).

``act`` is the only field of a pulse that reaches the world. The effector is pure
sensorimotor mechanism — it maps the outward act kinds to world-client calls and
records provenance on the canonical ledger (reusing the existing runtime event
types so the Major 46 projections pick the moves up). It makes no decisions; the
pulse already did.
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.identity.loader import ResidentIdentity
from src.runtime.ledger import append_runtime_event
from src.runtime.naming import normalize_reference
from src.runtime.pulse import Act
from src.runtime.relations import chat_utterance_id, relational_event_fields
from src.runtime.workshop import Workshop
from src.runtime.world import WorldWeaverClient

logger = logging.getLogger(__name__)

_CITY_TARGETS = {"city", "__city__", "citywide", "broadcast"}
# A write addressed to one of these goes to the resident's OWN workshop (Major 50),
# not the mail system — output it owns, capability-scoped, safe by construction.
_WORKSHOP_TARGETS = {
    "journal",
    "diary",
    "log",
    "notebook",
    "workshop",
    "zine",
    "blog",
    "page",
    "notes",
    "record",
    "my_record",
    "my_own_record",
    "own_record",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorldEffector:
    """Execute a pulse ``act`` against the world on behalf of one resident."""

    def __init__(
        self,
        *,
        ww_client: WorldWeaverClient,
        session_id: str,
        identity: ResidentIdentity,
        memory_dir: Path,
        location_hint: str = "",
        workshop: Workshop | None = None,
        all_writes_to_workshop: bool = False,
    ) -> None:
        self._ww = ww_client
        self._session_id = session_id
        self._identity = identity
        self._memory_dir = memory_dir
        self._workshop = workshop
        # When a resident has no one to write *to* (a solo familiar), every write
        # is its own work — any target lands in the workshop, so it can name and
        # carry its own projects (a zine, an essay) instead of misfiring as mail.
        self._all_writes_to_workshop = bool(all_writes_to_workshop)
        self.location = str(location_hint or "").strip()
        # Who is co-located right now (display names), refreshed by the core each
        # tick. Lets a person-addressed reply reach someone who isn't here.
        self.present: list[str] = []
        # The same co-presence set with durable actor/session identity. Names remain
        # for routing; these references are what relational ledger events record.
        self.co_present: list[dict[str, str]] = []
        # The heard set this tick (speaker + stable msg id), refreshed by the core.
        # Major 66: lets a person-addressed reply record WHICH overture it answers —
        # READ-FROM the already-perceived speech, never elicited from the model.
        self.heard: list[dict[str, Any]] = []
        # Incubation (arrival quarantine): set per tick by the core. While True, a
        # speak act is sealed off the commons and becomes the resident's own making.
        self.incubating = False
        # Cost the megaphone: citywide broadcast is rationed to one per this many seconds
        # per resident (0 = off, the default). A city-targeted speak inside the cooldown
        # lands in the resident's ROOM instead — so the commons stops being a free firehose
        # the loud majority can saturate. Law-safe: it limits HOW OFTEN you address everyone,
        # never WHAT you may say. Tracked in-memory for the run's lifetime.
        self._broadcast_refractory = max(0.0, float(os.environ.get("WW_BROADCAST_REFRACTORY_SECONDS") or 0.0))
        self._last_broadcast_epoch = 0.0

    def relational_context(self, *, location: str | None = None) -> dict[str, Any]:
        return relational_event_fields(
            actor_id=str(self._identity.actor_id or ""),
            actor_session_id=self._session_id,
            location=self.location if location is None else location,
            co_present=self.co_present,
        )

    async def __call__(self, act: Act, *, now: Any = None) -> dict[str, Any]:
        try:
            if act.kind == "speak":
                return await self._speak(act)
            if act.kind == "move":
                return await self._move(act)
            if act.kind == "do":
                return await self._do(act)
            if act.kind == "write":
                return await self._write(act)
            if act.kind == "mark":
                return await self._mark(act)
        except Exception as exc:  # effector failures must never crash the rhythm
            logger.warning("[%s:effector] %s act failed: %s", self._identity.name, act.kind, exc)
            return {"executed": False, "kind": act.kind, "reason": "exception"}
        return {"executed": False, "kind": act.kind, "reason": "unknown_kind"}

    async def _current_location(self) -> str:
        if self.location:
            return self.location
        try:
            scene = await self._ww.get_scene(self._session_id)
            self.location = str(scene.location or "").strip()
        except Exception:
            self.location = ""
        return self.location

    async def _speak(self, act: Act) -> dict[str, Any]:
        # Incubation (arrival quarantine): a sealed resident is not yet wired into the
        # city, so a verbal impulse becomes its OWN making rather than reaching the
        # commons. This keeps it off the citywide feed AND accrues the groundedness that
        # ends the quarantine — the impulse to broadcast becomes a journal entry.
        if self.incubating and self._workshop is not None:
            body = str(act.body or "").strip()
            if not body:
                return {
                    "executed": False,
                    "kind": "speak",
                    "reason": "incubating_empty",
                }
            result = self._workshop.append(body, artifact="journal.md")
            if result.get("written"):
                append_runtime_event(
                    self._memory_dir,
                    event_type="workshop_entry",
                    payload={
                        "artifact": result.get("artifact"),
                        "title": result.get("title"),
                        "ts": result.get("ts"),
                        "source": "incubated_speech",
                    },
                )
            return {
                "executed": bool(result.get("written")),
                "kind": "speak",
                "incubated": True,
                "workshop": result.get("artifact"),
            }
        target_name = str(act.target or "").strip()
        target_lower = target_name.lower()
        # Match co-presence / reply-edges on a separator-folded form so a pen addressing
        # "Ji Hoon Park" (space) reaches a co-present "Ji-Hoon Park" (hyphen) instead of
        # mis-routing to the mail path. Folding is collision-safe: the homophone cluster
        # (Ji-Hoon Park / Jihoon Cho / Jiahao Chen) stays three distinct normalized strings.
        target_norm = normalize_reference(target_name)
        # Major 66 — the reply-edge: which overture (by stable id) this addressed speech
        # answers. READ-FROM the heard set (the most-recent thing the addressee actually
        # said that this resident perceived); never asked of the model. None when the
        # addressee said nothing heard this tick (e.g. a fresh, unprompted overture).
        in_reply_to = self._reply_edge(target_name)
        reply_to_utterance_id = self._reply_utterance_id(target_name)
        addressed_actor_id = self._addressed_actor_id(target_name)
        # Major 63 — speech is physical. A citywide broadcast is a *deliberate, costly act*
        # (an explicit "city"/"broadcast" target); everything else reaches only the room.
        # Addressing a specific person who is NOT co-located is a DIRECTED CARRY — a private
        # word sent to them (the mail path), never an ambient public post. So directed speech
        # can no longer saturate the commons (__city__) into one shared mind-feed everyone
        # overhears, which the canonical-reset trial proved is the engine of convergence.
        # This changes *who can hear*, never *what may be said* — world-physics, law-safe.
        if target_lower in _CITY_TARGETS:
            now_epoch = datetime.now(timezone.utc).timestamp()
            if self._broadcast_refractory > 0.0 and (now_epoch - self._last_broadcast_epoch) < self._broadcast_refractory:
                # Megaphone on cooldown — the words land in the room the resident is in,
                # not the citywide feed (logged as a local chat_sent so the shift is legible).
                location = await self._current_location()
                if not location:
                    append_runtime_event(
                        self._memory_dir,
                        event_type="broadcast_rationed",
                        payload={
                            **self.relational_context(),
                            "message": act.body,
                            "landed": None,
                        },
                    )
                    return {
                        "executed": False,
                        "kind": "speak",
                        "reason": "broadcast_rationed_no_location",
                    }
                posted = await self._ww.post_location_chat(
                    location=location,
                    session_id=self._session_id,
                    message=act.body,
                    display_name=self._identity.display_name,
                )
                append_runtime_event(
                    self._memory_dir,
                    event_type="chat_sent",
                    payload={
                        **self.relational_context(location=location),
                        "utterance_id": chat_utterance_id(location, posted.get("id")),
                        "transport_id": str(posted.get("id") or ""),
                        "location": location,
                        "message": act.body,
                        "addressed": target_name or None,
                        "addressed_actor_id": addressed_actor_id,
                        "in_reply_to": in_reply_to,
                        "reply_to_utterance_id": reply_to_utterance_id,
                        "rationed_from": "city",
                    },
                )
                return {
                    "executed": True,
                    "kind": "speak",
                    "location": location,
                    "rationed": True,
                }
            self._last_broadcast_epoch = now_epoch
            posted = await self._ww.post_location_chat(
                location="__city__",
                session_id=self._session_id,
                message=act.body,
                display_name=self._identity.display_name,
            )
            append_runtime_event(
                self._memory_dir,
                event_type="city_broadcast_sent",
                payload={
                    **self.relational_context(),
                    "utterance_id": chat_utterance_id("__city__", posted.get("id")),
                    "transport_id": str(posted.get("id") or ""),
                    "message": act.body,
                    "addressed": target_name or None,
                    "addressed_actor_id": addressed_actor_id,
                    "in_reply_to": in_reply_to,
                    "reply_to_utterance_id": reply_to_utterance_id,
                },
            )
            return {
                "executed": True,
                "kind": "speak",
                "location": "__city__",
                "addressed": target_name or None,
                "addressed_actor_id": addressed_actor_id,
            }
        if target_name and target_norm not in {normalize_reference(p) for p in (self.present or [])}:
            # absent specific person → a private directed carry, not a citywide broadcast
            await self._ww.send_letter(
                from_name=self._identity.display_name,
                to_agent=target_name,
                body=act.body,
                session_id=self._session_id,
            )
            append_runtime_event(
                self._memory_dir,
                event_type="speech_carried",
                payload={
                    **self.relational_context(),
                    "recipient": target_name,
                    "message": act.body,
                    "sent_at": _utc_now_iso(),
                    "in_reply_to": in_reply_to,
                    "reply_to_utterance_id": reply_to_utterance_id,
                },
            )
            return {"executed": True, "kind": "speak", "carried_to": target_name}
        location = await self._current_location()
        if not location:
            return {"executed": False, "kind": "speak", "reason": "no_location"}
        posted = await self._ww.post_location_chat(
            location=location,
            session_id=self._session_id,
            message=act.body,
            display_name=self._identity.display_name,
        )
        append_runtime_event(
            self._memory_dir,
            event_type="chat_sent",
            payload={
                **self.relational_context(location=location),
                "utterance_id": chat_utterance_id(location, posted.get("id")),
                "transport_id": str(posted.get("id") or ""),
                "location": location,
                "message": act.body,
                "addressed": target_name or None,
                "addressed_actor_id": addressed_actor_id,
                "in_reply_to": in_reply_to,
                "reply_to_utterance_id": reply_to_utterance_id,
            },
        )
        return {
            "executed": True,
            "kind": "speak",
            "location": location,
            "addressed": target_name or None,
        }

    def _reply_edge(self, target_name: str) -> str | None:
        """Major 66 (read-from): the stable id of the most-recent overture from
        ``target_name`` that this resident actually perceived this tick — matched from the
        already-perceived ``heard`` set, never elicited from the model. ``None`` when the
        addressee said nothing heard (an unprompted overture, not a reply)."""
        if not target_name:
            return None
        tl = normalize_reference(target_name)
        for h in reversed(self.heard or []):
            if normalize_reference(str(h.get("speaker") or "")) == tl:
                return str(h.get("id") or "").strip() or None
        return None

    def _reply_utterance_id(self, target_name: str) -> str | None:
        if not target_name:
            return None
        target = normalize_reference(target_name)
        for heard in reversed(self.heard or []):
            if normalize_reference(str(heard.get("speaker") or "")) == target:
                return str(heard.get("source_id") or "").strip() or None
        return None

    def _addressed_actor_id(self, target_name: str) -> str | None:
        if not target_name:
            return None
        target = normalize_reference(target_name)
        for person in self.co_present:
            if normalize_reference(str(person.get("name") or "")) == target:
                return str(person.get("actor_id") or "").strip() or None
        return None

    async def _move(self, act: Act) -> dict[str, Any]:
        destination = str(act.target or act.body or "").strip()
        if not destination:
            return {"executed": False, "kind": "move", "reason": "no_destination"}
        try:
            names = await self._ww.get_place_names()
        except Exception:
            names = set()
        matched = next((n for n in names if n.lower() == destination.lower()), destination)
        departure_context = self.relational_context()
        result = await self._ww.post_map_move(self._session_id, matched)
        moved = bool(result.get("moved"))
        arrived_at = str(result.get("to_location", matched) or matched)
        if bool(result.get("travel_pending")):
            append_runtime_event(
                self._memory_dir,
                event_type="world_travel_requested",
                payload={
                    **departure_context,
                    "destination": matched,
                    "status": "pending",
                },
            )
            return {
                "executed": True,
                "kind": "move",
                "destination": matched,
                "arrived_at": "",
                "travel_pending": True,
            }
        if moved:
            self.location = arrived_at
            append_runtime_event(
                self._memory_dir,
                event_type="move_executed",
                payload={
                    **departure_context,
                    "destination": matched,
                    "arrived_at": arrived_at,
                    "remaining": list(result.get("route_remaining") or []),
                    "status": "moved",
                },
            )
        else:
            append_runtime_event(
                self._memory_dir,
                event_type="move_executed",
                payload={
                    **departure_context,
                    "destination": matched,
                    "status": "blocked",
                },
            )
        return {
            "executed": moved,
            "kind": "move",
            "destination": matched,
            "arrived_at": arrived_at if moved else "",
        }

    async def _do(self, act: Act) -> dict[str, Any]:
        result = await self._ww.post_action(self._session_id, act.body)
        narrative = str(getattr(result, "narrative", "") or "")
        if bool(getattr(result, "travel_pending", False)):
            append_runtime_event(
                self._memory_dir,
                event_type="world_travel_requested",
                payload={
                    **self.relational_context(),
                    "destination": act.body,
                    "status": "pending",
                },
            )
            return {
                "executed": True,
                "kind": "do",
                "narrative": narrative[:200],
                "detail": narrative,
                "travel_pending": True,
            }
        plausible = bool(getattr(result, "plausible", True))
        append_runtime_event(
            self._memory_dir,
            event_type="action_executed" if plausible else "action_declined",
            payload={
                **self.relational_context(),
                "action": act.body,
                "location": await self._current_location(),
                "narrative": narrative[:200],
            },
        )
        return {
            "executed": plausible,
            "kind": "do",
            "narrative": narrative[:200],
            "detail": narrative,
        }

    async def _mark(self, act: Act) -> dict[str, Any]:
        leave_trace = getattr(self._ww, "post_world_trace", None)
        if not callable(leave_trace):
            return {
                "executed": False,
                "kind": "mark",
                "reason": "trace_commons_unavailable",
            }
        result = await leave_trace(self._session_id, act.body, str(act.target or ""))
        trace = dict(result.get("trace") or {}) if isinstance(result, dict) else {}
        executed = bool(isinstance(result, dict) and result.get("ok") and trace.get("trace_id"))
        if executed:
            append_runtime_event(
                self._memory_dir,
                event_type="world_trace_left",
                payload={
                    **self.relational_context(location=str(trace.get("location") or await self._current_location())),
                    "trace_id": str(trace.get("trace_id") or ""),
                    "location": str(trace.get("location") or await self._current_location()),
                    "target": str(trace.get("target") or ""),
                    "body": str(trace.get("body") or act.body),
                    "expires_at": str(trace.get("expires_at") or ""),
                },
            )
        return {
            "executed": executed,
            "kind": "mark",
            "trace": trace,
            **({} if executed else {"reason": "trace_not_created"}),
        }

    async def _write(self, act: Act) -> dict[str, Any]:
        recipient = str(act.target or "").strip()
        normalized_recipient = re.sub(r"[^a-z0-9]+", "_", recipient.lower()).strip("_")
        named_workshop_project = recipient.lower().startswith("workshop:")
        # A write to the resident's OWN workshop — output it owns, sandboxed.
        to_workshop = self._workshop is not None and (
            self._all_writes_to_workshop or normalized_recipient in _WORKSHOP_TARGETS or named_workshop_project
        )
        if to_workshop:
            body = str(act.body or "").strip()
            # A write whose body is an SVG is a *drawing*, kept as a picture (a
            # versioned file) rather than appended as prose — for residents who
            # would rather draw than write.
            if body.startswith("<svg"):
                base = recipient.lower() if recipient and recipient.lower() not in {"journal", "diary", "log", "notes"} else "weave"
                result = self._workshop.draw(body, base=base)
                if result.get("written"):
                    append_runtime_event(
                        self._memory_dir,
                        event_type="workshop_drawing",
                        payload={
                            "artifact": result.get("artifact"),
                            "title": result.get("title"),
                            "ts": result.get("ts"),
                        },
                    )
                return {
                    "executed": bool(result.get("written")),
                    "kind": "write",
                    "drawing": result.get("artifact"),
                    "reason": result.get("reason"),
                }
            kind = recipient.split(":", 1)[1].strip() if named_workshop_project else recipient.lower()
            artifact = "journal.md" if kind in {"journal", "diary", "log", "notes", ""} else f"{kind}.md"
            result = self._workshop.append(body, artifact=artifact)
            if result.get("written"):
                append_runtime_event(
                    self._memory_dir,
                    event_type="workshop_entry",
                    payload={
                        "artifact": result.get("artifact"),
                        "title": result.get("title"),
                        "ts": result.get("ts"),
                    },
                )
            return {
                "executed": bool(result.get("written")),
                "kind": "write",
                "workshop": result.get("artifact"),
                "reason": result.get("reason"),
            }
        if not recipient:
            return {"executed": False, "kind": "write", "reason": "no_recipient"}
        await self._ww.send_letter(
            from_name=self._identity.display_name,
            to_agent=recipient,
            body=act.body,
            session_id=self._session_id,
        )
        append_runtime_event(
            self._memory_dir,
            event_type="mail_intent_sent",
            # Major 66: a letter to someone heard this tick is a reply too. Additive field
            # (readers that don't consume it are unaffected); reciprocity.py does NOT count
            # mail as reciprocation yet — that metric-definition call is deferred.
            payload={
                **self.relational_context(),
                "mail_intent_id": f"mailint-{uuid.uuid4().hex[:12]}",
                "recipient": recipient,
                "source": "pulse",
                "sent_at": _utc_now_iso(),
                "in_reply_to": self._reply_edge(recipient),
                "reply_to_utterance_id": self._reply_utterance_id(recipient),
            },
        )
        return {"executed": True, "kind": "write", "recipient": recipient}
