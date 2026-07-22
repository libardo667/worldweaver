#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Run a deterministic resident-gym episode without a live shard."""

from __future__ import annotations

import argparse
import asyncio
import base64
from contextlib import contextmanager, suppress
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from sqlalchemy import (
    create_engine,
    event as sqlalchemy_event,
    inspect as sqlalchemy_inspect,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import uvicorn

ENGINE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ENGINE_ROOT.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from src.api.game import _state_managers  # noqa: E402
from main import app  # noqa: E402
from src.config import settings  # noqa: E402
from src.database import Base, configure_sqlite_connection, get_db  # noqa: E402
from src.models import (  # noqa: E402
    DurableObject,
    ObjectExchange,
    ResidentSessionRetirementReceipt,
    SessionVars,
    SpaceAccessRequest,
    StoopObjectEntry,
)
from src.services.clock import Clock, ControlledClock, get_world_clock  # noqa: E402
from src.services.gym_batch import summarize_episode  # noqa: E402
from src.services.gym_counterfactual import (  # noqa: E402
    GymCounterfactualBranch,
    GymCounterfactualResult,
)
from src.services.gym_counterfactual_presentation import (  # noqa: E402
    render_counterfactual_html,
    render_counterfactual_terminal,
)
from src.services.gym_presentation import (  # noqa: E402
    render_html,
    render_terminal,
    render_terminal_record,
    render_terminal_stream_footer,
    render_terminal_stream_header,
)
from src.services.resident_gym import (  # noqa: E402
    GymParticipant,
    ProductionRuleGym,
    finish_quiet_interval,
    prepare_quiet_interval,
    run_first_conversation,
    run_quiet_interval,
    run_waiting_letter,
)
from src.services.federation_identity import current_shard_id  # noqa: E402
from src.services.resident_authority import (  # noqa: E402
    activate_resident_generation,
    bind_resident_identity,
    bind_resident_session,
)
from src.services.resident_protocol import ResidentRuntimeCertificate  # noqa: E402
from src.services.session_service import _session_locks  # noqa: E402
from src.services.consequence_objects import found_durable_object  # noqa: E402
from src.services.material_making import initialize_material_pools  # noqa: E402
from src.services.object_exchange import accept_object_exchange  # noqa: E402
from src.services.space_access import (  # noqa: E402
    found_space_policy,
    resolve_access_request,
)
from src.services.world_stoops import (  # noqa: E402
    found_world_stoop,
    take_stoop_object,
)


def _agent_artifact_command(*arguments: str) -> dict:
    completed = subprocess.run(
        [sys.executable, "scripts/resident_gym_artifact.py", *arguments],
        cwd=WORKSPACE_ROOT / "ww_agent",
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "resident process failed")
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("resident process returned an invalid result")
    return payload


_GYM_ADAPTER_PROTOCOL = "worldweaver.gym-participant-stdio"
_GYM_ADAPTER_PROTOCOL_VERSION = 2


def _safe_failure_class(exc: Exception) -> str:
    """Map an exception to one bounded class without retaining its message."""

    message = str(exc)
    if isinstance(exc, SQLAlchemyError):
        return "database"
    if message.startswith("persistent world chronology escaped"):
        return "world_chronology"
    if "attachment" in message:
        return "attachment_invariant"
    if "scheduled" in message or "return" in message:
        return "scheduler_contract"
    if "loopback" in message or "transport" in message:
        return "participant_transport"
    if (
        "resident process" in message
        or "resident host" in message
        or "resident adapter" in message
    ):
        return "resident_process"
    if isinstance(exc, ValueError):
        return "scenario_contract"
    return "runtime_invariant"


def _write_failure_envelope(path: Path | None, *, episode: str, exc: Exception) -> None:
    """Write the only failure fields a batch member may disclose."""

    if path is None:
        return
    output = path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema": "worldweaver.resident-gym.failure",
                "schema_version": 1,
                "episode": str(episode),
                "failure_class": _safe_failure_class(exc),
                "exception_type": type(exc).__name__,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _require_explicit_session_time(session, _flush_context, _instances) -> None:
    """Fail before a controlled run can invoke SessionVars' wall-time fallback."""

    for row in session.dirty:
        if not isinstance(row, SessionVars):
            continue
        state = sqlalchemy_inspect(row)
        if state.attrs.updated_at.history.has_changes():
            continue
        changed = sorted(
            attribute.key
            for attribute in state.attrs
            if attribute.history.has_changes()
        )
        if set(changed) <= {"actor_id", "player_id"}:
            # Bootstrap repairs this intermediate flush to the injected instant
            # before committing the complete joined presence.
            continue
        raise RuntimeError(
            "controlled SessionVars update omitted world time: "
            f"session={row.session_id} fields={changed!r}"
        )


@contextmanager
def _temporary_gym_dependencies(db, *, world_clock: Clock):
    """Bind the production app to one isolated database and world clock."""

    previous_database_override = app.dependency_overrides.get(get_db)
    previous_clock_override = app.dependency_overrides.get(get_world_clock)

    def override_database():
        yield db

    def override_world_clock():
        return world_clock

    app.dependency_overrides[get_db] = override_database
    app.dependency_overrides[get_world_clock] = override_world_clock
    try:
        yield
    finally:
        if previous_database_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_database_override
        if previous_clock_override is None:
            app.dependency_overrides.pop(get_world_clock, None)
        else:
            app.dependency_overrides[get_world_clock] = previous_clock_override


@contextmanager
def _temporary_gym_request_dependencies(session_factory, *, world_clock: Clock):
    """Give every real loopback request its own isolated database session."""

    previous_database_override = app.dependency_overrides.get(get_db)
    previous_clock_override = app.dependency_overrides.get(get_world_clock)

    def override_database():
        with session_factory() as request_db:
            yield request_db

    def override_world_clock():
        return world_clock

    app.dependency_overrides[get_db] = override_database
    app.dependency_overrides[get_world_clock] = override_world_clock
    try:
        yield
    finally:
        if previous_database_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_database_override
        if previous_clock_override is None:
            app.dependency_overrides.pop(get_world_clock, None)
        else:
            app.dependency_overrides[get_world_clock] = previous_clock_override


@contextmanager
def _temporary_gym_api(db, *, world_clock: Clock):
    """Serve the production FastAPI app through an in-process ASGI transport."""

    with _temporary_gym_dependencies(db, world_clock=world_clock):
        yield _GymAPIClient(db)


class _GymAPIClient:
    """Synchronously dispatch requests through FastAPI's ASGI boundary."""

    def __init__(self, db) -> None:
        self._db = db

    def request(
        self,
        method: str,
        target: str,
        *,
        fail_before_domain_commit: bool = False,
        **kwargs,
    ) -> httpx.Response:
        commit_count = 0

        def fail_second_commit(_session) -> None:
            nonlocal commit_count
            commit_count += 1
            if commit_count == 2:
                raise RuntimeError("injected retirement failure before commit")

        if fail_before_domain_commit:
            sqlalchemy_event.listen(self._db, "before_commit", fail_second_commit)

        async def dispatch() -> httpx.Response:
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://worldweaver-gym.local",
            ) as client:
                return await client.request(method, target, **kwargs)

        try:
            return asyncio.run(dispatch())
        finally:
            if fail_before_domain_commit:
                sqlalchemy_event.remove(self._db, "before_commit", fail_second_commit)


class _ObservedLoopbackApp:
    """Record content-safe HTTP receipts around the real loopback ASGI server."""

    def __init__(self, gym: ProductionRuleGym, participant_session_id: str) -> None:
        self._gym = gym
        self._participant_session_id = participant_session_id

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await app(scope, receive, send)
            return
        status_code = 500
        response_parts: list[bytes] = []
        recorded = False
        raw_path = scope.get("raw_path") or str(scope.get("path") or "").encode("ascii")
        raw_query = scope.get("query_string") or b""
        target = bytes(raw_path).decode("ascii")
        if raw_query:
            target = f"{target}?{bytes(raw_query).decode('ascii')}"
        headers = {
            bytes(key).decode("latin1").lower(): bytes(value).decode("latin1")
            for key, value in scope.get("headers") or []
        }

        def record_response() -> None:
            nonlocal recorded
            if recorded:
                return
            recorded = True
            try:
                response_payload = json.loads(b"".join(response_parts))
            except (json.JSONDecodeError, UnicodeDecodeError):
                response_payload = None
            self._gym.db.expire_all()
            self._gym.record_participant_http(
                self._participant_session_id,
                method=str(scope.get("method") or ""),
                target=target,
                status_code=status_code,
                resident_proof=all(
                    str(headers.get(name.lower()) or "").strip()
                    for name in (
                        "X-WW-Resident-Certificate",
                        "X-WW-Resident-Timestamp",
                        "X-WW-Resident-Nonce",
                        "X-WW-Resident-Signature",
                    )
                ),
                response_payload=response_payload,
            )
            if (
                str(scope.get("method") or "").upper() == "POST"
                and target.partition("?")[0] == "/api/session/leave"
                and 200 <= status_code < 300
                and isinstance(response_payload, dict)
            ):
                self._gym.record_resident_departure_receipt(
                    self._participant_session_id,
                    response_payload,
                )

        async def observe_send(message) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status") or 500)
            elif message.get("type") == "http.response.body":
                response_parts.append(bytes(message.get("body") or b""))
                if not message.get("more_body", False):
                    record_response()
            await send(message)

        await app(scope, receive, observe_send)
        record_response()


@contextmanager
def _temporary_gym_loopback(
    db,
    *,
    session_factory,
    world_clock: Clock,
    gym: ProductionRuleGym,
    participant_session_id: str,
):
    """Serve the production app on a real ephemeral IPv4 loopback socket."""

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    host, port = listener.getsockname()[:2]
    observed_app = _ObservedLoopbackApp(gym, participant_session_id)
    config = uvicorn.Config(
        observed_app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
        lifespan="off",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(
        target=server.run,
        kwargs={"sockets": [listener]},
        name="worldweaver-gym-loopback",
        daemon=True,
    )
    with _temporary_gym_request_dependencies(session_factory, world_clock=world_clock):
        thread.start()
        deadline = time.monotonic() + 10.0
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        if not server.started:
            server.should_exit = True
            thread.join(timeout=5)
            raise RuntimeError("gym loopback server did not start")
        gym.record_resident_transport(
            participant_session_id,
            transport="loopback_http",
        )
        try:
            yield f"http://{host}:{port}"
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            if thread.is_alive():
                server.force_exit = True
                thread.join(timeout=5)
            with suppress(OSError):
                listener.close()
            if thread.is_alive():
                raise RuntimeError("gym loopback server did not stop")


class _InjectedResidentCrash(RuntimeError):
    """The gym intentionally stopped a resident at one durable boundary."""


def _stop_adapter_process(process: subprocess.Popen[str]) -> None:
    """Terminate and reap one failed adapter child without leaving a zombie."""

    if process.poll() is None:
        process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


@contextmanager
def _temporary_gym_node_configuration(*, shard_experience_path: Path | None = None):
    """Publish a synthetic node identity through ordinary node settings."""

    previous = {
        "city_id": settings.city_id,
        "shard_id": settings.shard_id,
        "shard_type": settings.shard_type,
        "shard_experience_path": settings.shard_experience_path,
    }
    settings.city_id = "resident_gym"
    settings.shard_id = "resident-gym"
    settings.shard_type = "city"
    settings.shard_experience_path = (
        str(shard_experience_path.resolve())
        if shard_experience_path is not None
        else None
    )
    try:
        yield
    finally:
        for name, value in previous.items():
            setattr(settings, name, value)


def _model_adapter_command(
    gym: ProductionRuleGym,
    *,
    api_client: _GymAPIClient | None,
    home: Path,
    host_key: Path,
    process_path: Path,
    participant_session_id: str,
    protocol_session_id: str,
    now: datetime,
    model_id: str,
    model_mode: str = "live",
    command: str = "handle-return-model",
    event_id: str = "",
    scenario_step: int = 0,
    departure_fault: str = "",
    transport_fault: str = "",
    transport_mode: str = "stdio",
    base_url: str = "http://worldweaver-gym.local",
    scripted_source: str = "",
    scripted_query: str = "",
    scripted_target: str = "",
    scripted_action_kind: str = "do",
) -> dict:
    """Run one child resident while serving its bounded world requests."""

    arguments = [
        sys.executable,
        "scripts/resident_gym_artifact.py",
        command,
        "--home",
        str(home),
        "--host-key",
        str(host_key),
        "--expected-process",
        str(process_path),
        "--now",
        now.isoformat(),
        "--model",
        model_id,
        "--model-mode",
        model_mode,
        "--scenario-step",
        str(int(scenario_step)),
        "--transport-fault",
        transport_fault,
        "--transport-mode",
        transport_mode,
        "--base-url",
        base_url,
    ]
    if event_id:
        arguments.extend(("--event-id", event_id))
    if scripted_source:
        arguments.extend(("--scripted-source", scripted_source))
    if scripted_query:
        arguments.extend(("--scripted-query", scripted_query))
    if scripted_target:
        arguments.extend(("--scripted-target", scripted_target))
    if scripted_action_kind != "do":
        arguments.extend(("--scripted-action-kind", scripted_action_kind))
    process = subprocess.Popen(
        arguments,
        cwd=WORKSPACE_ROOT / "ww_agent",
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.stdin is None or process.stdout is None or process.stderr is None:
        process.kill()
        raise RuntimeError("resident adapter pipes were not created")
    expected_participant_session_id = str(participant_session_id or "").strip()
    expected_protocol_session_id = str(protocol_session_id or "").strip()
    if not expected_participant_session_id or not expected_protocol_session_id:
        process.kill()
        raise RuntimeError("resident adapter session binding is incomplete")

    def respond(request_id: str, *, ok: bool, result=None, error: str = "") -> None:
        process.stdin.write(
            json.dumps(
                {
                    "protocol": _GYM_ADAPTER_PROTOCOL,
                    "protocol_version": _GYM_ADAPTER_PROTOCOL_VERSION,
                    "type": "response",
                    "request_id": request_id,
                    "ok": ok,
                    "result": result,
                    "error": error,
                },
                sort_keys=True,
            )
            + "\n"
        )
        process.stdin.flush()

    result: dict | None = None
    leave_fault_injected = False
    seen_request_ids: set[str] = set()
    for line in process.stdout:
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            _stop_adapter_process(process)
            raise RuntimeError("resident adapter emitted invalid JSON") from exc
        if (
            not isinstance(message, dict)
            or message.get("protocol") != _GYM_ADAPTER_PROTOCOL
            or message.get("protocol_version") != _GYM_ADAPTER_PROTOCOL_VERSION
        ):
            _stop_adapter_process(process)
            raise RuntimeError("resident adapter protocol binding is invalid")
        message_type = str(message.get("type") or "")
        if message_type == "event":
            event_kind = str(message.get("event") or "")
            try:
                gym.record_resident_boundary(
                    expected_participant_session_id,
                    kind=event_kind,
                    detail=(
                        dict(message.get("detail") or {})
                        if isinstance(message.get("detail"), dict)
                        else {}
                    ),
                )
            except Exception:
                _stop_adapter_process(process)
                raise
            if (
                departure_fault == "after_hearth_checkpoint"
                and event_kind == "resident_attachment_checkpointed"
            ):
                gym.record_resident_departure_fault(
                    expected_participant_session_id,
                    mode=departure_fault,
                )
                _stop_adapter_process(process)
                raise _InjectedResidentCrash(
                    "resident stopped after durable hearth checkpoint"
                )
            continue
        if message_type == "result":
            candidate = message.get("result")
            if not isinstance(candidate, dict):
                _stop_adapter_process(process)
                raise RuntimeError("resident adapter result must be an object")
            result = candidate
            break
        if message_type == "error":
            _stop_adapter_process(process)
            raise RuntimeError(str(message.get("error") or "resident adapter failed"))
        if message_type != "request":
            _stop_adapter_process(process)
            raise RuntimeError("resident adapter emitted an unknown message")
        request_id = str(message.get("request_id") or "")
        session_id = str(message.get("session_id") or "")
        operation = str(message.get("operation") or "")
        payload = message.get("payload")
        if not request_id or request_id in seen_request_ids:
            _stop_adapter_process(process)
            raise RuntimeError("resident adapter replayed or omitted a request ID")
        seen_request_ids.add(request_id)
        if session_id != expected_protocol_session_id or not isinstance(payload, dict):
            _stop_adapter_process(process)
            raise RuntimeError("resident adapter request binding is invalid")
        try:
            if operation != "http":
                raise ValueError("unsupported gym participant operation")
            if api_client is None:
                raise ValueError("loopback resident may not use stdio HTTP dispatch")
            method = str(payload.get("method") or "").strip().upper()
            target = str(payload.get("target") or "").strip()
            headers = payload.get("headers")
            if method not in {"GET", "POST"}:
                raise ValueError("unsupported gym participant HTTP method")
            if not (target.startswith("/api/") or target == "/health"):
                raise ValueError("unsupported gym participant HTTP target")
            if not isinstance(headers, dict):
                raise ValueError("gym participant HTTP headers are invalid")
            body = base64.b64decode(
                str(payload.get("body_base64") or ""), validate=True
            )
            leave_request = method == "POST" and target == "/api/session/leave"
            inject_here = leave_request and not leave_fault_injected
            if inject_here and departure_fault == "before_request":
                leave_fault_injected = True
                gym.record_resident_departure_fault(
                    expected_participant_session_id,
                    mode=departure_fault,
                )
                respond(request_id, ok=False, error="injected failure before request")
                continue
            if transport_fault == "malformed_response":
                process.stdin.write("{malformed-response\n")
                process.stdin.flush()
                transport_fault = ""
                continue
            api_response = api_client.request(
                method,
                target,
                fail_before_domain_commit=(
                    inject_here and departure_fault == "before_commit"
                ),
                headers={str(key): str(value) for key, value in headers.items()},
                content=body,
            )
            if inject_here and departure_fault == "before_commit":
                leave_fault_injected = True
                gym.record_resident_departure_fault(
                    expected_participant_session_id,
                    mode=departure_fault,
                )
            try:
                response_payload = api_response.json()
            except ValueError:
                response_payload = None
            gym.record_participant_http(
                expected_participant_session_id,
                method=method,
                target=target,
                status_code=api_response.status_code,
                resident_proof=all(
                    str(headers.get(name) or headers.get(name.lower()) or "").strip()
                    for name in (
                        "X-WW-Resident-Certificate",
                        "X-WW-Resident-Timestamp",
                        "X-WW-Resident-Nonce",
                        "X-WW-Resident-Signature",
                    )
                ),
                response_payload=response_payload,
            )
            if (
                leave_request
                and 200 <= api_response.status_code < 300
                and isinstance(response_payload, dict)
            ):
                gym.record_resident_departure_receipt(
                    expected_participant_session_id,
                    response_payload,
                )
            if inject_here and departure_fault == "response_loss":
                leave_fault_injected = True
                gym.record_resident_departure_fault(
                    expected_participant_session_id,
                    mode=departure_fault,
                )
                respond(request_id, ok=False, error="injected response loss")
                continue
            response = {
                "status_code": api_response.status_code,
                "headers": dict(api_response.headers),
                "body_base64": base64.b64encode(api_response.content).decode("ascii"),
            }
        except Exception as exc:
            respond(request_id, ok=False, error=type(exc).__name__)
        else:
            respond(request_id, ok=True, result=response)

    process.stdin.close()
    return_code = process.wait()
    stderr = process.stderr.read().strip()
    if return_code != 0 or result is None:
        raise RuntimeError(stderr or "resident adapter stopped without a result")
    return result


def _memory_database():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)()


@contextmanager
def _temporary_branch_database(path: Path):
    """Open one file-backed fork database with production SQLite settings."""

    engine = create_engine(
        f"sqlite+pysqlite:///{path}",
        connect_args={"check_same_thread": False},
    )
    sqlalchemy_event.listen(engine, "connect", configure_sqlite_connection)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    sqlalchemy_event.listen(
        session_factory, "before_flush", _require_explicit_session_time
    )
    try:
        with session_factory() as db:
            yield db, session_factory
    finally:
        engine.dispose()
        _state_managers.clear()
        _session_locks.clear()


def _run_scripted_resident_return(db, *, record_observer=None):
    """Show the stop, due return, lost acknowledgement, and safe retry path."""

    with tempfile.TemporaryDirectory(prefix="worldweaver-gym-return-") as raw_temp:
        temp = Path(raw_temp)
        artifact = _agent_artifact_command(
            "create-fixture",
            "--home",
            str(temp / "source-resident"),
            "--package",
            str(temp / "resident.wwhearth"),
            "--actor-id",
            "gym-afternoon-actor-mara",
            "--world-id",
            "gym-long-afternoon-world",
            "--session-id",
            "gym-afternoon-mara",
            "--started-at",
            "2026-07-20T12:00:00+00:00",
            "--return-at",
            "2026-07-22T12:00:00+00:00",
        )
        process = artifact["process"]
        scheduled_return = artifact["scheduled_return"]
        descriptor_path = temp / "descriptor.json"
        process_path = temp / "process.json"
        scene_path = temp / "scene.json"
        descriptor_path.write_text(json.dumps(artifact["descriptor"]), encoding="utf-8")
        process_path.write_text(json.dumps(process), encoding="utf-8")

        gym = prepare_quiet_interval(
            db,
            record_observer=record_observer,
            mara_implementation="reference_resident_scripted_wait",
        )
        gym.bind_participant_artifacts(
            "gym-afternoon-mara",
            adapter_id=process["adapter"]["id"],
            adapter_version=process["adapter"]["version"],
            model_id=process["model"]["id"],
            private_state=artifact["descriptor"],
        )
        gym.schedule_resident_return(
            "gym-afternoon-mara",
            resident_event_id=scheduled_return["event_id"],
            activity_id=scheduled_return["activity_id"],
            due_at=datetime.fromisoformat(scheduled_return["due_at"]),
        )
        first_checkpoint = json.loads(json.dumps(gym.checkpoint()))
        _agent_artifact_command(
            "restore",
            "--package",
            str(temp / "resident.wwhearth"),
            "--home",
            str(temp / "restored-resident"),
            "--descriptor",
            str(descriptor_path),
            "--expected-process",
            str(process_path),
        )

        first_engine, first_db = _memory_database()
        replay_engine, replay_db = _memory_database()
        try:
            first = ProductionRuleGym.from_checkpoint(
                first_db,
                first_checkpoint,
                record_observer=record_observer,
            )
            inspection = first.offer_next_scheduled()[0]
            first.inspect_sublocation(
                parent_location=str(inspection.payload["parent_location"]),
                sublocation_id=str(inspection.payload["sublocation_id"]),
            )
            first.acknowledge_scheduled((inspection.event_id,))
            due = first.offer_next_scheduled()[0]

            def handle_return(event, scene):
                scene_path.write_text(json.dumps(scene), encoding="utf-8")
                return _agent_artifact_command(
                    "handle-return",
                    "--home",
                    str(temp / "restored-resident"),
                    "--expected-process",
                    str(process_path),
                    "--scene",
                    str(scene_path),
                    "--event-id",
                    str(event.payload["resident_event_id"]),
                    "--now",
                    event.due_at.isoformat(),
                )

            first.deliver_resident_return(due, handle_return)
            lost_ack_checkpoint = json.loads(json.dumps(first.checkpoint()))

            replay = ProductionRuleGym.from_checkpoint(
                replay_db,
                lost_ack_checkpoint,
                record_observer=record_observer,
            )
            retried = replay.offer_next_scheduled()[0]
            replay.deliver_resident_return(retried, handle_return)
            replay.acknowledge_scheduled((retried.event_id,))
            return finish_quiet_interval(replay)
        finally:
            first_db.close()
            replay_db.close()
            first_engine.dispose()
            replay_engine.dispose()
            _state_managers.clear()
            _session_locks.clear()


def _run_model_resident_return(
    db,
    *,
    session_factory=None,
    record_observer=None,
    model_id: str,
    model_mode: str = "live",
    departure_fault: str = "",
    transport_fault: str = "",
    transport_mode: str = "stdio",
):
    """Run one bounded model activation entirely inside the synthetic gym."""

    with (
        tempfile.TemporaryDirectory(prefix="worldweaver-gym-model-") as raw_temp,
        _temporary_gym_node_configuration(),
    ):
        temp = Path(raw_temp)
        source_home = temp / "source-resident"
        source_package = temp / "resident-before.wwhearth"
        host_key = temp / "gym-host-transport.key"
        artifact = _agent_artifact_command(
            "create-fixture",
            "--home",
            str(source_home),
            "--package",
            str(source_package),
            "--host-key",
            str(host_key),
            "--actor-id",
            "gym-afternoon-actor-mara",
            "--display-name",
            "Mara",
            "--world-id",
            "gym-long-afternoon-world",
            "--session-id",
            "gym-afternoon-mara",
            "--model-id",
            model_id,
            "--started-at",
            "2026-07-20T12:00:00+00:00",
            "--return-at",
            "2026-07-22T12:00:00+00:00",
        )
        process_binding = artifact["process"]
        scheduled_return = artifact["scheduled_return"]
        identity = artifact.get("identity")
        if not isinstance(identity, dict):
            raise RuntimeError("model gym fixture omitted resident identity proof")
        process_path = temp / "process.json"
        process_path.write_text(json.dumps(process_binding), encoding="utf-8")

        gym = prepare_quiet_interval(
            db,
            record_observer=record_observer,
            mara_implementation="reference_resident_model",
            episode="The Model Appointment",
        )
        gym.bind_participant_artifacts(
            "gym-afternoon-mara",
            adapter_id=process_binding["adapter"]["id"],
            adapter_version=process_binding["adapter"]["version"],
            model_id=process_binding["model"]["id"],
            private_state=artifact["descriptor"],
        )
        gym.schedule_resident_return(
            "gym-afternoon-mara",
            resident_event_id=scheduled_return["event_id"],
            activity_id=scheduled_return["activity_id"],
            due_at=datetime.fromisoformat(scheduled_return["due_at"]),
        )
        audience = current_shard_id()
        certificate_result = _agent_artifact_command(
            "issue-runtime-certificate",
            "--home",
            str(source_home),
            "--host-key",
            str(host_key),
            "--audience",
            audience,
        )
        certificate_header = str(
            certificate_result.get("certificate_header") or ""
        ).strip()
        certificate = ResidentRuntimeCertificate.decode_header(certificate_header)
        bind_resident_identity(
            db,
            actor_id=str(identity.get("actor_id") or ""),
            hearth_shard_id=str(identity.get("hearth_shard_id") or ""),
            identity_public_key=str(identity.get("identity_public_key") or ""),
            recovery_policy_version=int(identity.get("recovery_policy_version") or 0),
            admission_reason="synthetic resident gym fixture",
            admitted_by="resident-gym",
        )
        activate_resident_generation(
            db,
            certificate=certificate,
            expected_audience=audience,
        )
        bind_resident_session(
            db,
            session_id="gym-afternoon-mara",
            actor_id=str(identity.get("actor_id") or ""),
            runtime_generation=certificate.runtime_generation,
        )
        db.commit()
        inspection = gym.offer_next_scheduled()[0]
        gym.inspect_sublocation(
            parent_location=str(inspection.payload["parent_location"]),
            sublocation_id=str(inspection.payload["sublocation_id"]),
        )
        gym.acknowledge_scheduled((inspection.event_id,))
        due = gym.offer_next_scheduled()[0]

        participant_session_id = "gym-afternoon-mara"
        if transport_mode == "stdio":
            transport_context = _temporary_gym_api(db, world_clock=gym.clock)
        elif transport_mode == "loopback":
            if departure_fault or transport_fault:
                raise ValueError("loopback transport does not accept stdio fault modes")
            if session_factory is None:
                raise RuntimeError(
                    "loopback transport requires a database session factory"
                )
            transport_context = _temporary_gym_loopback(
                db,
                session_factory=session_factory,
                world_clock=gym.clock,
                gym=gym,
                participant_session_id=participant_session_id,
            )
        else:
            raise ValueError("unsupported model gym transport")

        with transport_context as transport_endpoint:
            api_client = (
                transport_endpoint
                if isinstance(transport_endpoint, _GymAPIClient)
                else None
            )
            base_url = (
                "http://worldweaver-gym.local"
                if api_client is not None
                else str(transport_endpoint)
            )

            def deliver(*, fault: str = "") -> dict:
                current_process = json.loads(process_path.read_text(encoding="utf-8"))

                def handle_return(event, _scene):
                    return _model_adapter_command(
                        gym,
                        api_client=api_client,
                        home=source_home,
                        host_key=host_key,
                        process_path=process_path,
                        participant_session_id=participant_session_id,
                        protocol_session_id=str(
                            current_process["attachment"]["session_id"]
                        ),
                        now=event.due_at,
                        model_id=model_id,
                        model_mode=model_mode,
                        event_id=str(event.payload["resident_event_id"]),
                        departure_fault=fault,
                        transport_fault=transport_fault,
                        transport_mode=transport_mode,
                        base_url=base_url,
                    )

                return gym.deliver_resident_return(due, handle_return)

            try:
                first_result = deliver(fault=departure_fault)
            except _InjectedResidentCrash:
                if departure_fault != "after_hearth_checkpoint":
                    raise
                first_result = None
                checkpointed_process = _agent_artifact_command(
                    "describe-process",
                    "--home",
                    str(source_home),
                )
                process_path.write_text(
                    json.dumps(checkpointed_process), encoding="utf-8"
                )
            else:
                first_process = first_result.get("process")
                if not isinstance(first_process, dict):
                    raise RuntimeError("model resident omitted its process checkpoint")
                process_path.write_text(json.dumps(first_process), encoding="utf-8")

            current_process = json.loads(process_path.read_text(encoding="utf-8"))
            current_attachment = current_process.get("attachment")
            if not isinstance(current_attachment, dict):
                raise RuntimeError("model resident omitted its attachment checkpoint")

            if current_attachment.get("kind") == "city":
                if departure_fault:
                    retry_result = deliver()
                    if int(retry_result.get("model_call_count") or 0) != 0:
                        raise RuntimeError(
                            "departure recovery repeated model inference"
                        )
                    final_process = retry_result.get("process")
                    if not isinstance(final_process, dict):
                        raise RuntimeError(
                            "departure retry omitted its process checkpoint"
                        )
                    process_path.write_text(json.dumps(final_process), encoding="utf-8")
                else:
                    final_process = current_process
            elif current_attachment.get("kind") == "hearth":
                final_process = current_process
            else:
                raise RuntimeError("model resident stopped at an invalid attachment")

            if not isinstance(final_process, dict):
                raise RuntimeError("model resident omitted its process checkpoint")
            attachment = final_process.get("attachment")
            if not isinstance(attachment, dict) or attachment.get("kind") not in {
                "city",
                "hearth",
            }:
                raise RuntimeError("model resident checkpointed an invalid attachment")
            if departure_fault and attachment.get("kind") != "hearth":
                raise RuntimeError("departure recovery did not reach the hearth")
            process_path.write_text(json.dumps(final_process), encoding="utf-8")
            needs_hearth_restart = attachment.get("kind") == "hearth" and (
                not departure_fault or departure_fault == "after_hearth_checkpoint"
            )
            if needs_hearth_restart:
                hearth_result = _model_adapter_command(
                    gym,
                    api_client=api_client,
                    home=source_home,
                    host_key=host_key,
                    process_path=process_path,
                    participant_session_id=participant_session_id,
                    protocol_session_id=str(attachment["session_id"]),
                    now=gym.clock.now(),
                    model_id=model_id,
                    model_mode=model_mode,
                    command="observe-hearth-model",
                    transport_mode=transport_mode,
                    base_url=base_url,
                )
                restarted_process = hearth_result.get("process")
                restarted_attachment = (
                    restarted_process.get("attachment")
                    if isinstance(restarted_process, dict)
                    else None
                )
                restarted_hosting = (
                    restarted_process.get("hosting")
                    if isinstance(restarted_process, dict)
                    else None
                )
                if (
                    hearth_result.get("status") != "observed"
                    or int(hearth_result.get("model_call_count") or 0) != 0
                    or not isinstance(restarted_attachment, dict)
                    or restarted_attachment.get("kind") != "hearth"
                    or not isinstance(restarted_hosting, dict)
                    or restarted_hosting.get("state") != "suspended"
                ):
                    raise RuntimeError("restarted hearth observation was not clean")
                process_path.write_text(
                    json.dumps(restarted_process),
                    encoding="utf-8",
                )
                final_process = restarted_process

            final_attachment = final_process.get("attachment")
            final_hosting = final_process.get("hosting")
            expected_attachment = (
                str(final_attachment.get("kind") or "")
                if isinstance(final_attachment, dict)
                else ""
            )
            expected_session_id = (
                "gym-afternoon-actor-mara-hearth"
                if expected_attachment == "hearth"
                else "gym-afternoon-mara"
            )
            if (
                not isinstance(final_attachment, dict)
                or expected_attachment not in {"city", "hearth"}
                or str(final_attachment.get("session_id") or "") != expected_session_id
                or not isinstance(final_hosting, dict)
                or final_hosting.get("state") != "suspended"
            ):
                raise RuntimeError(
                    "model resident did not finish suspended at its checkpointed attachment"
                )
            active_city_sessions = (
                db.query(SessionVars)
                .filter(SessionVars.actor_id == "gym-afternoon-actor-mara")
                .count()
            )
            expected_city_sessions = 0 if expected_attachment == "hearth" else 1
            expected_receipts = 1 if expected_attachment == "hearth" else 0
            if active_city_sessions != expected_city_sessions:
                raise RuntimeError("model resident attachment count is inconsistent")
            if db.query(ResidentSessionRetirementReceipt).count() != expected_receipts:
                raise RuntimeError(
                    "model resident retirement receipt count is inconsistent"
                )
            gym.record_resident_attachment_verified(
                participant_session_id,
                attachment=expected_attachment,
                process_hosting_state="suspended",
                active_city_session_count=active_city_sessions,
            )
        gym.acknowledge_scheduled((due.event_id,))
        updated_descriptor = _agent_artifact_command(
            "export",
            "--home",
            str(source_home),
            "--package",
            str(temp / "resident-after.wwhearth"),
        )
        gym.bind_participant_artifacts(
            "gym-afternoon-mara",
            adapter_id=process_binding["adapter"]["id"],
            adapter_version=process_binding["adapter"]["version"],
            model_id=process_binding["model"]["id"],
            private_state=updated_descriptor,
        )
        gym.audit_world_chronology()
        return gym.result()


def _run_counterfactual_model_fork(
    db,
    *,
    record_observer=None,
    model_id: str,
    model_mode: str = "live",
    transport_mode: str = "loopback",
):
    """Resume two independent model residents from one exact pre-event state."""

    participant_session_id = "gym-afternoon-mara"
    participant_actor_id = "gym-afternoon-actor-mara"
    with (
        tempfile.TemporaryDirectory(prefix="worldweaver-gym-fork-") as raw_temp,
        _temporary_gym_node_configuration(),
    ):
        temp = Path(raw_temp)
        source_home = temp / "source-resident"
        source_package = temp / "resident-before.wwhearth"
        host_key = temp / "gym-host-transport.key"
        artifact = _agent_artifact_command(
            "create-fixture",
            "--home",
            str(source_home),
            "--package",
            str(source_package),
            "--host-key",
            str(host_key),
            "--actor-id",
            participant_actor_id,
            "--display-name",
            "Mara",
            "--world-id",
            "gym-long-afternoon-world",
            "--session-id",
            participant_session_id,
            "--model-id",
            model_id,
            "--started-at",
            "2026-07-20T12:00:00+00:00",
            "--return-at",
            "2026-07-22T12:00:00+00:00",
        )
        process_binding = artifact["process"]
        scheduled_return = artifact["scheduled_return"]
        descriptor = artifact["descriptor"]
        identity = artifact.get("identity")
        if not isinstance(identity, dict):
            raise RuntimeError("counterfactual fixture omitted resident identity proof")

        source = prepare_quiet_interval(
            db,
            mara_implementation="reference_resident_model",
            episode="The Forked Invitation",
        )
        source.bind_participant_artifacts(
            participant_session_id,
            adapter_id=process_binding["adapter"]["id"],
            adapter_version=process_binding["adapter"]["version"],
            model_id=process_binding["model"]["id"],
            private_state=descriptor,
        )
        source.schedule_resident_return(
            participant_session_id,
            resident_event_id=str(scheduled_return["event_id"]),
            activity_id=str(scheduled_return["activity_id"]),
            due_at=datetime.fromisoformat(str(scheduled_return["due_at"])),
        )
        audience = current_shard_id()
        certificate_result = _agent_artifact_command(
            "issue-runtime-certificate",
            "--home",
            str(source_home),
            "--host-key",
            str(host_key),
            "--audience",
            audience,
        )
        certificate = ResidentRuntimeCertificate.decode_header(
            str(certificate_result.get("certificate_header") or "").strip()
        )
        bind_resident_identity(
            db,
            actor_id=str(identity.get("actor_id") or ""),
            hearth_shard_id=str(identity.get("hearth_shard_id") or ""),
            identity_public_key=str(identity.get("identity_public_key") or ""),
            recovery_policy_version=int(identity.get("recovery_policy_version") or 0),
            admission_reason="synthetic counterfactual fixture",
            admitted_by="resident-gym",
        )
        activate_resident_generation(
            db, certificate=certificate, expected_audience=audience
        )
        bind_resident_session(
            db,
            session_id=participant_session_id,
            actor_id=participant_actor_id,
            runtime_generation=certificate.runtime_generation,
        )
        db.commit()

        inspection = source.offer_next_scheduled()[0]
        source.inspect_sublocation(
            parent_location=str(inspection.payload["parent_location"]),
            sublocation_id=str(inspection.payload["sublocation_id"]),
        )
        source.acknowledge_scheduled((inspection.event_id,))
        checkpoint = json.loads(json.dumps(source.checkpoint()))
        checkpoint_id = str(checkpoint.get("checkpoint_id") or "")
        private_artifact_id = str(descriptor.get("artifact_id") or "")
        common_records = list(checkpoint["gym"]["records"])
        if not checkpoint_id or not private_artifact_id:
            raise RuntimeError("counterfactual source checkpoint is incomplete")

        descriptor_path = temp / "descriptor.json"
        descriptor_path.write_text(json.dumps(descriptor), encoding="utf-8")
        branch_specs = (
            ("invitation", "exact_place_speech_present", True),
            ("quiet", "exact_place_speech_absent", False),
        )
        branches: list[GymCounterfactualBranch] = []

        for branch_id, condition, add_speech in branch_specs:
            home = temp / f"resident-{branch_id}"
            process_path = temp / f"process-{branch_id}.json"
            process_path.write_text(json.dumps(process_binding), encoding="utf-8")
            _agent_artifact_command(
                "restore-synthetic-fork",
                "--package",
                str(source_package),
                "--home",
                str(home),
                "--source-home",
                str(source_home),
                "--descriptor",
                str(descriptor_path),
                "--expected-process",
                str(process_path),
            )

            with _temporary_branch_database(temp / f"{branch_id}.sqlite3") as (
                branch_db,
                branch_session_factory,
            ):
                branch = ProductionRuleGym.from_checkpoint(
                    branch_db,
                    checkpoint,
                    record_observer=record_observer,
                )
                if add_speech:
                    branch.speak(
                        "gym-afternoon-ivo",
                        "The bridge group will meet beside the dry bench.",
                    )
                due_events = branch.offer_next_scheduled()
                if len(due_events) != 1 or due_events[0].kind != (
                    "resident_private_return"
                ):
                    raise RuntimeError("counterfactual fork did not reach one return")
                due = due_events[0]

                if transport_mode == "stdio":
                    transport_context = _temporary_gym_api(
                        branch_db, world_clock=branch.clock
                    )
                elif transport_mode == "loopback":
                    transport_context = _temporary_gym_loopback(
                        branch_db,
                        session_factory=branch_session_factory,
                        world_clock=branch.clock,
                        gym=branch,
                        participant_session_id=participant_session_id,
                    )
                else:
                    raise ValueError("unsupported counterfactual transport")

                with transport_context as transport_endpoint:
                    api_client = (
                        transport_endpoint
                        if isinstance(transport_endpoint, _GymAPIClient)
                        else None
                    )
                    base_url = (
                        "http://worldweaver-gym.local"
                        if api_client is not None
                        else str(transport_endpoint)
                    )
                    current_process = json.loads(
                        process_path.read_text(encoding="utf-8")
                    )

                    def handle_return(event, _scene):
                        return _model_adapter_command(
                            branch,
                            api_client=api_client,
                            home=home,
                            host_key=host_key,
                            process_path=process_path,
                            participant_session_id=participant_session_id,
                            protocol_session_id=str(
                                current_process["attachment"]["session_id"]
                            ),
                            now=event.due_at,
                            model_id=model_id,
                            model_mode=model_mode,
                            event_id=str(event.payload["resident_event_id"]),
                            transport_mode=transport_mode,
                            base_url=base_url,
                        )

                    activation = branch.deliver_resident_return(due, handle_return)
                    updated_process = activation.get("process")
                    if not isinstance(updated_process, dict):
                        raise RuntimeError(
                            "counterfactual resident omitted its process checkpoint"
                        )
                    process_path.write_text(
                        json.dumps(updated_process), encoding="utf-8"
                    )
                    attachment = updated_process.get("attachment")
                    if not isinstance(attachment, dict) or attachment.get(
                        "kind"
                    ) not in {"city", "hearth"}:
                        raise RuntimeError(
                            "counterfactual resident checkpointed an invalid attachment"
                        )
                    if attachment.get("kind") == "hearth":
                        hearth_result = _model_adapter_command(
                            branch,
                            api_client=api_client,
                            home=home,
                            host_key=host_key,
                            process_path=process_path,
                            participant_session_id=participant_session_id,
                            protocol_session_id=str(attachment["session_id"]),
                            now=branch.clock.now(),
                            model_id=model_id,
                            model_mode=model_mode,
                            command="observe-hearth-model",
                            transport_mode=transport_mode,
                            base_url=base_url,
                        )
                        updated_process = hearth_result.get("process")
                        if int(
                            hearth_result.get("model_call_count") or 0
                        ) != 0 or not isinstance(updated_process, dict):
                            raise RuntimeError(
                                "counterfactual hearth restart was not clean"
                            )
                        process_path.write_text(
                            json.dumps(updated_process), encoding="utf-8"
                        )

                    final_attachment = updated_process.get("attachment")
                    final_hosting = updated_process.get("hosting")
                    attachment_kind = (
                        str(final_attachment.get("kind") or "")
                        if isinstance(final_attachment, dict)
                        else ""
                    )
                    if (
                        attachment_kind not in {"city", "hearth"}
                        or not isinstance(final_hosting, dict)
                        or final_hosting.get("state") != "suspended"
                    ):
                        raise RuntimeError(
                            "counterfactual resident did not suspend cleanly"
                        )
                    active_sessions = (
                        branch_db.query(SessionVars)
                        .filter(SessionVars.actor_id == participant_actor_id)
                        .count()
                    )
                    expected_sessions = 0 if attachment_kind == "hearth" else 1
                    if active_sessions != expected_sessions:
                        raise RuntimeError(
                            "counterfactual resident attachment count is inconsistent"
                        )
                    branch.record_resident_attachment_verified(
                        participant_session_id,
                        attachment=attachment_kind,
                        process_hosting_state="suspended",
                        active_city_session_count=active_sessions,
                    )

                branch.acknowledge_scheduled((due.event_id,))
                finish_quiet_interval(branch)
                updated_descriptor = _agent_artifact_command(
                    "export",
                    "--home",
                    str(home),
                    "--package",
                    str(temp / f"resident-{branch_id}-after.wwhearth"),
                )
                branch.bind_participant_artifacts(
                    participant_session_id,
                    adapter_id=process_binding["adapter"]["id"],
                    adapter_version=process_binding["adapter"]["version"],
                    model_id=process_binding["model"]["id"],
                    private_state=updated_descriptor,
                )
                branch.audit_world_chronology()
                episode = branch.result()
                payload = episode.as_payload()
                if payload["records"][: len(common_records)] != common_records:
                    raise RuntimeError(
                        "counterfactual branch changed its common prefix"
                    )
                summary = summarize_episode(
                    payload,
                    run_id=branch_id,
                    duration_ms=0,
                    report_name=f"{branch_id}.html",
                )
                branches.append(
                    GymCounterfactualBranch(
                        branch_id=branch_id,
                        condition=condition,
                        summary=summary,
                        episode=episode,
                    )
                )

        return GymCounterfactualResult(
            episode="The Forked Invitation",
            source_checkpoint_id=checkpoint_id,
            private_artifact_id=private_artifact_id,
            common_record_count=len(common_records),
            controlled_variable="one exact-place public utterance before the due return",
            branches=tuple(branches),
        )


def _run_willow_week(
    db,
    *,
    session_factory=None,
    record_observer=None,
    model_id: str,
    model_mode: str = "live",
    transport_mode: str = "stdio",
):
    """Run one resident through six legitimate host intervals over seven days."""

    started_at = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)
    week_end = started_at + timedelta(days=7)
    participant_session_id = "gym-week-mara"
    participant_actor_id = "gym-week-actor-mara"
    with (
        tempfile.TemporaryDirectory(prefix="worldweaver-gym-week-") as raw_temp,
        _temporary_gym_node_configuration(),
    ):
        temp = Path(raw_temp)
        source_home = temp / "source-resident"
        source_package = temp / "resident-before.wwhearth"
        host_key = temp / "gym-host-transport.key"
        artifact = _agent_artifact_command(
            "create-fixture",
            "--home",
            str(source_home),
            "--package",
            str(source_package),
            "--host-key",
            str(host_key),
            "--actor-id",
            participant_actor_id,
            "--display-name",
            "Mara",
            "--world-id",
            "gym-willow-week-world",
            "--session-id",
            participant_session_id,
            "--model-id",
            model_id,
            "--started-at",
            started_at.isoformat(),
            "--return-at",
            (started_at + timedelta(days=2)).isoformat(),
        )
        process_binding = artifact["process"]
        scheduled_return = artifact["scheduled_return"]
        identity = artifact.get("identity")
        if not isinstance(identity, dict):
            raise RuntimeError("Willow Week fixture omitted resident identity proof")
        process_path = temp / "process.json"
        process_path.write_text(json.dumps(process_binding), encoding="utf-8")

        gym = ProductionRuleGym(
            db,
            episode="Willow Week",
            world_id="gym-willow-week-world",
            clock=ControlledClock(started_at),
            scenario_id="willow-week",
            scenario_version=1,
            scenario_seed=0,
            record_observer=record_observer,
        )
        gym.arrange_world(("Willow Court", "Footbridge", "Market Hall"))
        gym.join(
            GymParticipant(
                session_id=participant_session_id,
                actor_id=participant_actor_id,
                display_name="Mara",
                implementation="reference_resident_model",
            ),
            location="Willow Court",
        )
        gym.join(
            GymParticipant(
                session_id="gym-week-ivo",
                actor_id="gym-week-actor-ivo",
                display_name="Ivo",
                implementation="scripted_actor",
            ),
            location="Willow Court",
        )
        gym.bind_participant_artifacts(
            participant_session_id,
            adapter_id=process_binding["adapter"]["id"],
            adapter_version=process_binding["adapter"]["version"],
            model_id=process_binding["model"]["id"],
            private_state=artifact["descriptor"],
        )
        audience = current_shard_id()
        certificate_result = _agent_artifact_command(
            "issue-runtime-certificate",
            "--home",
            str(source_home),
            "--host-key",
            str(host_key),
            "--audience",
            audience,
        )
        certificate = ResidentRuntimeCertificate.decode_header(
            str(certificate_result.get("certificate_header") or "").strip()
        )
        bind_resident_identity(
            db,
            actor_id=str(identity.get("actor_id") or ""),
            hearth_shard_id=str(identity.get("hearth_shard_id") or ""),
            identity_public_key=str(identity.get("identity_public_key") or ""),
            recovery_policy_version=int(identity.get("recovery_policy_version") or 0),
            admission_reason="synthetic Willow Week fixture",
            admitted_by="resident-gym",
        )
        activate_resident_generation(
            db, certificate=certificate, expected_audience=audience
        )
        bind_resident_session(
            db,
            session_id=participant_session_id,
            actor_id=participant_actor_id,
            runtime_generation=certificate.runtime_generation,
        )
        db.commit()

        gym.speak("gym-week-ivo", "The bridge group meets after the rain.")
        for step, elapsed_days in ((0, 0), (1, 1), (3, 3), (4, 5), (5, 7)):
            gym.schedule_in(
                timedelta(days=elapsed_days),
                kind="resident_host_tick",
                payload={"session_id": participant_session_id, "step": step},
            )
        gym.schedule_resident_return(
            participant_session_id,
            resident_event_id=str(scheduled_return["event_id"]),
            activity_id=str(scheduled_return["activity_id"]),
            due_at=datetime.fromisoformat(str(scheduled_return["due_at"])),
        )

        if transport_mode == "stdio":
            transport_context = _temporary_gym_api(db, world_clock=gym.clock)
        elif transport_mode == "loopback":
            if session_factory is None:
                raise RuntimeError(
                    "loopback transport requires a database session factory"
                )
            transport_context = _temporary_gym_loopback(
                db,
                session_factory=session_factory,
                world_clock=gym.clock,
                gym=gym,
                participant_session_id=participant_session_id,
            )
        else:
            raise ValueError("unsupported Willow Week transport")

        def align_ivo_with_mara() -> None:
            if not gym.has_city_presence(participant_session_id):
                return
            location = gym.participant_location(participant_session_id)
            if gym.participant_location("gym-week-ivo") != location:
                gym.move("gym-week-ivo", location)

        def arrange_step(step: int) -> None:
            if step in {1, 4}:
                gym.send_letter(
                    "gym-week-ivo",
                    participant_actor_id,
                    (
                        "The bridge meeting moved to Thursday."
                        if step == 1
                        else "The rain changed the path back to Willow Court."
                    ),
                )
            if not gym.has_city_presence(participant_session_id):
                return
            if step == 3:
                mara_location = gym.participant_location(participant_session_id)
                away = (
                    "Willow Court" if mara_location != "Willow Court" else "Market Hall"
                )
                if gym.participant_location("gym-week-ivo") != away:
                    gym.move("gym-week-ivo", away)
                gym.speak("gym-week-ivo", "This first call is deliberately elsewhere.")
            align_ivo_with_mara()
            gym.speak(
                "gym-week-ivo",
                {
                    1: "I sent the changed meeting time.",
                    2: "The dry place is still here.",
                    3: "Now we are speaking in the same place.",
                    4: "The route back is clear.",
                    5: "The week can close here.",
                }.get(step, "The week begins at Willow Court."),
            )

        with transport_context as transport_endpoint:
            api_client = (
                transport_endpoint
                if isinstance(transport_endpoint, _GymAPIClient)
                else None
            )
            base_url = (
                "http://worldweaver-gym.local"
                if api_client is not None
                else str(transport_endpoint)
            )

            def invoke(event, *, command: str, step: int) -> dict:
                process = json.loads(process_path.read_text(encoding="utf-8"))
                attachment = process.get("attachment")
                if not isinstance(attachment, dict):
                    raise RuntimeError("Willow Week process omitted its attachment")
                result = _model_adapter_command(
                    gym,
                    api_client=api_client,
                    home=source_home,
                    host_key=host_key,
                    process_path=process_path,
                    participant_session_id=participant_session_id,
                    protocol_session_id=str(attachment.get("session_id") or ""),
                    now=event.due_at,
                    model_id=model_id,
                    model_mode=model_mode,
                    command=command,
                    event_id=(
                        str(event.payload["resident_event_id"])
                        if command == "handle-return-model"
                        else event.event_id
                    ),
                    scenario_step=step,
                    transport_mode=transport_mode,
                    base_url=base_url,
                )
                updated = result.get("process")
                if not isinstance(updated, dict):
                    raise RuntimeError("Willow Week activation omitted its process")
                process_path.write_text(json.dumps(updated), encoding="utf-8")
                return result

            while gym.scheduled_checkpoint()["pending"]:
                for event in gym.offer_next_scheduled():
                    if not gym.has_scheduled_event(event.event_id):
                        continue
                    should_reconcile_return = False
                    current_scheduled_return = None
                    if event.kind == "resident_private_return":
                        arrange_step(2)
                        result = gym.deliver_resident_return(
                            event,
                            lambda offered, _scene: invoke(
                                offered, command="handle-return-model", step=2
                            ),
                        )
                        should_reconcile_return = True
                        current_scheduled_return = result.get("scheduled_return")
                    elif event.kind == "resident_host_tick":
                        step = int(event.payload.get("step") or 0)
                        arrange_step(step)
                        if gym.has_city_presence(participant_session_id):
                            result = gym.deliver_resident_tick(
                                event,
                                lambda offered, _scene, step=step: invoke(
                                    offered, command="run-tick-model", step=step
                                ),
                            )
                            should_reconcile_return = True
                            current_scheduled_return = result.get("scheduled_return")
                        else:
                            gym.skip_resident_tick(event, reason="resident_at_hearth")
                    else:
                        raise RuntimeError("Willow Week scheduled an unknown event")
                    gym.acknowledge_scheduled((event.event_id,))
                    if should_reconcile_return:
                        gym.reconcile_resident_return(
                            participant_session_id,
                            (
                                current_scheduled_return
                                if isinstance(current_scheduled_return, dict)
                                else None
                            ),
                            not_after=week_end,
                        )

            final_process = json.loads(process_path.read_text(encoding="utf-8"))
            final_attachment = final_process.get("attachment")
            if not isinstance(final_attachment, dict):
                raise RuntimeError("Willow Week final attachment is invalid")
            attachment_kind = str(final_attachment.get("kind") or "")
            if attachment_kind == "hearth":
                hearth_result = _model_adapter_command(
                    gym,
                    api_client=api_client,
                    home=source_home,
                    host_key=host_key,
                    process_path=process_path,
                    participant_session_id=participant_session_id,
                    protocol_session_id=str(final_attachment.get("session_id") or ""),
                    now=gym.clock.now(),
                    model_id=model_id,
                    model_mode=model_mode,
                    command="observe-hearth-model",
                    scenario_step=6,
                    transport_mode=transport_mode,
                    base_url=base_url,
                )
                if int(hearth_result.get("model_call_count") or 0) != 0:
                    raise RuntimeError("Willow Week hearth restart called the model")
                final_process = hearth_result["process"]
                process_path.write_text(json.dumps(final_process), encoding="utf-8")
            elif attachment_kind != "city":
                raise RuntimeError("Willow Week stopped at an invalid attachment")

            active_city_sessions = (
                db.query(SessionVars)
                .filter(SessionVars.actor_id == participant_actor_id)
                .count()
            )
            expected_sessions = 0 if attachment_kind == "hearth" else 1
            if active_city_sessions != expected_sessions:
                raise RuntimeError("Willow Week city attachment count is inconsistent")
            gym.record_resident_attachment_verified(
                participant_session_id,
                attachment=attachment_kind,
                process_hosting_state="suspended",
                active_city_session_count=active_city_sessions,
            )

        updated_descriptor = _agent_artifact_command(
            "export",
            "--home",
            str(source_home),
            "--package",
            str(temp / "resident-after.wwhearth"),
        )
        gym.bind_participant_artifacts(
            participant_session_id,
            adapter_id=process_binding["adapter"]["id"],
            adapter_version=process_binding["adapter"]["version"],
            model_id=process_binding["model"]["id"],
            private_state=updated_descriptor,
        )
        gym.audit_world_chronology()
        return gym.result()


def _run_material_day(
    db,
    *,
    session_factory=None,
    record_observer=None,
    transport_mode: str = "stdio",
):
    """Exercise material life through one normal resident and canonical receipts."""

    started_at = datetime(2026, 7, 21, 9, 0, tzinfo=timezone.utc)
    mara_session = "gym-material-mara"
    mara_actor = "gym-material-actor-mara"
    ivo_session = "gym-material-ivo"
    ivo_actor = "gym-material-actor-ivo"
    model_id = "test/material-command-v1"
    if session_factory is None:
        raise RuntimeError("material-day requires a request-scoped session factory")
    with tempfile.TemporaryDirectory(prefix="worldweaver-gym-material-") as raw_temp:
        temp = Path(raw_temp)
        declaration = json.loads(
            (ENGINE_ROOT / "data/rulesets/private_constructive_game.v1.example.json")
            .read_text(encoding="utf-8")
            .replace("Alderbank Workshop", "Commons Worktable")
        )
        declaration_path = temp / "material-shard-experience.json"
        declaration_path.write_text(
            json.dumps(declaration, sort_keys=True), encoding="utf-8"
        )
        with _temporary_gym_node_configuration(shard_experience_path=declaration_path):
            source_home = temp / "mara"
            source_package = temp / "mara-before.wwhearth"
            host_key = temp / "mara-host.key"
            artifact = _agent_artifact_command(
                "create-fixture",
                "--home",
                str(source_home),
                "--package",
                str(source_package),
                "--host-key",
                str(host_key),
                "--actor-id",
                mara_actor,
                "--display-name",
                "Mara",
                "--world-id",
                "gym-material-world",
                "--session-id",
                mara_session,
                "--model-id",
                model_id,
                "--started-at",
                started_at.isoformat(),
                "--return-at",
                (started_at + timedelta(days=30)).isoformat(),
            )
            process_binding = artifact["process"]
            process_path = temp / "process.json"
            process_path.write_text(json.dumps(process_binding), encoding="utf-8")

            # This is a private hearth gift, deliberately distinct from an
            # object given in the shard. It becomes visible only after Mara goes home.
            source_home.joinpath("hearth.json").write_text(
                json.dumps({"gifts": True}), encoding="utf-8"
            )
            given_dir = source_home / "workshop" / "given"
            given_dir.mkdir(parents=True, exist_ok=True)
            given_dir.joinpath("worktable-note.txt").write_text(
                "A private note carried into the hearth after the material exercise.\n",
                encoding="utf-8",
            )
            source_home.joinpath("given.jsonl").write_text(
                json.dumps(
                    {
                        "ts": started_at.isoformat(),
                        "file": "worktable-note.txt",
                        "note": "A private gift waiting at home.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            gym = ProductionRuleGym(
                db,
                episode="The Commons Worktable",
                world_id="gym-material-world",
                clock=ControlledClock(started_at),
                scenario_id="material-day",
                scenario_version=1,
                scenario_seed=0,
                record_observer=record_observer,
            )
            gym.arrange_world(("Commons Worktable", "Garden Studio", "Lantern Square"))
            gym.join(
                GymParticipant(
                    session_id=mara_session,
                    actor_id=mara_actor,
                    display_name="Mara",
                    implementation="reference_resident_model",
                ),
                location="Commons Worktable",
            )
            gym.join(
                GymParticipant(
                    session_id=ivo_session,
                    actor_id=ivo_actor,
                    display_name="Ivo",
                    implementation="scripted_actor",
                ),
                location="Commons Worktable",
            )
            gym.bind_participant_artifacts(
                mara_session,
                adapter_id=process_binding["adapter"]["id"],
                adapter_version=process_binding["adapter"]["version"],
                model_id=process_binding["model"]["id"],
                private_state=artifact["descriptor"],
            )
            identity = artifact.get("identity")
            if not isinstance(identity, dict):
                raise RuntimeError("material fixture omitted resident identity proof")
            audience = current_shard_id()
            certificate_result = _agent_artifact_command(
                "issue-runtime-certificate",
                "--home",
                str(source_home),
                "--host-key",
                str(host_key),
                "--audience",
                audience,
            )
            certificate = ResidentRuntimeCertificate.decode_header(
                str(certificate_result.get("certificate_header") or "").strip()
            )
            bind_resident_identity(
                db,
                actor_id=str(identity.get("actor_id") or ""),
                hearth_shard_id=str(identity.get("hearth_shard_id") or ""),
                identity_public_key=str(identity.get("identity_public_key") or ""),
                recovery_policy_version=int(
                    identity.get("recovery_policy_version") or 0
                ),
                admission_reason="synthetic material-day fixture",
                admitted_by="resident-gym",
            )
            activate_resident_generation(
                db, certificate=certificate, expected_audience=audience
            )
            bind_resident_session(
                db,
                session_id=mara_session,
                actor_id=mara_actor,
                runtime_generation=certificate.runtime_generation,
            )
            db.commit()

            initialize_material_pools(db, now=gym.clock.now())
            ivo_token_id = found_durable_object(
                db,
                session_id=ivo_session,
                idempotency_key="material-seed-ivo-token",
                name="Ivo's ash token",
                description="A smooth ash token seeded for one exact exchange.",
                object_kind="wooden_token",
                provenance_ref="resident-gym:material-day:ivo-token",
                now=gym.clock.now(),
            ).object["object_id"]
            found_world_stoop(
                db,
                stoop_id="lantern-stoop",
                title="The Lantern Stoop",
                prompt="Leave one thing only by choosing to let a visitor take it.",
                location="Commons Worktable",
                capacity=3,
            )
            found_space_policy(
                db,
                location="Garden Studio",
                controller_actor_id=ivo_actor,
                mode="requestable",
                note="Entry is decided one request at a time.",
            )
            db.commit()

            if transport_mode == "stdio":
                transport_context = _temporary_gym_api(db, world_clock=gym.clock)
            elif transport_mode == "loopback":
                if session_factory is None:
                    raise RuntimeError(
                        "loopback transport requires a database session factory"
                    )
                transport_context = _temporary_gym_loopback(
                    db,
                    session_factory=session_factory,
                    world_clock=gym.clock,
                    gym=gym,
                    participant_session_id=mara_session,
                )
            else:
                raise ValueError("unsupported material-day transport")

            with transport_context as transport_endpoint:
                api_client = (
                    transport_endpoint
                    if isinstance(transport_endpoint, _GymAPIClient)
                    else None
                )
                base_url = (
                    "http://worldweaver-gym.local"
                    if api_client is not None
                    else str(transport_endpoint)
                )
                minute = 0

                def activate(
                    *,
                    source: str = "",
                    query: str = "",
                    target: str = "",
                    action_kind: str = "do",
                    expected_failure: bool = False,
                ) -> dict | None:
                    nonlocal minute
                    refusal_count_before = sum(
                        record.kind == "participant_access_refused"
                        for record in gym.result().records
                    )
                    location_before = gym.participant_location(mara_session)
                    minute += 1
                    event = gym.schedule_in(
                        timedelta(minutes=minute),
                        kind="resident_host_tick",
                        payload={"session_id": mara_session, "step": minute},
                    )
                    offered = gym.offer_next_scheduled()
                    if offered != (event,):
                        raise RuntimeError("material command scheduler drifted")

                    def invoke(_event, _scene):
                        process = json.loads(process_path.read_text(encoding="utf-8"))
                        attachment = process.get("attachment")
                        if not isinstance(attachment, dict):
                            raise RuntimeError(
                                "material process omitted its attachment"
                            )
                        result = _model_adapter_command(
                            gym,
                            api_client=api_client,
                            home=source_home,
                            host_key=host_key,
                            process_path=process_path,
                            participant_session_id=mara_session,
                            protocol_session_id=str(
                                attachment.get("session_id") or mara_session
                            ),
                            now=event.due_at,
                            model_id=model_id,
                            model_mode="scripted-gym-command",
                            command="run-tick-model",
                            event_id=event.event_id,
                            scenario_step=minute,
                            transport_mode=transport_mode,
                            base_url=base_url,
                            scripted_source=source,
                            scripted_query=query,
                            scripted_target=target,
                            scripted_action_kind=action_kind,
                        )
                        updated = result.get("process")
                        if not isinstance(updated, dict):
                            raise RuntimeError(
                                "material activation omitted its process"
                            )
                        process_path.write_text(json.dumps(updated), encoding="utf-8")
                        return result

                    try:
                        result = gym.deliver_resident_tick(event, invoke)
                    except RuntimeError:
                        if not expected_failure:
                            raise
                        result = None
                    finally:
                        gym.acknowledge_scheduled((event.event_id,))
                    if expected_failure:
                        refusal_count_after = sum(
                            record.kind == "participant_access_refused"
                            for record in gym.result().records
                        )
                        if (
                            refusal_count_after != refusal_count_before + 1
                            or gym.participant_location(mara_session) != location_before
                        ):
                            raise RuntimeError(
                                "expected material command refusal did not hold"
                            )
                    return result

                for source, query in (
                    ("making", ""),
                    ("objects", ""),
                    ("exchanges", ""),
                    ("access", "Garden Studio"),
                    ("stoops", ""),
                ):
                    activate(source=source, query=query)

                activate(target="recipe:small_clay_cup")
                activate(target="recipe:wooden_token")
                db.expire_all()
                mara_objects = {
                    str(row.name): str(row.object_id)
                    for row in db.query(DurableObject)
                    .filter(DurableObject.created_by_actor_id == mara_actor)
                    .all()
                }
                mara_cup_id = mara_objects["Small clay cup"]
                mara_token_id = mara_objects["Wooden token"]

                activate(target=f"object-give:{mara_cup_id}:{ivo_session}")
                activate(
                    target=(
                        f"exchange-offer:{ivo_session}:{mara_token_id}:{ivo_token_id}"
                    )
                )
                db.expire_all()
                exchange_id = str(db.query(ObjectExchange).one().exchange_id)
                accept_object_exchange(
                    db,
                    session_id=ivo_session,
                    exchange_id=exchange_id,
                    idempotency_key="material-ivo-accept",
                    now=gym.clock.now(),
                )
                db.commit()

                activate(target=f"stoop-leave:lantern-stoop:{ivo_token_id}")
                db.expire_all()
                entry_id = str(db.query(StoopObjectEntry).one().entry_id)
                take_stoop_object(
                    db,
                    session_id=ivo_session,
                    entry_id=entry_id,
                    idempotency_key="material-ivo-stoop-take",
                    now=gym.clock.now(),
                )
                db.commit()

                activate(target="access-request:Garden Studio")
                db.expire_all()
                request_id = str(db.query(SpaceAccessRequest).one().request_id)
                resolve_access_request(
                    db,
                    session_id=ivo_session,
                    request_id=request_id,
                    decision="denied",
                    idempotency_key="material-ivo-deny",
                    now=gym.clock.now(),
                )
                db.commit()
                activate(
                    target="Garden Studio",
                    action_kind="move",
                    expected_failure=True,
                )

                gym.audit_material_capabilities()
                activate(target="home", action_kind="move")
                final_process = json.loads(process_path.read_text(encoding="utf-8"))
                final_attachment = final_process.get("attachment")
                final_hosting = final_process.get("hosting")
                if not isinstance(final_attachment, dict) or not isinstance(
                    final_hosting, dict
                ):
                    raise RuntimeError("material process final checkpoint is invalid")

                hearth_result = _model_adapter_command(
                    gym,
                    api_client=api_client,
                    home=source_home,
                    host_key=host_key,
                    process_path=process_path,
                    participant_session_id=mara_session,
                    protocol_session_id=mara_session,
                    now=gym.clock.now(),
                    model_id=model_id,
                    model_mode="scripted-gym-command",
                    command="observe-hearth-model",
                    transport_mode=transport_mode,
                    base_url=base_url,
                    scripted_source="gifts",
                )
                if int(hearth_result.get("model_call_count") or 0) != 0:
                    raise RuntimeError("final hearth observation called the model")
                hearth_observation = next(
                    (
                        record
                        for record in reversed(gym.result().records)
                        if record.kind == "resident_hearth_observed"
                    ),
                    None,
                )
                if hearth_observation is None or "gifts" not in set(
                    hearth_observation.detail.get("source_names") or []
                ):
                    raise RuntimeError("hearth gift capability was not attached")
                active_sessions = (
                    db.query(SessionVars)
                    .filter(SessionVars.session_id == mara_session)
                    .count()
                )
                gym.record_resident_attachment_verified(
                    mara_session,
                    attachment=str(final_attachment.get("kind") or ""),
                    process_hosting_state=str(final_hosting.get("state") or ""),
                    active_city_session_count=active_sessions,
                )

            updated_descriptor = _agent_artifact_command(
                "export",
                "--home",
                str(source_home),
                "--package",
                str(temp / "mara-after.wwhearth"),
            )
            gym.bind_participant_artifacts(
                mara_session,
                adapter_id=process_binding["adapter"]["id"],
                adapter_version=process_binding["adapter"]["version"],
                model_id=process_binding["model"]["id"],
                private_state=updated_descriptor,
            )
            gym.audit_world_chronology()
            return gym.result()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a deterministic production-rule resident gym episode."
    )
    parser.add_argument(
        "--episode",
        choices=(
            "footbridge",
            "waiting-letter",
            "quiet-interval",
            "resident-return",
            "resident-model",
            "willow-fork",
            "willow-week",
            "material-day",
        ),
        default="footbridge",
        help="episode to run (default: footbridge)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="self-contained HTML result (default: .runs/gym/<episode>.html)",
    )
    parser.add_argument(
        "--failure-output", type=Path, default=None, help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the structural episode JSON instead of the terminal view",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="print the old complete terminal report after the episode finishes",
    )
    parser.add_argument(
        "--model",
        default="",
        help="model ID for --episode resident-model (default: WW_INFERENCE_MODEL)",
    )
    parser.add_argument(
        "--model-mode",
        choices=("live", "scripted-read-home", "scripted-read-move", "scripted-week"),
        default="live",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--transport-mode",
        choices=("stdio", "loopback"),
        default="stdio",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--transport-fault",
        choices=(
            "",
            "child_exit",
            "malformed_json",
            "malformed_message",
            "replayed_request",
            "malformed_response",
        ),
        default="",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--departure-fault",
        choices=(
            "",
            "before_request",
            "before_commit",
            "response_loss",
            "after_hearth_checkpoint",
        ),
        default="",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    _state_managers.clear()
    _session_locks.clear()
    database_directory = tempfile.TemporaryDirectory(prefix="worldweaver-gym-db-")
    database_path = Path(database_directory.name) / "gym.sqlite3"
    engine = create_engine(
        f"sqlite+pysqlite:///{database_path}",
        connect_args={"check_same_thread": False},
    )
    sqlalchemy_event.listen(engine, "connect", configure_sqlite_connection)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    sqlalchemy_event.listen(
        session_factory, "before_flush", _require_explicit_session_time
    )
    stream = not args.json and not args.no_stream and args.episode != "willow-fork"
    episode_titles = {
        "footbridge": "The Footbridge Hello",
        "waiting-letter": "The Waiting Letter",
        "quiet-interval": "The Long Afternoon",
        "resident-return": "The Kept Appointment",
        "resident-model": "The Model Appointment",
        "willow-fork": "The Forked Invitation",
        "willow-week": "Willow Week",
        "material-day": "The Commons Worktable",
    }
    if stream:
        print(render_terminal_stream_header(episode_titles[args.episode]), flush=True)

    def show_record(record):
        print(render_terminal_record(record), flush=True)

    try:
        with session_factory() as db:
            runners = {
                "footbridge": run_first_conversation,
                "waiting-letter": run_waiting_letter,
                "quiet-interval": run_quiet_interval,
                "resident-return": _run_scripted_resident_return,
            }
            if args.episode == "material-day":
                if args.departure_fault or args.transport_fault:
                    parser.error("The Commons Worktable does not accept fault modes")
                result = _run_material_day(
                    db,
                    session_factory=session_factory,
                    record_observer=show_record if stream else None,
                    transport_mode=args.transport_mode,
                )
            elif args.episode in {"resident-model", "willow-fork", "willow-week"}:
                model_id = str(
                    args.model or os.environ.get("WW_INFERENCE_MODEL", "")
                ).strip()
                if not model_id:
                    parser.error(
                        "model-backed episodes require --model or WW_INFERENCE_MODEL"
                    )
                if args.episode == "willow-week":
                    if args.departure_fault or args.transport_fault:
                        parser.error("Willow Week does not accept fault modes")
                    result = _run_willow_week(
                        db,
                        session_factory=session_factory,
                        record_observer=show_record if stream else None,
                        model_id=model_id,
                        model_mode=args.model_mode,
                        transport_mode=args.transport_mode,
                    )
                elif args.episode == "willow-fork":
                    if args.departure_fault or args.transport_fault:
                        parser.error(
                            "The Forked Invitation does not accept fault modes"
                        )
                    result = _run_counterfactual_model_fork(
                        db,
                        record_observer=None,
                        model_id=model_id,
                        model_mode=args.model_mode,
                        transport_mode=args.transport_mode,
                    )
                else:
                    result = _run_model_resident_return(
                        db,
                        session_factory=session_factory,
                        record_observer=show_record if stream else None,
                        model_id=model_id,
                        model_mode=args.model_mode,
                        departure_fault=args.departure_fault,
                        transport_fault=args.transport_fault,
                        transport_mode=args.transport_mode,
                    )
            else:
                result = runners[args.episode](
                    db,
                    record_observer=show_record if stream else None,
                )
        default_names = {
            "footbridge": "footbridge-hello.html",
            "waiting-letter": "waiting-letter.html",
            "quiet-interval": "long-afternoon.html",
            "resident-return": "kept-appointment.html",
            "resident-model": "model-appointment.html",
            "willow-fork": "forked-invitation.html",
            "willow-week": "willow-week.html",
            "material-day": "commons-worktable.html",
        }
        default_name = default_names[args.episode]
        output = (
            (args.output or WORKSPACE_ROOT / ".runs" / "gym" / default_name)
            .expanduser()
            .resolve()
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            (
                render_counterfactual_html(result)
                if isinstance(result, GymCounterfactualResult)
                else render_html(result)
            ),
            encoding="utf-8",
        )
        if args.json:
            print(json.dumps(result.as_payload(), indent=2, ensure_ascii=False))
        elif stream:
            print(render_terminal_stream_footer(result), flush=True)
        elif isinstance(result, GymCounterfactualResult):
            print(render_counterfactual_terminal(result))
        else:
            print(render_terminal(result))
        print(f"Visual episode: {output}")
    except Exception as exc:
        _write_failure_envelope(
            args.failure_output,
            episode=args.episode,
            exc=exc,
        )
        raise
    finally:
        engine.dispose()
        database_directory.cleanup()
        _state_managers.clear()
        _session_locks.clear()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
