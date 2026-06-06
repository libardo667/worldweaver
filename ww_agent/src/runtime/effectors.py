"""Effectors: carry one routed pulse ``act`` to the world (Major 49, Phase 3).

``act`` is the only field of a pulse that reaches the world. The effector is pure
sensorimotor mechanism — it maps the four act kinds to world-client calls and
records provenance on the canonical ledger (reusing the existing runtime event
types so the Major 46 projections pick the moves up). It makes no decisions; the
pulse already did.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.identity.loader import ResidentIdentity
from src.runtime.ledger import append_runtime_event
from src.runtime.pulse import Act
from src.runtime.workshop import Workshop
from src.runtime.world import WorldWeaverClient

logger = logging.getLogger(__name__)

_CITY_TARGETS = {"city", "__city__", "citywide", "broadcast"}
# A write addressed to one of these goes to the resident's OWN workshop (Major 50),
# not the mail system — output it owns, capability-scoped, safe by construction.
_WORKSHOP_TARGETS = {"journal", "diary", "log", "notebook", "workshop", "zine", "blog", "page", "notes"}


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
        target_name = str(act.target or "").strip()
        target_lower = target_name.lower()
        # Major 63 — speech is physical. A citywide broadcast is a *deliberate, costly act*
        # (an explicit "city"/"broadcast" target); everything else reaches only the room.
        # Addressing a specific person who is NOT co-located is a DIRECTED CARRY — a private
        # word sent to them (the mail path), never an ambient public post. So directed speech
        # can no longer saturate the commons (__city__) into one shared mind-feed everyone
        # overhears, which the canonical-reset trial proved is the engine of convergence.
        # This changes *who can hear*, never *what may be said* — world-physics, law-safe.
        if target_lower in _CITY_TARGETS:
            await self._ww.post_location_chat(location="__city__", session_id=self._session_id, message=act.body, display_name=self._identity.display_name)
            append_runtime_event(self._memory_dir, event_type="city_broadcast_sent", payload={"message": act.body, "addressed": target_name or None})
            return {"executed": True, "kind": "speak", "location": "__city__", "addressed": target_name or None}
        if target_name and target_lower not in {str(p).strip().lower() for p in (self.present or [])}:
            # absent specific person → a private directed carry, not a citywide broadcast
            await self._ww.send_letter(from_name=self._identity.display_name, to_agent=target_name, body=act.body, session_id=self._session_id)
            append_runtime_event(self._memory_dir, event_type="speech_carried", payload={"recipient": target_name, "message": act.body, "sent_at": _utc_now_iso()})
            return {"executed": True, "kind": "speak", "carried_to": target_name}
        location = await self._current_location()
        if not location:
            return {"executed": False, "kind": "speak", "reason": "no_location"}
        await self._ww.post_location_chat(location=location, session_id=self._session_id, message=act.body, display_name=self._identity.display_name)
        append_runtime_event(self._memory_dir, event_type="chat_sent", payload={"location": location, "message": act.body})
        return {"executed": True, "kind": "speak", "location": location, "addressed": target_name or None}

    async def _move(self, act: Act) -> dict[str, Any]:
        destination = str(act.target or act.body or "").strip()
        if not destination:
            return {"executed": False, "kind": "move", "reason": "no_destination"}
        try:
            names = await self._ww.get_place_names()
        except Exception:
            names = set()
        matched = next((n for n in names if n.lower() == destination.lower()), destination)
        result = await self._ww.post_map_move(self._session_id, matched)
        moved = bool(result.get("moved"))
        arrived_at = str(result.get("to_location", matched) or matched)
        if moved:
            self.location = arrived_at
            append_runtime_event(
                self._memory_dir,
                event_type="move_executed",
                payload={"destination": matched, "arrived_at": arrived_at, "remaining": list(result.get("route_remaining") or []), "status": "moved"},
            )
        else:
            append_runtime_event(self._memory_dir, event_type="move_executed", payload={"destination": matched, "status": "blocked"})
        return {"executed": moved, "kind": "move", "destination": matched, "arrived_at": arrived_at if moved else ""}

    async def _do(self, act: Act) -> dict[str, Any]:
        result = await self._ww.post_action(self._session_id, act.body)
        narrative = str(getattr(result, "narrative", "") or "")
        append_runtime_event(
            self._memory_dir,
            event_type="action_executed",
            payload={"action": act.body, "location": await self._current_location(), "narrative": narrative[:200]},
        )
        return {"executed": True, "kind": "do", "narrative": narrative[:200], "detail": narrative}

    async def _write(self, act: Act) -> dict[str, Any]:
        recipient = str(act.target or "").strip()
        # A write to the resident's OWN workshop — output it owns, sandboxed.
        to_workshop = self._workshop is not None and (self._all_writes_to_workshop or recipient.lower() in _WORKSHOP_TARGETS)
        if to_workshop:
            body = str(act.body or "").strip()
            # A write whose body is an SVG is a *drawing*, kept as a picture (a
            # versioned file) rather than appended as prose — for residents who
            # would rather draw than write.
            if body.startswith("<svg"):
                base = recipient.lower() if recipient and recipient.lower() not in {"journal", "diary", "log", "notes"} else "weave"
                result = self._workshop.draw(body, base=base)
                if result.get("written"):
                    append_runtime_event(self._memory_dir, event_type="workshop_drawing", payload={"artifact": result.get("artifact"), "title": result.get("title"), "ts": result.get("ts")})
                return {"executed": bool(result.get("written")), "kind": "write", "drawing": result.get("artifact"), "reason": result.get("reason")}
            kind = recipient.lower()
            artifact = "journal.md" if kind in {"journal", "diary", "log", "notes", ""} else f"{kind}.md"
            result = self._workshop.append(body, artifact=artifact)
            if result.get("written"):
                append_runtime_event(self._memory_dir, event_type="workshop_entry", payload={"artifact": result.get("artifact"), "title": result.get("title"), "ts": result.get("ts")})
            return {"executed": bool(result.get("written")), "kind": "write", "workshop": result.get("artifact"), "reason": result.get("reason")}
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
            payload={"mail_intent_id": f"mailint-{uuid.uuid4().hex[:12]}", "recipient": recipient, "source": "pulse", "sent_at": _utc_now_iso()},
        )
        return {"executed": True, "kind": "write", "recipient": recipient}
