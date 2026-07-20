from __future__ import annotations

import json

import pytest

from src.services.hearth_transport import (
    HearthTransportDescriptor,
    HearthTransportError,
    generate_hearth_transport_identity,
    hearth_transport_key_id,
    load_hearth_transport_private_key,
)


def test_generated_transport_key_is_private_separate_and_matches_descriptor(tmp_path):
    private_path = tmp_path / "hearth-host" / "identity" / "transport.key"
    descriptor_path = tmp_path / "hearth-host.json"

    descriptor = generate_hearth_transport_identity(
        private_key_path=private_path,
        descriptor_path=descriptor_path,
    )
    private_key = load_hearth_transport_private_key(private_path)

    assert private_path.stat().st_mode & 0o077 == 0
    assert json.loads(descriptor_path.read_text(encoding="utf-8")) == (
        descriptor.to_dict()
    )
    assert descriptor == HearthTransportDescriptor.from_dict(descriptor.to_dict())
    assert descriptor.transport_key_id == hearth_transport_key_id(
        private_key.public_key()
    )


def test_transport_generation_refuses_to_replace_either_half(tmp_path):
    private_path = tmp_path / "identity" / "transport.key"
    descriptor_path = tmp_path / "hearth-host.json"
    first = generate_hearth_transport_identity(
        private_key_path=private_path,
        descriptor_path=descriptor_path,
    )

    with pytest.raises(HearthTransportError, match="Refusing to replace"):
        generate_hearth_transport_identity(
            private_key_path=private_path,
            descriptor_path=descriptor_path,
        )

    assert (
        HearthTransportDescriptor.from_dict(
            json.loads(descriptor_path.read_text(encoding="utf-8"))
        )
        == first
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", True, "schema"),
        ("transport_key_id", "x25519:" + ("0" * 32), "key ID"),
        ("transport_public_key", " not-a-key", "public key"),
    ],
)
def test_transport_descriptor_rejects_changed_or_ambiguous_fields(
    tmp_path, field, value, message
):
    descriptor = generate_hearth_transport_identity(
        private_key_path=tmp_path / "identity" / "transport.key",
        descriptor_path=tmp_path / "hearth-host.json",
    )
    raw = descriptor.to_dict()
    raw[field] = value

    with pytest.raises(HearthTransportError, match=message):
        HearthTransportDescriptor.from_dict(raw)
