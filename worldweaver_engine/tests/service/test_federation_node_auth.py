from __future__ import annotations

import json

import pytest

from src.services.federation_node_auth import (
    NodeSignatureError,
    generate_node_identity,
    signed_request_headers,
    verify_signed_request,
)


def test_generated_identity_signs_and_verifies_exact_request(tmp_path) -> None:
    private_key = tmp_path / "identity" / "node.key"
    descriptor_path = tmp_path / "node.json"
    descriptor = generate_node_identity(
        private_key_path=private_key,
        descriptor_path=descriptor_path,
        node_id="river-coop-1",
        shard_type="city",
        city_id="portland",
    )
    body = b'{"shard_id":"river-coop-1"}'
    headers = signed_request_headers(
        node_id="river-coop-1",
        private_key_path=private_key,
        method="POST",
        path="/api/federation/pulse",
        body=body,
        timestamp=1_800_000_000,
        nonce="request-one",
    )

    assert json.loads(descriptor_path.read_text(encoding="utf-8")) == descriptor
    assert private_key.stat().st_mode & 0o077 == 0
    assert verify_signed_request(
        public_key=str(descriptor["public_key"]),
        method="POST",
        path="/api/federation/pulse",
        body=body,
        headers=headers,
        now=1_800_000_000,
    ) == ("1800000000", "request-one")


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/api/federation/pulse", b'{"shard_id":"river-coop-1"}'),
        ("POST", "/api/federation/travel/start", b'{"shard_id":"river-coop-1"}'),
        ("POST", "/api/federation/pulse", b'{"shard_id":"another-node"}'),
    ],
)
def test_signature_rejects_changed_request(tmp_path, method, path, body) -> None:
    private_key = tmp_path / "identity" / "node.key"
    descriptor = generate_node_identity(
        private_key_path=private_key,
        descriptor_path=tmp_path / "node.json",
        node_id="river-coop-1",
        shard_type="city",
        city_id="portland",
    )
    headers = signed_request_headers(
        node_id="river-coop-1",
        private_key_path=private_key,
        method="POST",
        path="/api/federation/pulse",
        body=b'{"shard_id":"river-coop-1"}',
        timestamp=1_800_000_000,
        nonce="request-one",
    )

    with pytest.raises(NodeSignatureError, match="signature is invalid"):
        verify_signed_request(
            public_key=str(descriptor["public_key"]),
            method=method,
            path=path,
            body=body,
            headers=headers,
            now=1_800_000_000,
        )


def test_signature_rejects_expired_timestamp(tmp_path) -> None:
    private_key = tmp_path / "identity" / "node.key"
    descriptor = generate_node_identity(
        private_key_path=private_key,
        descriptor_path=tmp_path / "node.json",
        node_id="river-coop-1",
        shard_type="city",
        city_id=None,
    )
    headers = signed_request_headers(
        node_id="river-coop-1",
        private_key_path=private_key,
        method="GET",
        path="/api/federation/actors/example",
        timestamp=1_800_000_000,
        nonce="request-one",
    )

    with pytest.raises(NodeSignatureError, match="outside the allowed window"):
        verify_signed_request(
            public_key=str(descriptor["public_key"]),
            method="GET",
            path="/api/federation/actors/example",
            body=b"",
            headers=headers,
            now=1_800_000_301,
        )
