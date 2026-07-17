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


def test_travel_readiness_counts_only_available_routes_and_live_nodes(tmp_path, monkeypatch):
    city = _shard(tmp_path, "ww_sfo", shard_type="city", city_id="san_francisco")
    monkeypatch.setattr(
        dev,
        "_request_json",
        lambda _url: {
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
        },
    )

    status = dev._city_travel_readiness(city)

    assert status.ready is True
    assert status.route_count == 2
    assert status.available_route_count == 1
    assert status.live_node_count == 1


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
        lambda _city: dev.TravelReadiness(True, True, True, 1, 1, 1),
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
        lambda _city: dev.TravelReadiness(True, True, True, 2, 0, 0),
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
