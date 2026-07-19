from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_API = ENGINE_ROOT / "client-public" / "src" / "api" / "ww.ts"


def test_public_client_wraps_current_typed_participant_custody_actions():
    source = PUBLIC_API.read_text(encoding="utf-8")

    for route in (
        "/api/world/objects/${encodeURIComponent(objectId)}/give",
        "/api/world/exchanges",
        "/api/world/stoops/entries/${encodeURIComponent(entryId)}/withdraw",
    ):
        assert route in source


def test_public_client_does_not_wrap_private_or_shard_wide_telemetry():
    source = PUBLIC_API.read_text(encoding="utf-8")

    for forbidden_route in (
        "/api/action",
        "/api/settings/readiness",
        "/api/world/digest",
        "/api/world/rest-metrics",
        "/api/world/roster",
    ):
        assert forbidden_route not in source
