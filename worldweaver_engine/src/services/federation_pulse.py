"""Federation pulse loop — runs on city shards when FEDERATION_URL is set.

Sends a periodic heartbeat to ww_world/ reporting active residents, their
locations, and any cross-shard travel events. Processes pending mailbox
messages returned in the pulse response.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from ..config import settings

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# resident_id resolution
# ---------------------------------------------------------------------------

_RESIDENT_ID_CACHE: Dict[str, str] = {}  # session_slug → resident_id


def _session_vars_payload(raw_vars: Any) -> Dict[str, Any]:
    payload = raw_vars if isinstance(raw_vars, dict) else {}
    nested = payload.get("variables")
    if str(payload.get("_v") or "").strip() == "2" and isinstance(nested, dict):
        return nested
    return payload


def _initial_pulse_seq() -> int:
    # Use a wall-clock seed so city-backend restarts don't reset to 0 and get
    # rejected forever as stale by ww_world's out-of-order pulse protection.
    return int(datetime.now(timezone.utc).timestamp())


def _resident_id_for(session_id: str, residents_base: Optional[str] = None) -> Optional[str]:
    """Return the resident_id for a session slug, creating identity/resident_id.txt if needed."""
    # Session IDs follow the pattern {name}-{timestamp}
    name = session_id.split("-")[0] if "-" in session_id else session_id
    if name in _RESIDENT_ID_CACHE:
        return _RESIDENT_ID_CACHE[name]

    # Try to read identity/resident_id.txt from the agent workspace
    base = residents_base or os.environ.get("WW_RESIDENTS_DIR", "residents")
    id_file = Path(base) / name / "identity" / "resident_id.txt"
    if id_file.exists():
        rid = id_file.read_text(encoding="utf-8").strip()
        if rid:
            _RESIDENT_ID_CACHE[name] = rid
            return rid
    identity_dir = id_file.parent
    if not identity_dir.exists():
        return None
    rid = str(uuid.uuid4())
    try:
        id_file.write_text(f"{rid}\n", encoding="utf-8")
    except OSError as exc:
        log.warning("Could not persist resident_id for %s at %s: %s", name, id_file, exc)
        return None
    _RESIDENT_ID_CACHE[name] = rid
    log.info("Created resident actor id for %s at %s", name, id_file)
    return rid
    return None


# ---------------------------------------------------------------------------
# Pulse payload builder
# ---------------------------------------------------------------------------


def _build_pulse_payload(db_session: Any, pulse_seq: int) -> Dict[str, Any]:
    """Build the pulse payload from current active sessions."""
    from ..models import SessionVars

    try:
        rows = db_session.query(SessionVars).all()
    except Exception:
        rows = []

    residents = []
    for row in rows:
        vars_ = _session_vars_payload(row.vars)
        city = vars_.get("city_id") or settings.city_id
        if city != settings.city_id:
            continue  # skip sessions that belong to a different city
        loc = vars_.get("location") or ""
        if not loc:
            continue  # skip incomplete/bootstrap sessions
        session_id = str(row.session_id)
        name = session_id.split("-")[0] if "-" in session_id else session_id
        resident_id = _resident_id_for(session_id)
        if not resident_id:
            continue  # can't federate without a durable ID
        residents.append({
            "resident_id": resident_id,
            "name": name,
            "session_id": session_id,
            "location": loc,
            "status": vars_.get("_dormant_state") or "active",
        })

    return {
        "shard_id": settings.city_id,
        "shard_url": os.environ.get("WW_PUBLIC_URL", ""),
        "pulse_seq": pulse_seq,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "residents": residents,
        "travelers_arriving": [],
        "travelers_departing": [],
    }


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------


def _post_pulse_sync(url: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Synchronously POST pulse payload; returns parsed response or None on error."""
    data = json.dumps(payload).encode()
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if settings.federation_token:
        headers["X-Federation-Token"] = settings.federation_token
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        log.warning("Federation pulse HTTP %d: %s", e.code, body[:200])
    except Exception as exc:
        log.warning("Federation pulse error: %s", exc)
    return None


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------


async def run_pulse_loop(db_factory: Any, interval_seconds: int) -> None:
    """Async loop — fires every interval_seconds and posts a pulse to FEDERATION_URL."""
    pulse_seq = _initial_pulse_seq()
    url = f"{settings.federation_url.rstrip('/')}/api/federation/pulse"  # type: ignore[union-attr]
    log.info("Federation pulse loop started → %s (interval=%ds)", url, interval_seconds)

    while True:
        db = db_factory()
        try:
            payload = _build_pulse_payload(db, pulse_seq)
        finally:
            db.close()

        response = await asyncio.get_event_loop().run_in_executor(
            None, _post_pulse_sync, url, payload
        )
        if response and response.get("accepted") is False:
            log.warning(
                "Federation pulse rejected: shard=%s seq=%s reason=%s",
                payload.get("shard_id"),
                payload.get("pulse_seq"),
                response.get("reason") or "unknown",
            )

        if response and response.get("pending_messages"):
            pending = response["pending_messages"]
            log.info(
                "Federation pulse: %d pending message(s) received from ww_world/",
                len(pending),
            )
            # Deliver pending cross-shard DMs to local DirectMessage table
            db = db_factory()
            try:
                _deliver_pending_messages(db, pending)
            finally:
                db.close()
        pulse_seq += 1
        await asyncio.sleep(interval_seconds)


def _deliver_pending_messages(db: Any, messages: list) -> None:
    """Deposit cross-shard DMs into the local direct_messages table."""
    from ..models import DirectMessage

    for m in messages:
        dm = DirectMessage(
            from_name=m.get("from_resident_id", ""),
            from_session_id=m.get("from_shard", ""),
            to_name=m.get("to_resident_id", ""),
            body=m.get("body", ""),
        )
        db.add(dm)
    if messages:
        db.commit()
        log.info("Delivered %d cross-shard DM(s) to local inbox.", len(messages))
