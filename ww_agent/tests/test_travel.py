from src.runtime.travel import (
    TravelRequest,
    derive_pending_shard_travel,
    parse_city_travel,
    parse_world_travel,
)


def test_travel_parser_distinguishes_world_travel_from_city_movement():
    assert parse_world_travel(
        "go home",
        allow_hearth=True,
    ) == TravelRequest("hearth")
    assert parse_world_travel("home", allow_hearth=True) == TravelRequest("hearth")
    assert parse_world_travel("your hearth", allow_hearth=True) == TravelRequest(
        "hearth"
    )
    assert parse_world_travel(
        "travel to city",
        city_names={"city"},
        allow_hearth=False,
    ) == TravelRequest("city", "city")
    assert (
        parse_world_travel(
            "walk to the park",
            city_names={"city"},
            allow_hearth=True,
        )
        is None
    )


def test_home_is_not_a_destination_while_already_at_the_hearth():
    assert parse_world_travel("go home", allow_hearth=False) is None
    assert parse_world_travel("home", allow_hearth=False) is None


def test_city_travel_requires_one_explicit_live_node():
    destinations = [
        {
            "route_id": "sf-portland",
            "nodes": [
                {
                    "shard_id": "rose-city-coop-1",
                    "shard_url": "https://pdx.example",
                    "status": "healthy",
                },
                {
                    "shard_id": "offline-copy",
                    "shard_url": "https://offline.example",
                    "status": "offline",
                },
            ],
        }
    ]

    assert parse_city_travel(
        "travel to rose-city-coop-1", destinations
    ) == TravelRequest("city", "rose-city-coop-1", "sf-portland", "rose-city-coop-1")
    assert parse_city_travel("travel to not-rose-city-coop-1", destinations) is None
    assert parse_city_travel("travel to offline-copy", destinations) is None
    assert parse_city_travel("walk to the park", destinations) is None


def test_pending_city_travel_is_derived_from_the_ledger_until_arrival():
    started = {
        "event_type": "inter_shard_travel_started",
        "payload": {
            "travel_id": "trip-1",
            "transition_id": "transition-1",
            "route_id": "sf-portland",
            "source_url": "https://sf.example",
            "source_session_id": "source-session",
            "destination_shard": "rose-city-coop-1",
            "destination_session_id": "destination-session",
        },
    }
    departed = {
        "event_type": "inter_shard_source_departed",
        "payload": {"travel_id": "trip-1", "destination_url": "https://pdx.example"},
    }

    pending = derive_pending_shard_travel([started, departed])

    assert pending is not None and pending.source_departed is True
    assert pending.destination_url == "https://pdx.example"
    assert (
        derive_pending_shard_travel(
            [
                started,
                departed,
                {
                    "event_type": "inter_shard_travel_arrived",
                    "payload": {"travel_id": "trip-1"},
                },
            ]
        )
        is None
    )
