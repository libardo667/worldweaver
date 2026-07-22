# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Versioned, integrity-checked checkpoint envelopes for synthetic gym runs."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from typing import Any

from sqlalchemy.orm import Session

CHECKPOINT_SCHEMA = "worldweaver.resident-gym.checkpoint"
CHECKPOINT_SCHEMA_VERSION = 1
MAX_SQLITE_SNAPSHOT_BYTES = 64 * 1024 * 1024


class GymCheckpointError(ValueError):
    """A checkpoint is unsupported, damaged, or unsafe to restore."""


def _canonical_json(payload: dict[str, Any]) -> bytes:
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise GymCheckpointError("checkpoint must be JSON serializable") from exc


def _digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def capture_sqlite_database(db: Session) -> dict[str, Any]:
    """Capture one committed synthetic SQLite database as an opaque artifact."""

    db.commit()
    raw = db.connection().connection.driver_connection
    if not isinstance(raw, sqlite3.Connection) or not hasattr(raw, "serialize"):
        raise GymCheckpointError("gym checkpoints currently require SQLite")
    # A file-backed gym uses WAL like a local production shard. Serializing that
    # connection directly preserves a WAL-mode database header which cannot be
    # opened after ``deserialize`` into an isolated in-memory validator. Take a
    # consistent SQLite backup and normalize only the portable copy.
    with tempfile.TemporaryDirectory(prefix="worldweaver-gym-snapshot-") as raw_temp:
        snapshot_path = Path(raw_temp) / "snapshot.sqlite3"
        snapshot = sqlite3.connect(snapshot_path)
        try:
            raw.backup(snapshot)
            mode = snapshot.execute("PRAGMA journal_mode=DELETE").fetchone()
            if mode != ("delete",):
                raise GymCheckpointError(
                    "gym database snapshot could not leave WAL mode"
                )
            snapshot.commit()
        finally:
            snapshot.close()
        data = snapshot_path.read_bytes()
    if len(data) > MAX_SQLITE_SNAPSHOT_BYTES:
        raise GymCheckpointError("gym database snapshot exceeds the size limit")
    return {
        "format": "sqlite3",
        "format_version": 1,
        "byte_length": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "data_base64": base64.b64encode(data).decode("ascii"),
    }


def _decode_sqlite_artifact(raw: Any) -> bytes:
    if not isinstance(raw, dict):
        raise GymCheckpointError("engine database artifact is missing")
    if set(raw) != {
        "format",
        "format_version",
        "byte_length",
        "sha256",
        "data_base64",
    }:
        raise GymCheckpointError("engine database artifact fields are invalid")
    if raw.get("format") != "sqlite3" or raw.get("format_version") != 1:
        raise GymCheckpointError("unsupported engine database artifact")
    try:
        expected_length = int(raw["byte_length"])
        expected_digest = str(raw["sha256"])
        data = base64.b64decode(str(raw["data_base64"]), validate=True)
    except (KeyError, TypeError, ValueError) as exc:
        raise GymCheckpointError("engine database artifact is invalid") from exc
    if expected_length < 0 or expected_length > MAX_SQLITE_SNAPSHOT_BYTES:
        raise GymCheckpointError("engine database snapshot exceeds the size limit")
    if len(expected_digest) != 64 or any(
        character not in "0123456789abcdef" for character in expected_digest
    ):
        raise GymCheckpointError("engine database digest is invalid")
    if (
        len(data) != expected_length
        or hashlib.sha256(data).hexdigest() != expected_digest
    ):
        raise GymCheckpointError("engine database artifact failed integrity validation")
    return data


def validate_sqlite_participant_bindings(
    artifact: dict[str, Any], bindings: list[tuple[str, str]]
) -> None:
    """Check session/actor bindings in an isolated database before restore."""

    data = _decode_sqlite_artifact(artifact)
    connection = sqlite3.connect(":memory:")
    try:
        connection.deserialize(data)
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity != ("ok",):
            raise GymCheckpointError("engine database failed SQLite integrity check")
        rows = {
            str(session_id): str(actor_id or "")
            for session_id, actor_id in connection.execute(
                "SELECT session_id, actor_id FROM session_vars"
            ).fetchall()
        }
    except sqlite3.DatabaseError as exc:
        raise GymCheckpointError(
            "engine database artifact is not a valid gym database"
        ) from exc
    finally:
        connection.close()
    for session_id, actor_id in bindings:
        if rows.get(session_id) != actor_id:
            raise GymCheckpointError(
                f"engine database does not match participant session {session_id}"
            )


def seal_checkpoint(unsigned: dict[str, Any]) -> dict[str, Any]:
    """Attach one content-derived ID and integrity digest."""

    body = json.loads(_canonical_json(unsigned))
    if body.get("schema") != CHECKPOINT_SCHEMA:
        raise GymCheckpointError("unsupported gym checkpoint schema")
    if body.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        raise GymCheckpointError("unsupported gym checkpoint version")
    _decode_sqlite_artifact(body.get("engine_database"))
    digest = _digest(body)
    return {
        **body,
        "checkpoint_id": f"gym-checkpoint-v1-{digest[:24]}",
        "integrity": {"algorithm": "sha256", "digest": digest},
    }


def validate_checkpoint(raw: Any) -> dict[str, Any]:
    """Validate the whole envelope before a caller mutates restore state."""

    if not isinstance(raw, dict):
        raise GymCheckpointError("gym checkpoint must be an object")
    body = dict(raw)
    checkpoint_id = str(body.pop("checkpoint_id", ""))
    integrity = body.pop("integrity", None)
    if set(body) != {
        "schema",
        "schema_version",
        "captured_at",
        "scenario",
        "engine_database",
        "scheduler",
        "gym",
        "participants",
    }:
        raise GymCheckpointError("gym checkpoint fields are invalid")
    if body.get("schema") != CHECKPOINT_SCHEMA:
        raise GymCheckpointError("unsupported gym checkpoint schema")
    if body.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        raise GymCheckpointError("unsupported gym checkpoint version")
    if (
        not isinstance(integrity, dict)
        or set(integrity) != {"algorithm", "digest"}
        or integrity.get("algorithm") != "sha256"
    ):
        raise GymCheckpointError("gym checkpoint integrity metadata is invalid")
    digest = _digest(body)
    if str(integrity.get("digest") or "") != digest:
        raise GymCheckpointError("gym checkpoint failed integrity validation")
    if checkpoint_id != f"gym-checkpoint-v1-{digest[:24]}":
        raise GymCheckpointError("gym checkpoint ID does not match its content")
    _decode_sqlite_artifact(body.get("engine_database"))
    for required in ("captured_at", "scenario", "scheduler", "gym", "participants"):
        if required not in body:
            raise GymCheckpointError(f"gym checkpoint omitted {required}")
    if (
        not isinstance(body["scenario"], dict)
        or not isinstance(body["scheduler"], dict)
        or not isinstance(body["gym"], dict)
    ):
        raise GymCheckpointError("gym checkpoint structure is invalid")
    if not isinstance(body["participants"], list):
        raise GymCheckpointError("gym checkpoint participant list is invalid")
    return body


def restore_sqlite_database(db: Session, artifact: dict[str, Any]) -> None:
    """Replace an empty synthetic SQLite connection after artifact validation."""

    data = _decode_sqlite_artifact(artifact)
    db.rollback()
    db.expunge_all()
    raw = db.connection().connection.driver_connection
    if not isinstance(raw, sqlite3.Connection) or not hasattr(raw, "deserialize"):
        raise GymCheckpointError("gym checkpoints currently require SQLite")
    database_path = next(
        (
            str(row[2] or "")
            for row in raw.execute("PRAGMA database_list").fetchall()
            if str(row[1] or "") == "main"
        ),
        "",
    )
    existing_tables = {
        str(row[0])
        for row in raw.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    for table in existing_tables - {"sqlite_sequence"}:
        quoted_table = table.replace('"', '""')
        count = int(raw.execute(f'SELECT COUNT(*) FROM "{quoted_table}"').fetchone()[0])
        if count:
            raise GymCheckpointError(
                "gym checkpoint restore target must contain no application data"
            )
    if database_path:
        source = sqlite3.connect(":memory:")
        try:
            source.deserialize(data)
            source.backup(raw)
        finally:
            source.close()
    else:
        raw.deserialize(data)
    db.expire_all()
