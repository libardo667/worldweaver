from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
import httpx
import pytest

from src.world.client import WorldWeaverClient
from src.identity.hearth_manifest import initialize_hearth_manifest
from src.identity.resident_identity import (
    create_resident_identity_descriptor,
    write_resident_identity_descriptor,
)
from src.identity.resident_key_seal import (
    SEALED_RESIDENT_IDENTITY_FILENAME,
    seal_resident_identity_private_key,
    write_resident_key_seal,
)
from src.world.resident_signing import (
    RESIDENT_CERTIFICATE_HEADER,
    RESIDENT_NONCE_HEADER,
    RESIDENT_SIGNATURE_HEADER,
    RESIDENT_TIMESTAMP_HEADER,
    ResidentRequestSigner,
    ResidentSigningError,
    signer_from_host_sealed_identity,
)


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _signer() -> ResidentRequestSigner:
    private_key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    certificate_header = _encode(b'{"schema":"synthetic-test-certificate"}')
    return ResidentRequestSigner(
        runtime_private_key=private_key,
        certificate_header=certificate_header,
    )


def _sealed_resident(tmp_path: Path) -> tuple[Path, Path, Ed25519PrivateKey]:
    home = tmp_path / "resident"
    identity_dir = home / "identity"
    identity_dir.mkdir(parents=True)
    (identity_dir / "resident_id.txt").write_text("actor-test", encoding="utf-8")
    manifest = initialize_hearth_manifest(home)
    identity_private = Ed25519PrivateKey.generate()
    descriptor = create_resident_identity_descriptor(
        manifest,
        identity_private_key=identity_private,
    )
    write_resident_identity_descriptor(home, descriptor)
    host_private = X25519PrivateKey.generate()
    host_key_path = tmp_path / "transport.key"
    host_key_path.write_text(
        _encode(host_private.private_bytes_raw()) + "\n",
        encoding="utf-8",
    )
    encoded_seal = seal_resident_identity_private_key(
        identity_private,
        identity_descriptor=descriptor,
        recipient_transport_public_key=host_private.public_key(),
    )
    write_resident_key_seal(
        identity_dir / SEALED_RESIDENT_IDENTITY_FILENAME,
        encoded_seal,
    )
    return home, host_key_path, identity_private


def test_host_sealed_identity_issues_engine_compatible_runtime_certificate(tmp_path):
    home, host_key_path, identity_private = _sealed_resident(tmp_path)

    signer = signer_from_host_sealed_identity(
        home,
        audience="ww_alderbank",
        host_transport_private_key_path=host_key_path,
    )

    certificate = json.loads(_decode(signer.certificate_header))
    signature = _decode(certificate.pop("identity_signature"))
    identity_private.public_key().verify(
        signature,
        json.dumps(
            certificate,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8"),
    )
    assert certificate["actor_id"] == "actor-test"
    assert certificate["runtime_generation"] == 1
    assert certificate["audience"] == "ww_alderbank"
    assert certificate["scopes"] == [
        "session.act",
        "session.bootstrap",
        "session.lifecycle",
    ]


def _verify_request_signature(signer, headers, *, method, target, body):
    canonical = "\n".join(
        (
            method,
            target,
            headers[RESIDENT_TIMESTAMP_HEADER],
            headers[RESIDENT_NONCE_HEADER],
            hashlib.sha256(body).hexdigest(),
            hashlib.sha256(
                headers[RESIDENT_CERTIFICATE_HEADER].encode("ascii")
            ).hexdigest(),
        )
    ).encode("utf-8")
    signer.runtime_private_key.public_key().verify(
        _decode(headers[RESIDENT_SIGNATURE_HEADER]),
        canonical,
    )


def test_signer_covers_exact_method_target_body_timestamp_and_nonce():
    signer = _signer()
    body = b'{"hello":"world"}'

    headers = signer.signed_headers(
        method="post",
        target="/api/world/make?mode=one%20two",
        body=body,
        timestamp=1_784_544_000,
        nonce="nonce-123",
    )

    assert headers[RESIDENT_TIMESTAMP_HEADER] == "1784544000"
    assert headers[RESIDENT_NONCE_HEADER] == "nonce-123"
    _verify_request_signature(
        signer,
        headers,
        method="POST",
        target="/api/world/make?mode=one%20two",
        body=body,
    )


@pytest.mark.parametrize(
    "target",
    ["", "https://city.example/api/world", "/api/world\n/other", "/café"],
)
def test_signer_rejects_noncanonical_targets(target):
    with pytest.raises(ResidentSigningError, match="target"):
        _signer().signed_headers(method="GET", target=target)


@pytest.mark.asyncio
async def test_world_client_signs_the_serialized_json_and_encoded_query_target():
    signer = _signer()
    requests: list[httpx.Request] = []

    async def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    client = WorldWeaverClient(
        "https://city.example",
        resident_signer=signer,
        transport=httpx.MockTransport(handle),
    )
    try:
        await client.make_world_object(
            "resident-session",
            "clay_cup",
            "make-once",
        )
        await client._get(
            "/api/world/objects",
            params={"session_id": "resident session", "kind": ["cup", "token"]},
        )
    finally:
        await client.close()

    post, get = requests
    assert json.loads(post.content) == {
        "session_id": "resident-session",
        "recipe_id": "clay_cup",
        "idempotency_key": "make-once",
    }
    _verify_request_signature(
        signer,
        post.headers,
        method="POST",
        target="/api/world/make",
        body=post.content,
    )
    assert (
        get.url.raw_path
        == b"/api/world/objects?session_id=resident+session&kind=cup&kind=token"
    )
    _verify_request_signature(
        signer,
        get.headers,
        method="GET",
        target=get.url.raw_path.decode("ascii"),
        body=b"",
    )


@pytest.mark.asyncio
async def test_signed_world_client_uses_the_pre_admitted_bootstrap_route():
    signer = _signer()
    requests: list[httpx.Request] = []

    async def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"success": True})

    client = WorldWeaverClient(
        "https://city.example",
        resident_signer=signer,
        transport=httpx.MockTransport(handle),
    )
    try:
        await client.bootstrap_session(
            session_id="resident-session",
            world_id="world-one",
            world_theme="",
            player_role="Resident",
            actor_id="resident-actor",
        )
    finally:
        await client.close()

    assert len(requests) == 1
    request = requests[0]
    assert request.url.path == "/api/session/bootstrap/resident"
    _verify_request_signature(
        signer,
        request.headers,
        method="POST",
        target="/api/session/bootstrap/resident",
        body=request.content,
    )


@pytest.mark.asyncio
async def test_resident_client_discovers_audience_then_uses_the_sealed_identity(
    tmp_path,
):
    home, host_key_path, _identity_private = _sealed_resident(tmp_path)
    requests: list[httpx.Request] = []

    async def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/settings/readiness":
            return httpx.Response(
                200,
                json={"shard": {"shard_id": "ww_alderbank"}},
            )
        return httpx.Response(200, json={"success": True})

    client = await WorldWeaverClient.for_resident(
        "https://city.example",
        home,
        host_transport_private_key_path=host_key_path,
        transport=httpx.MockTransport(handle),
    )
    try:
        await client.bootstrap_session(
            session_id="resident-session",
            world_id="world-one",
            world_theme="",
            player_role="Resident",
            actor_id="actor-test",
        )
    finally:
        await client.close()

    assert client.has_resident_signer is True
    assert [request.url.path for request in requests] == [
        "/api/settings/readiness",
        "/api/session/bootstrap/resident",
    ]
    assert RESIDENT_SIGNATURE_HEADER in requests[-1].headers


@pytest.mark.asyncio
async def test_resident_client_refuses_a_half_present_identity(tmp_path):
    home, host_key_path, _identity_private = _sealed_resident(tmp_path)
    (home / "identity" / SEALED_RESIDENT_IDENTITY_FILENAME).unlink()

    with pytest.raises(ResidentSigningError, match="both exist or both be absent"):
        await WorldWeaverClient.for_resident(
            "https://city.example",
            home,
            host_transport_private_key_path=host_key_path,
        )


def test_signer_replaces_a_runtime_key_before_its_certificate_expires():
    first_key = Ed25519PrivateKey.generate()
    second_key = Ed25519PrivateKey.generate()
    first_certificate = _encode(b'{"certificate":"first"}')
    second_certificate = _encode(b'{"certificate":"second"}')
    refreshes = []

    def refresh():
        refreshes.append(True)
        return second_key, second_certificate, 10_000

    signer = ResidentRequestSigner(
        runtime_private_key=first_key,
        certificate_header=first_certificate,
        certificate_expires_at=100,
        refresh=refresh,
    )

    headers = signer.signed_headers(
        method="GET",
        target="/api/world/id",
        timestamp=50,
        nonce="refresh-test",
    )

    assert refreshes == [True]
    assert headers[RESIDENT_CERTIFICATE_HEADER] == second_certificate
    _verify_request_signature(
        signer,
        headers,
        method="GET",
        target="/api/world/id",
        body=b"",
    )


@pytest.mark.asyncio
async def test_each_retry_uses_a_fresh_nonce(monkeypatch):
    signer = _signer()
    requests: list[httpx.Request] = []

    async def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(500 if len(requests) == 1 else 200, json={"ok": True})

    async def no_sleep(_delay):
        return None

    monkeypatch.setattr("src.world.client.asyncio.sleep", no_sleep)
    client = WorldWeaverClient(
        "https://city.example",
        resident_signer=signer,
        transport=httpx.MockTransport(handle),
    )
    try:
        response = await client._get_with_retry("/api/world/id", max_retries=1)
    finally:
        await client.close()

    assert response.status_code == 200
    assert len(requests) == 2
    assert (
        requests[0].headers[RESIDENT_NONCE_HEADER]
        != requests[1].headers[RESIDENT_NONCE_HEADER]
    )
