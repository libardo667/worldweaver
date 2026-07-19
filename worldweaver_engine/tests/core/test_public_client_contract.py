from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_API = ENGINE_ROOT / "client-public" / "src" / "api" / "ww.ts"
PUBLIC_COMPONENTS = ENGINE_ROOT / "client-public" / "src" / "components"
PUBLIC_STYLES = ENGINE_ROOT / "client-public" / "src" / "styles" / "app.css"
PUBLIC_VITE = ENGINE_ROOT / "client-public" / "vite.config.ts"


def test_public_client_wraps_current_typed_participant_custody_actions():
    source = PUBLIC_API.read_text(encoding="utf-8")

    for route in (
        "/api/world/objects/${encodeURIComponent(objectId)}/give",
        "/api/world/exchanges",
        "/api/world/stoops/entries/${encodeURIComponent(entryId)}/withdraw",
    ):
        assert route in source


def test_public_client_can_read_and_leave_the_same_local_marks_as_residents():
    source = PUBLIC_API.read_text(encoding="utf-8")
    place_panel = (PUBLIC_COMPONENTS / "PlacePanel.tsx").read_text(encoding="utf-8")
    marks = (PUBLIC_COMPONENTS / "MarksHere.tsx").read_text(encoding="utf-8")

    assert 'getJson("/api/world/traces"' in source
    assert 'postJson("/api/world/traces"' in source
    assert "<MarksHere" in place_panel
    assert "A mark stays at this exact place" in marks


def test_public_client_keeps_actor_password_recovery_on_the_public_entry_path():
    source = PUBLIC_API.read_text(encoding="utf-8")
    app = (ENGINE_ROOT / "client-public" / "src" / "App.tsx").read_text(encoding="utf-8")
    join = (PUBLIC_COMPONENTS / "JoinFlow.tsx").read_text(encoding="utf-8")

    assert '"/api/auth/request-password-reset"' in source
    assert '"/api/auth/reset-password"' in source
    assert 'get("reset_token")' in app
    assert 'mode === "reset"' in join


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


def test_schematic_map_keeps_layout_stable_and_does_not_draw_containment_as_a_path():
    world_map = (PUBLIC_COMPONENTS / "WorldMap.tsx").read_text(encoding="utf-8")
    app = (ENGINE_ROOT / "client-public" / "src" / "App.tsx").read_text(encoding="utf-8")
    place_panel = (PUBLIC_COMPONENTS / "PlacePanel.tsx").read_text(encoding="utf-8")

    assert "stableOffsetAngle(node.key)" in world_map
    assert 'if (edge.kind !== "path") continue' in world_map
    assert "{!placeParams && <ThemeToggle />}" in app
    assert "<ThemeToggle inline />" in place_panel


def test_schematic_map_uses_a_precompiled_field_drawing_without_generating_in_the_browser():
    world_map = (PUBLIC_COMPONENTS / "WorldMap.tsx").read_text(encoding="utf-8")
    api = PUBLIC_API.read_text(encoding="utf-8")

    assert 'getJson("/api/world/map/generated")' in api
    assert 'localShardPath("/api/world/map/generated.svg")' in api
    assert "L.imageOverlay(" in world_map
    assert "generatedLayerRef.current.bringToBack()" in world_map
    assert "map.getBoundsZoom(sheetBounds, true)" in world_map
    assert "map.setMaxBounds(sheetBounds)" in world_map
    assert "maxBoundsViscosity: 1" in world_map
    assert "Math.random(" not in world_map


def test_public_client_can_keep_shard_api_traffic_under_a_same_origin_prefix():
    api = PUBLIC_API.read_text(encoding="utf-8")
    base = (ENGINE_ROOT / "client-public" / "src" / "api" / "base.ts").read_text(encoding="utf-8")
    vite = PUBLIC_VITE.read_text(encoding="utf-8")

    assert "localShardPath(path)" in api
    assert "currentShardBase" in base
    assert "currentShardScope" in base
    assert "VITE_WW_SHARD_ROUTES" in vite
    assert "shardProxyEntries" in vite

    store = (ENGINE_ROOT / "client-public" / "src" / "session" / "store.ts").read_text(encoding="utf-8")
    assert "localKey(SESSION_KEY)" in store
    assert "localKey(PLACE_KEY)" in store


def test_public_client_travel_redirect_carries_only_a_recoverable_trip_id():
    app = (ENGINE_ROOT / "client-public" / "src" / "App.tsx").read_text(encoding="utf-8")
    arrival = (PUBLIC_COMPONENTS / "TravelArrival.tsx").read_text(encoding="utf-8")
    recovery = (PUBLIC_COMPONENTS / "TravelDepartureRecovery.tsx").read_text(encoding="utf-8")

    assert 'destination.pathname = `${destination.pathname.replace(/\\/$/, "")}/travel/arrive`' in app
    assert 'destination.searchParams.set("travel_id", departingTravelId)' in app
    assert 'searchParams.set("token"' not in app
    assert "postTravelArrival(travelId, sessionId)" in arrival
    assert "postRetryTravelDeparture(pending.travel_id)" in recovery
