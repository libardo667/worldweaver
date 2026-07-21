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
from datetime import datetime
from pathlib import Path

import httpx
from sqlalchemy import create_engine, event as sqlalchemy_event
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
from src.database import Base, get_db  # noqa: E402
from src.models import ResidentSessionRetirementReceipt, SessionVars  # noqa: E402
from src.services.clock import Clock, get_world_clock  # noqa: E402
from src.services.gym_presentation import (  # noqa: E402
    render_html,
    render_terminal,
    render_terminal_record,
    render_terminal_stream_footer,
    render_terminal_stream_header,
)
from src.services.resident_gym import (  # noqa: E402
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

        async def observe_send(message) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status") or 500)
            elif message.get("type") == "http.response.body":
                response_parts.append(bytes(message.get("body") or b""))
            await send(message)

        await app(scope, receive, observe_send)
        raw_path = scope.get("raw_path") or str(scope.get("path") or "").encode("ascii")
        raw_query = scope.get("query_string") or b""
        target = bytes(raw_path).decode("ascii")
        if raw_query:
            target = f"{target}?{bytes(raw_query).decode('ascii')}"
        headers = {
            bytes(key).decode("latin1").lower(): bytes(value).decode("latin1")
            for key, value in scope.get("headers") or []
        }
        try:
            response_payload = json.loads(b"".join(response_parts))
        except (json.JSONDecodeError, UnicodeDecodeError):
            response_payload = None
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


@contextmanager
def _temporary_gym_loopback(
    db,
    *,
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
    with _temporary_gym_dependencies(db, world_clock=world_clock):
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
def _temporary_gym_node_configuration():
    """Publish a synthetic commons identity through ordinary node settings."""

    previous = {
        "city_id": settings.city_id,
        "shard_id": settings.shard_id,
        "shard_type": settings.shard_type,
        "shard_experience_path": settings.shard_experience_path,
    }
    settings.city_id = "resident_gym"
    settings.shard_id = "resident-gym"
    settings.shard_type = "city"
    settings.shard_experience_path = None
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
    departure_fault: str = "",
    transport_fault: str = "",
    transport_mode: str = "stdio",
    base_url: str = "http://worldweaver-gym.local",
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
        "--transport-fault",
        transport_fault,
        "--transport-mode",
        transport_mode,
        "--base-url",
        base_url,
    ]
    if event_id:
        arguments.extend(("--event-id", event_id))
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
            transport_context = _temporary_gym_loopback(
                db,
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
        choices=("live", "scripted-read-home", "scripted-read-move"),
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
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    stream = not args.json and not args.no_stream
    episode_titles = {
        "footbridge": "The Footbridge Hello",
        "waiting-letter": "The Waiting Letter",
        "quiet-interval": "The Long Afternoon",
        "resident-return": "The Kept Appointment",
        "resident-model": "The Model Appointment",
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
            if args.episode == "resident-model":
                model_id = str(
                    args.model or os.environ.get("WW_INFERENCE_MODEL", "")
                ).strip()
                if not model_id:
                    parser.error(
                        "--episode resident-model requires --model or WW_INFERENCE_MODEL"
                    )
                result = _run_model_resident_return(
                    db,
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
        }
        default_name = default_names[args.episode]
        output = (
            (args.output or WORKSPACE_ROOT / ".runs" / "gym" / default_name)
            .expanduser()
            .resolve()
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_html(result), encoding="utf-8")
        if args.json:
            print(json.dumps(result.as_payload(), indent=2, ensure_ascii=False))
        elif stream:
            print(render_terminal_stream_footer(result), flush=True)
        else:
            print(render_terminal(result))
        print(f"Visual episode: {output}")
    finally:
        engine.dispose()
        _state_managers.clear()
        _session_locks.clear()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
