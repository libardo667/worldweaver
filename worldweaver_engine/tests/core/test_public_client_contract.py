from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_API = ENGINE_ROOT / "client-public" / "src" / "api" / "ww.ts"
PUBLIC_COMPONENTS = ENGINE_ROOT / "client-public" / "src" / "components"
PUBLIC_STYLES = ENGINE_ROOT / "client-public" / "src" / "styles" / "app.css"


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


def test_public_client_wraps_one_place_door_actions_without_a_town_wide_access_view():
    source = PUBLIC_API.read_text(encoding="utf-8")
    place_panel = (PUBLIC_COMPONENTS / "PlacePanel.tsx").read_text(encoding="utf-8")

    for route in (
        '"/api/world/access"',
        '"/api/world/access/requests"',
        '"/api/world/access/mode"',
    ):
        assert route in source
    assert "<AccessHere location={node.name}" in place_panel


def test_public_client_keeps_keyboard_and_reduced_motion_guards():
    world_map = (PUBLIC_COMPONENTS / "WorldMap.tsx").read_text(encoding="utf-8")
    threshold = (PUBLIC_COMPONENTS / "ThresholdOverlay.tsx").read_text(encoding="utf-8")
    join = (PUBLIC_COMPONENTS / "JoinFlow.tsx").read_text(encoding="utf-8")
    styles = PUBLIC_STYLES.read_text(encoding="utf-8")

    assert 'element.setAttribute("tabindex", "0")' in world_map
    assert 'key !== "Enter" && key !== " "' in world_map
    assert 'role="dialog"' in threshold
    assert 'className="sr-only"' in join
    assert "prefers-reduced-motion: reduce" in styles
    assert ":focus-visible" in styles
