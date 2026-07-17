from src.runtime.travel import TravelRequest, parse_world_travel


def test_travel_parser_distinguishes_world_travel_from_city_movement():
    assert parse_world_travel(
        "go home",
        allow_hearth=True,
    ) == TravelRequest("hearth")
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
