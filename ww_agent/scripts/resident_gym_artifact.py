#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Create or restore a synthetic resident artifact for cross-process gym tests."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
import httpx

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from src.identity.hearth_manifest import initialize_hearth_manifest  # noqa: E402
from src.identity.hearth_activation import initialize_hearth_activation  # noqa: E402
from src.identity.hearth_package import export_hearth_package  # noqa: E402
from src.identity.resident_identity_custody import (  # noqa: E402
    initialize_resident_identity_custody,
)
from src.identity.resident_identity import (  # noqa: E402
    load_resident_identity_descriptor,
)
from src.identity.resident_key_seal import (  # noqa: E402
    SEALED_RESIDENT_IDENTITY_FILENAME,
)
from src.inference.client import InferenceClient  # noqa: E402
from src.identity.loader import LoopTuning, ResidentIdentity  # noqa: E402
from src.resident import Resident  # noqa: E402
from src.familiar.local_world import LocalWorld  # noqa: E402
from src.runtime.ledger import (  # noqa: E402
    append_runtime_event,
    load_resident_process_envelope,
)
from src.runtime.private_artifact import (  # noqa: E402
    PrivateArtifactError,
    describe_private_artifact,
    restore_private_artifact,
)
from src.runtime.process_state import ResidentProcessBinding  # noqa: E402
from src.runtime.reference_core import (  # noqa: E402
    ReferenceResidentCore,
    ReferenceScheduledReturn,
    build_reference_scheduled_return,
)
from src.world.client import (  # noqa: E402
    SceneData,
    WorldWeaverClient,
    scene_data_from_payload,
)
from src.world.resident_signing import signer_from_host_sealed_identity  # noqa: E402
from src.runtime.world_clock import FixedWorldClock  # noqa: E402

_SYNTHETIC_PRIVATE_ACTIVITY = (
    "Privately compare the synthetic blue and green route notes."
)
_SYNTHETIC_ACTIVITY_ID = "activity-synthetic-route-notes"


def _read_object(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PrivateArtifactError(f"could not read JSON input: {path}") from exc
    if not isinstance(raw, dict):
        raise PrivateArtifactError(f"JSON input must be an object: {path}")
    return raw


def _create_fixture(args: argparse.Namespace) -> dict:
    home = args.home.resolve()
    package = args.package.resolve()
    if home.exists() or home.is_symlink():
        raise PrivateArtifactError("synthetic resident home already exists")
    if package.exists() or package.is_symlink():
        raise PrivateArtifactError("synthetic resident package already exists")
    home.joinpath("identity").mkdir(parents=True)
    home.joinpath("memory").mkdir()
    home.joinpath("workshop").mkdir()
    home.joinpath("identity", "resident_id.txt").write_text(
        f"{args.actor_id}\n", encoding="utf-8"
    )
    display_name = str(args.display_name or "Synthetic Gym Resident").strip()
    canonical_soul = (
        f"Your name is {display_name}. You are a synthetic gym participant.\n"
    )
    home.joinpath("identity", "display_name.txt").write_text(
        f"{display_name}\n", encoding="utf-8"
    )
    home.joinpath("identity", "SOUL.canonical.md").write_text(
        canonical_soul, encoding="utf-8"
    )
    home.joinpath("identity", "SOUL.md").write_text(canonical_soul, encoding="utf-8")
    home.joinpath("session_id.txt").write_text(f"{args.session_id}\n", encoding="utf-8")
    manifest = initialize_hearth_manifest(home)
    identity_descriptor = None
    if args.host_key is not None:
        host_key_path = args.host_key.resolve()
        if host_key_path.exists() or host_key_path.is_symlink():
            raise PrivateArtifactError("synthetic host key already exists")
        host_key_path.parent.mkdir(parents=True, exist_ok=True)
        host_private_key = X25519PrivateKey.generate()
        encoded_host_key = (
            base64.urlsafe_b64encode(host_private_key.private_bytes_raw())
            .decode("ascii")
            .rstrip("=")
        )
        host_key_path.write_text(f"{encoded_host_key}\n", encoding="utf-8")
        host_key_path.chmod(0o600)
        identity_descriptor = initialize_resident_identity_custody(
            home,
            host_transport_private_key_path=host_key_path,
        )
        initialize_hearth_activation(home)
    binding = ResidentProcessBinding(
        actor_id=args.actor_id,
        hearth_shard_id=manifest.hearth_shard_id,
        runtime_generation=manifest.runtime_generation,
        attachment_kind="city",
        world_id=args.world_id,
        city_id=args.city_id,
        session_id=args.session_id,
        model_id=args.model_id,
    )
    memory_dir = home / "memory"
    append_runtime_event(
        memory_dir,
        event_type="reference_process_bound",
        payload=binding.as_dict(),
        ts=args.started_at,
    )
    append_runtime_event(
        memory_dir,
        event_type="reference_activity_continued",
        payload={
            "activity_state_version": 1,
            "activity_id": _SYNTHETIC_ACTIVITY_ID,
            "activity": _SYNTHETIC_PRIVATE_ACTIVITY,
            "opened_at": args.started_at,
            "return_at": args.return_at,
            "wake_on": ["local_speech"],
        },
        ts=args.started_at,
    )
    package.parent.mkdir(parents=True, exist_ok=True)
    export_hearth_package(home, package)
    descriptor = describe_private_artifact(package)
    return_at = _parse_time(args.return_at)
    scheduled_return = build_reference_scheduled_return(
        actor_id=args.actor_id,
        activity_id=_SYNTHETIC_ACTIVITY_ID,
        due_at=return_at,
    )
    return {
        "schema": "worldweaver.synthetic-gym-private-artifact",
        "schema_version": 3,
        "descriptor": descriptor.as_dict(),
        "process": binding.as_dict(),
        "scheduled_return": scheduled_return.as_payload(),
        "identity": (
            identity_descriptor.to_dict() if identity_descriptor is not None else None
        ),
    }


def _restore(args: argparse.Namespace) -> dict:
    descriptor = _read_object(args.descriptor.resolve())
    process = ResidentProcessBinding.from_dict(
        _read_object(args.expected_process.resolve())
    )
    return restore_private_artifact(
        args.package.resolve(),
        args.home.resolve(),
        descriptor=descriptor,
        expected_process=process,
    )


def _restore_synthetic_fork(args: argparse.Namespace) -> dict:
    """Restore one synthetic branch without weakening portable hearth custody."""

    descriptor = _read_object(args.descriptor.resolve())
    process = ResidentProcessBinding.from_dict(
        _read_object(args.expected_process.resolve())
    )
    source_home = args.source_home.resolve()
    target_home = args.home.resolve()
    source_identity = load_resident_identity_descriptor(source_home)
    source_seal = (
        source_home / "identity" / SEALED_RESIDENT_IDENTITY_FILENAME
    ).resolve()
    source_session = source_home / "session_id.txt"
    if (
        source_identity.actor_id != process.actor_id
        or process.attachment_kind != "city"
        or not source_session.is_file()
        or source_session.read_text(encoding="utf-8").strip() != process.session_id
        or not source_seal.is_file()
        or target_home.exists()
        or target_home.is_symlink()
    ):
        raise PrivateArtifactError("synthetic fork source binding is invalid")
    staging = target_home.parent / f".{target_home.name}.fork-{uuid.uuid4().hex}"
    try:
        report = restore_private_artifact(
            args.package.resolve(),
            staging,
            descriptor=descriptor,
            expected_process=process,
        )
        target_identity = load_resident_identity_descriptor(staging)
        if source_identity != target_identity:
            raise PrivateArtifactError(
                "synthetic fork identity does not match its source"
            )
        target_seal = staging / "identity" / SEALED_RESIDENT_IDENTITY_FILENAME
        shutil.copyfile(source_seal, target_seal)
        target_seal.chmod(0o600)
        (staging / "session_id.txt").write_text(
            f"{process.session_id}\n", encoding="utf-8"
        )
        initialize_hearth_activation(staging)
        staging.rename(target_home)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {**report, "synthetic_fork_custody": "installed"}


def _export(args: argparse.Namespace) -> dict:
    home = args.home.resolve()
    package = args.package.resolve()
    package.parent.mkdir(parents=True, exist_ok=True)
    export_hearth_package(home, package)
    return describe_private_artifact(package).as_dict()


def _issue_runtime_certificate(args: argparse.Namespace) -> dict:
    signer = signer_from_host_sealed_identity(
        args.home.resolve(),
        audience=str(args.audience or "").strip(),
        host_transport_private_key_path=args.host_key.resolve(),
    )
    return {"certificate_header": signer.certificate_header}


def _describe_process(args: argparse.Namespace) -> dict:
    process = load_resident_process_envelope(args.home.resolve() / "memory")
    if not isinstance(process, dict):
        raise PrivateArtifactError("resident has no process checkpoint")
    return process


def _parse_time(raw: str) -> datetime:
    parsed = datetime.fromisoformat(str(raw or "").strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class _FixtureWorld:
    def __init__(self, scene: SceneData):
        self.scene = scene

    async def get_scene(self, _session_id: str) -> SceneData:
        return self.scene

    async def get_location_chat(self, _location: str, *, session_id: str) -> tuple:
        del session_id
        return ()

    async def get_pending_correspondence(
        self, _session_id: str, *, limit: int = 10
    ) -> tuple:
        del limit
        return ()

    async def acknowledge_correspondence(
        self, _session_id: str, _message_ids: tuple[int, ...]
    ) -> dict:
        return {"acknowledged_ids": []}


class _ScriptedWaitModel:
    def __init__(self) -> None:
        self.call_count = 0

    async def complete_json(self, *_args, **_kwargs) -> dict:
        self.call_count += 1
        return {"choice": "wait"}


async def _refuse_effect(*_args, **_kwargs) -> dict:
    raise RuntimeError("the scripted wait fixture may not perform an action or read")


_GYM_ADAPTER_PROTOCOL = "worldweaver.gym-participant-stdio"
_GYM_ADAPTER_PROTOCOL_VERSION = 2


def _write_protocol(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True), flush=True)


def _inject_transport_fault(mode: str, *, session_id: str) -> None:
    """Exercise parent/child framing failures before resident startup."""

    if not mode or mode == "malformed_response":
        return
    if mode == "child_exit":
        os._exit(86)
    if mode == "malformed_json":
        print("{malformed-child-message", flush=True)
        sys.stdin.readline()
        return
    if mode == "malformed_message":
        _write_protocol(
            {
                "protocol": _GYM_ADAPTER_PROTOCOL,
                "protocol_version": _GYM_ADAPTER_PROTOCOL_VERSION,
                "type": "unexpected",
            }
        )
        sys.stdin.readline()
        return
    if mode == "replayed_request":
        request = {
            "protocol": _GYM_ADAPTER_PROTOCOL,
            "protocol_version": _GYM_ADAPTER_PROTOCOL_VERSION,
            "type": "request",
            "request_id": "fault-request-replayed",
            "session_id": session_id,
            "operation": "http",
            "payload": {
                "method": "GET",
                "target": "/health",
                "headers": {},
                "body_base64": "",
            },
        }
        _write_protocol(request)
        sys.stdin.readline()
        _write_protocol(request)
        sys.stdin.readline()
        return
    raise ValueError("unsupported transport fault")


class _StdioHTTPTransport(httpx.AsyncBaseTransport):
    """Carry ordinary ``WorldWeaverClient`` HTTP requests to the parent app."""

    def __init__(self, session_id: str) -> None:
        self._request_sequence = 0
        self._session_id = str(session_id or "").strip()
        if not self._session_id:
            raise ValueError("gym HTTP transport requires a bound session")

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self._request_sequence += 1
        request_id = f"request-{self._request_sequence:08d}"
        body = await request.aread()
        target = request.url.raw_path.decode("ascii")
        _write_protocol(
            {
                "protocol": _GYM_ADAPTER_PROTOCOL,
                "protocol_version": _GYM_ADAPTER_PROTOCOL_VERSION,
                "type": "request",
                "request_id": request_id,
                "session_id": self._session_id,
                "operation": "http",
                "payload": {
                    "method": request.method,
                    "target": target,
                    "headers": dict(request.headers),
                    "body_base64": base64.b64encode(body).decode("ascii"),
                },
            }
        )
        line = sys.stdin.readline()
        if not line:
            raise RuntimeError("gym adapter closed before replying")
        try:
            response = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError("gym adapter returned invalid JSON") from exc
        if (
            not isinstance(response, dict)
            or response.get("protocol") != _GYM_ADAPTER_PROTOCOL
            or response.get("protocol_version") != _GYM_ADAPTER_PROTOCOL_VERSION
            or response.get("type") != "response"
            or response.get("request_id") != request_id
        ):
            raise RuntimeError("gym adapter response binding is invalid")
        if not bool(response.get("ok")):
            raise RuntimeError(str(response.get("error") or "gym operation failed"))
        result = response.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("gym HTTP transport response must be an object")
        try:
            content = base64.b64decode(str(result.get("body_base64") or ""))
        except (ValueError, TypeError) as exc:
            raise RuntimeError("gym HTTP transport body is invalid") from exc
        response_headers = result.get("headers")
        if not isinstance(response_headers, dict):
            raise RuntimeError("gym HTTP transport headers are invalid")
        return httpx.Response(
            status_code=int(result.get("status_code") or 500),
            headers={str(key): str(value) for key, value in response_headers.items()},
            content=content,
            request=request,
        )

    async def aclose(self) -> None:
        # ``WorldWeaverClient.for_resident`` closes its discovery client before
        # constructing the signed client over this same one-process transport.
        return None


class _ScriptedReadActModel:
    """Deterministic model fixture that exercises both adapter directions."""

    def __init__(self, *, model_id: str, target: str) -> None:
        self.default_model_id = model_id
        self._target = target
        self.total_calls = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

    async def complete_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        self.total_calls += 1
        if self.total_calls == 1:
            return {"choice": "read", "source": "measure", "query": "6 * 7"}
        return {
            "choice": "act",
            "action": {"kind": "move", "body": "", "target": self._target},
        }

    async def close(self) -> None:
        return None


class _ScriptedWeekModel:
    """Deterministic multi-activation policy for Willow Week conformance."""

    def __init__(self, *, model_id: str, step: int) -> None:
        self.default_model_id = model_id
        self.step = int(step)
        self.total_calls = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

    async def complete_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        self.total_calls += 1
        if self.step == 0:
            return {
                "choice": "act",
                "action": {"kind": "move", "body": "", "target": "Footbridge"},
            }
        if self.step == 1:
            return {
                "choice": "act",
                "action": {
                    "kind": "speak",
                    "body": "I can meet after the rain.",
                    "target": None,
                },
            }
        if self.step in {2, 3}:
            return {"choice": "wait"}
        if self.step == 4 and self.total_calls == 1:
            return {"choice": "read", "source": "recall", "query": "bridge"}
        if self.step == 4:
            return {
                "choice": "act",
                "action": {"kind": "move", "body": "", "target": "Willow Court"},
            }
        return {
            "choice": "act",
            "action": {"kind": "move", "body": "", "target": "home"},
        }

    async def close(self) -> None:
        return None


class _ScriptedGymCommandModel:
    """Deterministically select one real city source or one advertised effector."""

    def __init__(
        self,
        *,
        model_id: str,
        source: str = "",
        query: str = "",
        target: str = "",
        body: str = "",
        action_kind: str = "do",
    ) -> None:
        self.default_model_id = model_id
        self.source = str(source or "").strip()
        self.query = str(query or "").strip()
        self.target = str(target or "").strip()
        self.body = str(body or "").strip()
        self.action_kind = str(action_kind or "do").strip().lower()
        if self.action_kind not in {"do", "move", "speak"}:
            raise ValueError("scripted gym command action kind is invalid")
        if bool(self.source) == bool(self.target or self.body):
            raise ValueError(
                "scripted gym command requires exactly one source or action"
            )
        if self.action_kind == "move" and not self.target:
            raise ValueError("scripted gym movement requires a target")
        if self.action_kind == "speak" and not self.body:
            raise ValueError("scripted gym speech requires a body")
        self.total_calls = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

    async def complete_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        self.total_calls += 1
        if self.source and self.total_calls == 1:
            return {"choice": "read", "source": self.source, "query": self.query}
        if self.source:
            return {"choice": "wait"}
        return {
            "choice": "act",
            "action": {
                "kind": self.action_kind,
                "body": (
                    "" if self.action_kind == "move" else self.body or self.target
                ),
                "target": self.target or None,
            },
        }

    async def close(self) -> None:
        return None


class _ObservedModel:
    """Emit only content-free inference boundaries across the gym protocol."""

    def __init__(self, inner: Any, *, model_id: str):
        self.inner = inner
        self.model_id = model_id
        self.call_count = 0

    async def complete_json(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.call_count += 1
        _write_protocol(
            {
                "protocol": _GYM_ADAPTER_PROTOCOL,
                "protocol_version": _GYM_ADAPTER_PROTOCOL_VERSION,
                "type": "event",
                "event": "resident_inference_started",
                "detail": {"call_index": self.call_count, "model_id": self.model_id},
            }
        )
        try:
            result = await self.inner.complete_json(*args, **kwargs)
        except Exception as exc:
            _write_protocol(
                {
                    "protocol": _GYM_ADAPTER_PROTOCOL,
                    "protocol_version": _GYM_ADAPTER_PROTOCOL_VERSION,
                    "type": "event",
                    "event": "resident_inference_failed",
                    "detail": {
                        "call_index": self.call_count,
                        "model_id": self.model_id,
                        "reason": type(exc).__name__,
                        "prompt_tokens": int(
                            getattr(self.inner, "total_prompt_tokens", 0) or 0
                        ),
                        "completion_tokens": int(
                            getattr(self.inner, "total_completion_tokens", 0) or 0
                        ),
                    },
                }
            )
            raise
        _write_protocol(
            {
                "protocol": _GYM_ADAPTER_PROTOCOL,
                "protocol_version": _GYM_ADAPTER_PROTOCOL_VERSION,
                "type": "event",
                "event": "resident_inference_finished",
                "detail": {
                    "call_index": self.call_count,
                    "model_id": self.model_id,
                    "prompt_tokens": int(
                        getattr(self.inner, "total_prompt_tokens", 0) or 0
                    ),
                    "completion_tokens": int(
                        getattr(self.inner, "total_completion_tokens", 0) or 0
                    ),
                },
            }
        )
        return result


async def _run_model_return(args: argparse.Namespace) -> dict[str, Any]:
    home = args.home.resolve()
    expected_process = ResidentProcessBinding.from_dict(
        _read_object(args.expected_process.resolve())
    )
    restored_process = load_resident_process_envelope(home / "memory")
    if restored_process is None:
        raise PrivateArtifactError("restored resident has no process checkpoint")
    if ResidentProcessBinding.from_dict(restored_process) != expected_process:
        raise PrivateArtifactError("restored resident process binding does not match")

    model_id = expected_process.model_id
    if args.model_mode in {"scripted-read-home", "scripted-read-move"}:
        raw_model: Any = _ScriptedReadActModel(
            model_id=model_id,
            target=(
                "home" if args.model_mode == "scripted-read-home" else "Footbridge"
            ),
        )
    elif args.model_mode == "scripted-week":
        raw_model = _ScriptedWeekModel(
            model_id=model_id,
            step=int(args.scenario_step),
        )
    elif args.model_mode == "scripted-gym-command":
        raw_model = _ScriptedGymCommandModel(
            model_id=model_id,
            source=str(args.scripted_source or ""),
            query=str(args.scripted_query or ""),
            target=str(args.scripted_target or ""),
            body=str(args.scripted_body or ""),
            action_kind=str(args.scripted_action_kind or "do"),
        )
    else:
        key = os.environ.get("WW_INFERENCE_KEY", "").strip()
        if not key:
            raise PrivateArtifactError(
                "WW_INFERENCE_KEY is required for a model-backed gym resident"
            )
        configured_model = str(args.model or model_id).strip()
        if configured_model != model_id:
            raise PrivateArtifactError(
                "configured model does not match process binding"
            )
        raw_model = InferenceClient(
            base_url=os.environ.get("WW_INFERENCE_URL", "https://openrouter.ai/api/v1"),
            api_key=key,
            default_model=configured_model,
            timeout=float(os.environ.get("WW_INFERENCE_TIMEOUT", "200")),
        )
    model = _ObservedModel(raw_model, model_id=model_id)
    transport = (
        _StdioHTTPTransport(expected_process.session_id)
        if args.transport_mode == "stdio"
        else None
    )
    client: WorldWeaverClient | None = None
    controlled_clock = FixedWorldClock(_parse_time(args.now))
    _inject_transport_fault(
        str(args.transport_fault or ""),
        session_id=expected_process.session_id,
    )

    last_tick_result: dict[str, Any] | None = None
    last_scheduled_return: ReferenceScheduledReturn | None = None

    async def observe_host_tick(_identity, world, _core, _result, _tick_count):
        nonlocal last_scheduled_return, last_tick_result
        last_tick_result = dict(_result) if isinstance(_result, dict) else None
        last_scheduled_return = _core.scheduled_return()
        if isinstance(world, LocalWorld):
            grounding = await world.get_grounding()
            process = load_resident_process_envelope(home / "memory") or {}
            attachment = (
                process.get("attachment")
                if isinstance(process.get("attachment"), dict)
                else {}
            )
            hosting = (
                process.get("hosting")
                if isinstance(process.get("hosting"), dict)
                else {}
            )
            _write_protocol(
                {
                    "protocol": _GYM_ADAPTER_PROTOCOL,
                    "protocol_version": _GYM_ADAPTER_PROTOCOL_VERSION,
                    "type": "event",
                    "event": "resident_hearth_observed",
                    "detail": {
                        "attachment": str(attachment.get("kind") or ""),
                        "hosting_state": str(hosting.get("state") or ""),
                        "location": world.place,
                        "source_names": sorted(world.information_source_names),
                        "hour": int(grounding.get("hour") or 0),
                        "day_of_week": str(grounding.get("day_of_week") or ""),
                        "time_of_day": str(grounding.get("time_of_day") or ""),
                        "observed_at": controlled_clock.now().isoformat(),
                    },
                }
            )
            return
        _write_protocol(
            {
                "protocol": _GYM_ADAPTER_PROTOCOL,
                "protocol_version": _GYM_ADAPTER_PROTOCOL_VERSION,
                "type": "event",
                "event": "resident_city_profile_loaded",
                "detail": {
                    "city_id": resident.city_id,
                    "capability_ids": list(resident.city_capabilities),
                    "source_names": sorted(
                        str(item)
                        for item in tuple(
                            getattr(world, "information_source_names", ()) or ()
                        )
                        if str(item)
                    ),
                },
            }
        )

    async def observe_attachment_checkpoint(_identity, transition_id):
        _write_protocol(
            {
                "protocol": _GYM_ADAPTER_PROTOCOL,
                "protocol_version": _GYM_ADAPTER_PROTOCOL_VERSION,
                "type": "event",
                "event": "resident_attachment_checkpointed",
                "detail": {"transition_id": str(transition_id)},
            }
        )

    try:
        client = await WorldWeaverClient.for_resident(
            str(args.base_url or "").strip(),
            home,
            host_transport_private_key_path=args.host_key.resolve(),
            transport=transport,
        )
        resident = Resident(
            home,
            client,
            model,
            tick_seconds=2,
            pulse_model=model_id,
            pulse_temperature=None,
            tick_observer=observe_host_tick,
            attachment_checkpoint_observer=observe_attachment_checkpoint,
            world_clock=controlled_clock,
        )
        await resident.start(expected_process.world_id)
        _write_protocol(
            {
                "protocol": _GYM_ADAPTER_PROTOCOL,
                "protocol_version": _GYM_ADAPTER_PROTOCOL_VERSION,
                "type": "event",
                "event": "resident_host_started",
                "detail": {},
            }
        )
        if args.command in {"observe-hearth-model", "run-tick-model"}:
            if expected_process.attachment_kind != "hearth":
                if args.command == "observe-hearth-model":
                    raise PrivateArtifactError(
                        "hearth observation requires a hearth-bound process"
                    )
            await resident.run(
                max_ticks=1,
                pause_seconds=0.0,
                force_initial_ignite=args.command == "run-tick-model",
            )
            if args.command == "observe-hearth-model":
                result = {
                    "status": "observed",
                    "event_id": "",
                    "activation_status": "observed",
                    "choice": "none",
                }
            else:
                result = {
                    "status": "processed",
                    "event_id": str(args.event_id),
                    "activation_status": str(
                        (last_tick_result or {}).get("status") or "completed"
                    ),
                    "choice": str((last_tick_result or {}).get("choice") or "none"),
                    "action_outcome": str(
                        (last_tick_result or {}).get("action_outcome") or ""
                    ),
                }
            scheduled_return = (
                None
                if args.command == "observe-hearth-model"
                else last_scheduled_return
            )
        else:
            result, scheduled_return = await resident.run_scheduled_return(
                args.event_id,
                now=_parse_time(args.now),
            )
        _write_protocol(
            {
                "protocol": _GYM_ADAPTER_PROTOCOL,
                "protocol_version": _GYM_ADAPTER_PROTOCOL_VERSION,
                "type": "event",
                "event": "resident_host_finished",
                "detail": {},
            }
        )
    finally:
        await raw_model.close()
        if client is not None:
            await client.close()
    process = load_resident_process_envelope(home / "memory")
    if not isinstance(process, dict):
        raise PrivateArtifactError("model host omitted its final process checkpoint")
    return {
        "schema": "worldweaver.synthetic-gym-return-result",
        "schema_version": 3,
        "status": str(result.get("status") or ""),
        "event_id": str(result.get("event_id") or ""),
        "activation_status": str(result.get("activation_status") or ""),
        "choice": str(result.get("choice") or "none"),
        "action_outcome": str(result.get("action_outcome") or ""),
        "model_id": model_id,
        "model_call_count": model.call_count,
        "prompt_tokens": int(getattr(raw_model, "total_prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(raw_model, "total_completion_tokens", 0) or 0),
        "scheduled_return": (
            scheduled_return.as_payload() if scheduled_return is not None else None
        ),
        "process": process,
    }


def _handle_model_return(args: argparse.Namespace) -> dict[str, Any]:
    return asyncio.run(_run_model_return(args))


def _handle_return(args: argparse.Namespace) -> dict:
    home = args.home.resolve()
    expected_process = ResidentProcessBinding.from_dict(
        _read_object(args.expected_process.resolve())
    )
    restored_process = load_resident_process_envelope(home / "memory")
    if restored_process is None:
        raise PrivateArtifactError("restored resident has no process checkpoint")
    if ResidentProcessBinding.from_dict(restored_process) != expected_process:
        raise PrivateArtifactError("restored resident process binding does not match")

    scene_payload = _read_object(args.scene.resolve())
    scene = scene_data_from_payload(
        scene_payload,
        session_id=expected_process.session_id,
    )
    model = _ScriptedWaitModel()
    identity = ResidentIdentity(
        name="synthetic_gym_resident",
        actor_id=expected_process.actor_id,
        soul="You are a synthetic gym participant.",
        canonical_soul="You are a synthetic gym participant.",
        growth_soul="",
        vibe="",
        core="",
        voice_seed=[],
        tuning=LoopTuning(),
    )
    core = ReferenceResidentCore(
        identity=identity,
        memory_dir=home / "memory",
        world=_FixtureWorld(scene),
        llm=model,
        session_id=expected_process.session_id,
        effector=_refuse_effect,
        information_access=_refuse_effect,
        tick_seconds=2,
        model=expected_process.model_id,
    )
    result = asyncio.run(
        core.handle_scheduled_return(
            args.event_id,
            now=_parse_time(args.now),
        )
    )
    return {
        "schema": "worldweaver.synthetic-gym-return-result",
        "schema_version": 1,
        "status": str(result.get("status") or ""),
        "event_id": str(result.get("event_id") or ""),
        "activation_status": str(result.get("activation_status") or ""),
        "choice": str(result.get("choice") or "none"),
        "model_call_count": model.call_count,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    fixture = subparsers.add_parser(
        "create-fixture",
        help="create a new synthetic home and stopped portable artifact",
    )
    fixture.add_argument("--home", type=Path, required=True)
    fixture.add_argument("--package", type=Path, required=True)
    fixture.add_argument("--actor-id", required=True)
    fixture.add_argument("--display-name", default="Synthetic Gym Resident")
    fixture.add_argument("--world-id", required=True)
    fixture.add_argument("--city-id", default="")
    fixture.add_argument("--session-id", required=True)
    fixture.add_argument("--model-id", default="test/reference-policy-v1")
    fixture.add_argument("--started-at", required=True)
    fixture.add_argument("--return-at", required=True)
    fixture.add_argument("--host-key", type=Path)

    restore = subparsers.add_parser(
        "restore",
        help="verify and restore into a new synthetic resident home",
    )
    restore.add_argument("--package", type=Path, required=True)
    restore.add_argument("--home", type=Path, required=True)
    restore.add_argument("--descriptor", type=Path, required=True)
    restore.add_argument("--expected-process", type=Path, required=True)
    fork_restore = subparsers.add_parser(
        "restore-synthetic-fork",
        help="restore one explicitly synthetic counterfactual branch",
    )
    fork_restore.add_argument("--package", type=Path, required=True)
    fork_restore.add_argument("--home", type=Path, required=True)
    fork_restore.add_argument("--descriptor", type=Path, required=True)
    fork_restore.add_argument("--expected-process", type=Path, required=True)
    fork_restore.add_argument("--source-home", type=Path, required=True)
    export = subparsers.add_parser(
        "export",
        help="export an updated stopped synthetic home for the engine checkpoint",
    )
    export.add_argument("--home", type=Path, required=True)
    export.add_argument("--package", type=Path, required=True)
    certificate = subparsers.add_parser(
        "issue-runtime-certificate",
        help="issue public runtime proof for one stopped synthetic resident",
    )
    certificate.add_argument("--home", type=Path, required=True)
    certificate.add_argument("--host-key", type=Path, required=True)
    certificate.add_argument("--audience", required=True)
    describe_process = subparsers.add_parser(
        "describe-process",
        help="return the content-free current resident process checkpoint",
    )
    describe_process.add_argument("--home", type=Path, required=True)
    handle_return = subparsers.add_parser(
        "handle-return",
        help="offer a due return to the restored reference core with a scripted wait",
    )
    handle_return.add_argument("--home", type=Path, required=True)
    handle_return.add_argument("--expected-process", type=Path, required=True)
    handle_return.add_argument("--scene", type=Path, required=True)
    handle_return.add_argument("--event-id", required=True)
    handle_return.add_argument("--now", required=True)
    model_return = subparsers.add_parser(
        "handle-return-model",
        help="run a normally hosted model-backed resident over the two-way gym protocol",
    )
    model_return.add_argument("--home", type=Path, required=True)
    model_return.add_argument("--expected-process", type=Path, required=True)
    model_return.add_argument("--event-id", required=True)
    model_return.add_argument("--now", required=True)
    model_return.add_argument("--model", default="")
    model_return.add_argument("--host-key", type=Path, required=True)
    model_return.add_argument(
        "--transport-mode",
        choices=("stdio", "loopback"),
        default="stdio",
        help=argparse.SUPPRESS,
    )
    model_return.add_argument(
        "--base-url",
        default="http://worldweaver-gym.local",
        help=argparse.SUPPRESS,
    )
    model_return.add_argument(
        "--model-mode",
        choices=(
            "live",
            "scripted-read-home",
            "scripted-read-move",
            "scripted-week",
            "scripted-gym-command",
        ),
        default="live",
        help=argparse.SUPPRESS,
    )
    model_return.add_argument(
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
    model_return.add_argument(
        "--scenario-step", type=int, default=0, help=argparse.SUPPRESS
    )
    model_return.add_argument("--scripted-source", default="", help=argparse.SUPPRESS)
    model_return.add_argument("--scripted-query", default="", help=argparse.SUPPRESS)
    model_return.add_argument("--scripted-target", default="", help=argparse.SUPPRESS)
    model_return.add_argument("--scripted-body", default="", help=argparse.SUPPRESS)
    model_return.add_argument(
        "--scripted-action-kind", default="do", help=argparse.SUPPRESS
    )
    hearth_observation = subparsers.add_parser(
        "observe-hearth-model",
        help="restart a normally hosted resident and observe its private hearth",
    )
    hearth_observation.add_argument("--home", type=Path, required=True)
    hearth_observation.add_argument("--expected-process", type=Path, required=True)
    hearth_observation.add_argument("--now", required=True)
    hearth_observation.add_argument("--model", default="")
    hearth_observation.add_argument("--host-key", type=Path, required=True)
    hearth_observation.add_argument(
        "--transport-mode",
        choices=("stdio", "loopback"),
        default="stdio",
        help=argparse.SUPPRESS,
    )
    hearth_observation.add_argument(
        "--base-url",
        default="http://worldweaver-gym.local",
        help=argparse.SUPPRESS,
    )
    hearth_observation.add_argument(
        "--model-mode",
        choices=(
            "live",
            "scripted-read-home",
            "scripted-read-move",
            "scripted-week",
            "scripted-gym-command",
        ),
        default="live",
        help=argparse.SUPPRESS,
    )
    hearth_observation.add_argument(
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
    hearth_observation.add_argument(
        "--scenario-step", type=int, default=0, help=argparse.SUPPRESS
    )
    hearth_observation.add_argument(
        "--scripted-source", default="", help=argparse.SUPPRESS
    )
    hearth_observation.add_argument(
        "--scripted-query", default="", help=argparse.SUPPRESS
    )
    hearth_observation.add_argument(
        "--scripted-target", default="", help=argparse.SUPPRESS
    )
    hearth_observation.add_argument(
        "--scripted-body", default="", help=argparse.SUPPRESS
    )
    hearth_observation.add_argument(
        "--scripted-action-kind", default="do", help=argparse.SUPPRESS
    )
    tick = subparsers.add_parser(
        "run-tick-model",
        help="run one normally hosted model activation for a synthetic scenario event",
    )
    tick.add_argument("--home", type=Path, required=True)
    tick.add_argument("--expected-process", type=Path, required=True)
    tick.add_argument("--event-id", required=True)
    tick.add_argument("--now", required=True)
    tick.add_argument("--model", default="")
    tick.add_argument("--host-key", type=Path, required=True)
    tick.add_argument(
        "--transport-mode", choices=("stdio", "loopback"), default="stdio"
    )
    tick.add_argument("--base-url", default="http://worldweaver-gym.local")
    tick.add_argument(
        "--model-mode",
        choices=(
            "live",
            "scripted-read-home",
            "scripted-read-move",
            "scripted-week",
            "scripted-gym-command",
        ),
        default="live",
    )
    tick.add_argument("--scenario-step", type=int, default=0)
    tick.add_argument("--scripted-source", default="", help=argparse.SUPPRESS)
    tick.add_argument("--scripted-query", default="", help=argparse.SUPPRESS)
    tick.add_argument("--scripted-target", default="", help=argparse.SUPPRESS)
    tick.add_argument("--scripted-body", default="", help=argparse.SUPPRESS)
    tick.add_argument("--scripted-action-kind", default="do", help=argparse.SUPPRESS)
    tick.add_argument("--transport-fault", default="", help=argparse.SUPPRESS)
    return parser


def main() -> int:
    args = _parser().parse_args()
    interactive = args.command in {
        "handle-return-model",
        "observe-hearth-model",
        "run-tick-model",
    }
    try:
        handlers = {
            "create-fixture": _create_fixture,
            "restore": _restore,
            "restore-synthetic-fork": _restore_synthetic_fork,
            "export": _export,
            "issue-runtime-certificate": _issue_runtime_certificate,
            "describe-process": _describe_process,
            "handle-return": _handle_return,
            "handle-return-model": _handle_model_return,
            "observe-hearth-model": _handle_model_return,
            "run-tick-model": _handle_model_return,
        }
        result = handlers[args.command](args)
    except (OSError, PrivateArtifactError, ValueError) as exc:
        if interactive:
            _write_protocol(
                {
                    "protocol": _GYM_ADAPTER_PROTOCOL,
                    "protocol_version": _GYM_ADAPTER_PROTOCOL_VERSION,
                    "type": "error",
                    "error": str(exc),
                }
            )
            return 2
        print(json.dumps({"status": "invalid", "error": str(exc)}), file=sys.stderr)
        return 2
    if interactive:
        _write_protocol(
            {
                "protocol": _GYM_ADAPTER_PROTOCOL,
                "protocol_version": _GYM_ADAPTER_PROTOCOL_VERSION,
                "type": "result",
                "result": result,
            }
        )
        return 0
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
