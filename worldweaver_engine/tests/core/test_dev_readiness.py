import json
from pathlib import Path

from scripts import dev


def _shard(tmp_path: Path, name: str, *, shard_type: str, city_id: str = "", shard_id: str = "") -> dev.ShardSpec:
    shard_dir = tmp_path / name
    shard_dir.mkdir()
    env_file = shard_dir / ".env"
    env_file.write_text(
        "\n".join(
            line
            for line in (
                f"SHARD_TYPE={shard_type}",
                f"CITY_ID={city_id}" if city_id else "",
                f"SHARD_ID={shard_id}" if shard_id else "",
                "BACKEND_PORT=8002",
            )
            if line
        ),
        encoding="utf-8",
    )
    compose_file = shard_dir / "docker-compose.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    return dev.ShardSpec(
        dir_name=name,
        shard_dir=shard_dir,
        compose_file=compose_file,
        env_file=env_file,
        shard_type=shard_type,
        shard_id=shard_id or None,
        city_id=city_id or None,
        backend_port="8002",
    )


def test_registry_identity_matches_the_engine_legacy_fallback(tmp_path):
    legacy = _shard(tmp_path, "ww_pdx", shard_type="city", city_id="portland")
    explicit = _shard(tmp_path, "cooperative_node", shard_type="city", city_id="portland", shard_id="rose-city-coop-1")

    assert dev._registry_shard_id(legacy) == "portland"
    assert dev._registry_shard_id(explicit) == "rose-city-coop-1"


def test_all_city_start_uses_one_canonical_directory_per_registry_identity(tmp_path):
    canonical = _shard(tmp_path, "ww_pdx", shard_type="city", city_id="portland")
    duplicate = _shard(tmp_path, "ww_pdx_variant", shard_type="city", city_id="portland")
    alderbank = _shard(tmp_path, "ww_alderbank", shard_type="city", city_id="alderbank", shard_id="ww_alderbank")

    assert dev._ordered_unique_city_shards([duplicate, alderbank, canonical]) == [alderbank, canonical]


def test_registration_refreshes_when_human_client_url_is_stale(tmp_path):
    city = _shard(tmp_path, "ww_sfo", shard_type="city", city_id="san_francisco")
    current = {
        "status": "healthy",
        "shard_url": "http://host.docker.internal:8002",
        "client_url": "",
    }

    assert dev._registration_needs_refresh(current, city) is True
    current["client_url"] = "http://localhost:5174/ww-sfo"
    assert dev._registration_needs_refresh(current, city) is False


def test_client_routes_keep_browser_traffic_off_runtime_only_node_urls(tmp_path):
    canonical = _shard(tmp_path, "ww_pdx", shard_type="city", city_id="portland")
    duplicate = _shard(tmp_path, "ww_pdx_variant", shard_type="city", city_id="portland")
    alderbank = _shard(tmp_path, "ww_alderbank", shard_type="city", city_id="alderbank", shard_id="ww_alderbank")

    routes = json.loads(
        dev._client_shard_routes(
            [canonical, duplicate, alderbank],
            target_for=dev._docker_network_backend_url,
        )
    )

    assert routes["portland"] == {
        "prefix": "/ww-pdx",
        "target": "http://ww_pdx-backend:8000",
    }
    assert routes["ww_alderbank"] == {
        "prefix": "/ww-alderbank",
        "target": "http://ww_alderbank-backend:8000",
    }


def test_default_client_compose_runs_the_public_surface():
    compose = dev.CLIENT_COMPOSE_FILE.read_text(encoding="utf-8")

    assert "dockerfile: client-public/Dockerfile" in compose
    assert "./client-public:/app/client-public" in compose
    assert "public_client_node_modules:/app/client-public/node_modules" in compose
    assert '"5174:5174"' in compose
    assert "client/Dockerfile" not in compose


def test_weave_client_runs_public_client_against_selected_shard(tmp_path, monkeypatch):
    world = _shard(tmp_path, "ww_world", shard_type="world", shard_id="ww_world")
    city = _shard(tmp_path, "ww_alderbank", shard_type="city", city_id="alderbank", shard_id="ww_alderbank")
    commands: list[list[str]] = []
    monkeypatch.setattr(dev, "_load_shard_specs", lambda: [world, city])
    monkeypatch.setattr(dev, "_run", lambda command, **_kwargs: commands.append(command) or 0)

    result = dev.run_weave_client(city="ww_alderbank", lan=False)

    assert result == 0
    assert commands == [["npm", "--prefix", "client-public", "run", "dev"]]


def test_compose_resolution_rejects_unusable_path_placeholders(monkeypatch):
    monkeypatch.setattr(dev.shutil, "which", lambda command: f"/fake/{command}")
    monkeypatch.setattr(dev.subprocess, "call", lambda *_args, **_kwargs: 1)

    assert dev._resolve_compose_command() is None


def test_compose_resolution_can_fall_back_to_a_working_legacy_binary(monkeypatch):
    monkeypatch.setattr(dev.shutil, "which", lambda command: f"/fake/{command}")
    results = iter([1, 0])
    monkeypatch.setattr(dev.subprocess, "call", lambda *_args, **_kwargs: next(results))

    assert dev._resolve_compose_command() == ["docker-compose"]


def test_federation_registration_waits_for_a_real_pulse(tmp_path, monkeypatch):
    world = _shard(tmp_path, "ww_world", shard_type="world", shard_id="ww_world")
    city = _shard(tmp_path, "ww_sfo", shard_type="city", city_id="san_francisco")
    entries = iter(
        [
            {"status": "offline"},
            {"status": "healthy"},
        ]
    )
    monkeypatch.setattr(dev, "_registered_shard_entry", lambda _world, _city: next(entries))
    monkeypatch.setattr(dev.time, "sleep", lambda _seconds: None)

    assert dev._wait_for_federation_registration(world, city, timeout_seconds=1) is True


def test_travel_readiness_counts_only_available_routes_and_live_nodes(tmp_path, monkeypatch):
    city = _shard(tmp_path, "ww_sfo", shard_type="city", city_id="san_francisco")

    def request_json(url, **_kwargs):
        if url.endswith("/health"):
            return {"status": "healthy"}
        return {
            "registry": {"configured": True, "reachable": True},
            "destinations": [
                {
                    "availability": "available",
                    "nodes": [
                        {"shard_id": "rose-city-coop-1", "shard_url": "https://pdx.example", "status": "healthy"},
                        {"shard_id": "offline-copy", "shard_url": "https://offline.example", "status": "offline"},
                    ],
                },
                {"availability": "unhosted", "nodes": []},
            ],
        }

    monkeypatch.setattr(
        dev,
        "_request_json",
        request_json,
    )

    status = dev._city_travel_readiness(city)

    assert status.ready is True
    assert status.route_count == 2
    assert status.available_route_count == 1
    assert status.live_node_count == 1
    assert status.reachable_node_count == 1


def test_travel_readiness_rejects_an_advertised_node_that_does_not_answer(tmp_path, monkeypatch):
    city = _shard(tmp_path, "ww_sfo", shard_type="city", city_id="san_francisco")

    def request_json(url, **_kwargs):
        if url.endswith("/health"):
            raise OSError("destination unavailable")
        return {
            "registry": {"configured": True, "reachable": True},
            "destinations": [
                {
                    "availability": "available",
                    "nodes": [
                        {"shard_id": "rose-city-coop-1", "shard_url": "https://pdx.example", "status": "healthy"},
                    ],
                }
            ],
        }

    monkeypatch.setattr(dev, "_request_json", request_json)

    status = dev._city_travel_readiness(city)

    assert status.live_node_count == 1
    assert status.reachable_node_count == 0
    assert status.ready is False


def test_local_registration_advertises_the_docker_host_address(tmp_path, monkeypatch):
    world = _shard(tmp_path, "ww_world", shard_type="world", shard_id="ww_world")
    city = _shard(tmp_path, "ww_sfo", shard_type="city", city_id="san_francisco", shard_id="bay-node-1")
    requests = []

    def request_json(url, **kwargs):
        requests.append((url, kwargs))
        return {}

    monkeypatch.setattr(dev, "_request_json", request_json)

    assert dev._register_city_shard(world, city, dry_run=False) is True
    assert requests[0][1]["payload"]["shard_url"] == "http://host.docker.internal:8002"
    assert requests[0][1]["payload"]["client_url"] == "http://localhost:5174/ww-sfo"


def test_agent_start_keeps_the_local_backend_address_override(tmp_path, monkeypatch):
    city = _shard(tmp_path, "ww_sfo", shard_type="city", city_id="san_francisco")
    compose_calls = []
    monkeypatch.setattr(dev, "_compose", lambda *args, **kwargs: compose_calls.append((args, kwargs)) or 0)

    assert dev._restart_city_agent(["docker", "compose"], city, build=False, env={"WW_EMBEDDING_URL": "http://embedder"}) == 0
    assert compose_calls[0][1]["env"] == {
        "WW_RUNTIME_PUBLIC_URL": "http://host.docker.internal:8002",
        "WW_EMBEDDING_URL": "http://embedder",
    }


def test_automatic_city_seed_cannot_reset_world_or_resident_state(tmp_path, monkeypatch):
    city = _shard(tmp_path, "ww_sfo", shard_type="city", city_id="san_francisco")
    commands: list[tuple[list[str], Path]] = []
    monkeypatch.setattr(
        dev,
        "_run",
        lambda command, *, cwd=None, **_kwargs: commands.append((command, cwd)) or 0,
    )

    assert dev._seed_city_shard(city, dry_run=False) == 0
    assert commands == [
        (
            [
                dev.sys.executable,
                "scripts/seed_world.py",
                "--shard-dir",
                str(city.shard_dir),
                "--no-reset",
                "--no-residents",
            ],
            dev.ROOT,
        )
    ]


def test_strict_status_passes_without_starting_or_inspecting_agents(tmp_path, monkeypatch, capsys):
    world = _shard(tmp_path, "ww_world", shard_type="world", shard_id="ww_world")
    city = _shard(tmp_path, "ww_sfo", shard_type="city", city_id="san_francisco", shard_id="bay-node-1")
    monkeypatch.setattr(dev, "_resolve_compose_command", lambda: ["docker", "compose"])
    monkeypatch.setattr(dev, "_load_shard_specs", lambda: [world, city])
    monkeypatch.setattr(dev, "_list_running_compose_projects", lambda _command: [{"Name": "ww_world"}, {"Name": "ww_sfo"}])
    monkeypatch.setattr(dev, "_wait_for_backend_health", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(dev, "_city_place_count", lambda _shard: 12)
    monkeypatch.setattr(
        dev,
        "_registered_shard_entry",
        lambda _world, _city: {"status": "healthy", "shard_url": "https://sfo.example"},
    )
    monkeypatch.setattr(
        dev,
        "_city_travel_readiness",
        lambda _city: dev.TravelReadiness(True, True, True, 1, 1, 1, 1),
    )

    result = dev.run_weave_status(city="ww_sfo", all_cities=False, strict=True, require_travel=True)

    assert result == 0
    assert "agent processes were not started or inspected" in capsys.readouterr().out


def test_strict_travel_status_fails_when_no_live_route_exists(tmp_path, monkeypatch):
    world = _shard(tmp_path, "ww_world", shard_type="world", shard_id="ww_world")
    city = _shard(tmp_path, "ww_sfo", shard_type="city", city_id="san_francisco", shard_id="bay-node-1")
    monkeypatch.setattr(dev, "_resolve_compose_command", lambda: ["docker", "compose"])
    monkeypatch.setattr(dev, "_load_shard_specs", lambda: [world, city])
    monkeypatch.setattr(dev, "_list_running_compose_projects", lambda _command: [{"Name": "ww_world"}, {"Name": "ww_sfo"}])
    monkeypatch.setattr(dev, "_wait_for_backend_health", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(dev, "_city_place_count", lambda _shard: 12)
    monkeypatch.setattr(
        dev,
        "_registered_shard_entry",
        lambda _world, _city: {"status": "healthy", "shard_url": "https://sfo.example"},
    )
    monkeypatch.setattr(
        dev,
        "_city_travel_readiness",
        lambda _city: dev.TravelReadiness(True, True, True, 2, 0, 0, 0),
    )

    assert dev.run_weave_status(city="ww_sfo", all_cities=False, strict=True, require_travel=True) == 1


def test_weave_up_keeps_agents_off_unless_explicitly_requested(tmp_path, monkeypatch, capsys):
    world = _shard(tmp_path, "ww_world", shard_type="world", shard_id="ww_world")
    city = _shard(tmp_path, "ww_sfo", shard_type="city", city_id="san_francisco", shard_id="bay-node-1")
    monkeypatch.setattr(dev, "_resolve_compose_command", lambda: ["docker", "compose"])
    monkeypatch.setattr(dev, "_load_shard_specs", lambda: [world, city])
    monkeypatch.setattr(dev, "_warn_for_running_project_conflicts", lambda **_kwargs: None)

    result = dev.run_weave_up(
        city="ww_sfo",
        build=False,
        include_client=False,
        start_agents=False,
        dry_run=True,
        all_cities=False,
    )

    output = capsys.readouterr().out
    assert result == 0
    assert "agents: not started" in output
    assert "dry-run agent command" not in output
    assert "up -d db backend" in output


def test_weave_up_stages_explicit_agents_after_readiness(tmp_path, monkeypatch, capsys):
    world = _shard(tmp_path, "ww_world", shard_type="world", shard_id="ww_world")
    city = _shard(tmp_path, "ww_sfo", shard_type="city", city_id="san_francisco", shard_id="bay-node-1")
    monkeypatch.setattr(dev, "_resolve_compose_command", lambda: ["docker", "compose"])
    monkeypatch.setattr(dev, "_load_shard_specs", lambda: [world, city])
    monkeypatch.setattr(dev, "_warn_for_running_project_conflicts", lambda **_kwargs: None)

    result = dev.run_weave_up(
        city="ww_sfo",
        build=False,
        include_client=False,
        start_agents=True,
        dry_run=True,
        all_cities=False,
    )

    output = capsys.readouterr().out
    assert result == 0
    assert "dry-run agent command after readiness" in output


def test_weave_up_does_not_start_agents_after_failed_registration(tmp_path, monkeypatch):
    def unexpected_agent_start(*_args, **_kwargs):
        raise AssertionError("agent start must remain unreachable")

    world = _shard(tmp_path, "ww_world", shard_type="world", shard_id="ww_world")
    city = _shard(tmp_path, "ww_sfo", shard_type="city", city_id="san_francisco", shard_id="bay-node-1")
    monkeypatch.setattr(dev, "_resolve_compose_command", lambda: ["docker", "compose"])
    monkeypatch.setattr(dev, "_load_shard_specs", lambda: [world, city])
    monkeypatch.setattr(dev, "_warn_for_running_project_conflicts", lambda **_kwargs: None)
    monkeypatch.setattr(dev, "_compose", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(dev, "_wait_for_backend_health", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(dev, "_city_is_seeded", lambda _shard: True)
    monkeypatch.setattr(dev, "_registered_shard_entry", lambda _world, _city: None)
    monkeypatch.setattr(dev, "_register_city_shard", lambda _world, _city, **_kwargs: False)
    monkeypatch.setattr(dev, "_restart_city_agent", unexpected_agent_start)

    result = dev.run_weave_up(
        city="ww_sfo",
        build=False,
        include_client=False,
        start_agents=True,
        dry_run=False,
        all_cities=False,
    )

    assert result == 1
