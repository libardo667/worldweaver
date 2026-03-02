"""Tests for src/services/location_mapper.py."""

from src.services.location_mapper import LocationMapper


class TestLocationMapper:

    def _make(self):
        return LocationMapper()

    # -- Exact pattern matches --

    def test_exact_match_forest(self):
        mapper = self._make()
        coords = mapper._get_coordinates_for_location("forest", set())
        assert coords == (-3, 0)

    def test_exact_match_cave(self):
        mapper = self._make()
        coords = mapper._get_coordinates_for_location("cave", set())
        assert coords == (-4, -1)

    def test_exact_match_hub(self):
        mapper = self._make()
        coords = mapper._get_coordinates_for_location("hub", set())
        assert coords == (0, 0)

    # -- Partial matches --

    def test_partial_match_via_word_overlap(self):
        mapper = self._make()
        # "dark forest" (space-separated) splits into {"dark", "forest"}
        # which overlaps with the "forest" pattern
        coords = mapper._get_coordinates_for_location("dark forest", set())
        assert coords == (-3, 0)

    def test_underscore_names_fall_through_to_hash(self):
        mapper = self._make()
        # "dark_forest" is a single \w+ token — no overlap with "forest"
        coords = mapper._get_coordinates_for_location("dark_forest", set())
        # Falls through to hash, so just verify it returns valid coords
        assert isinstance(coords, tuple) and len(coords) == 2

    # -- Hash fallback --

    def test_hash_fallback_for_unknown(self):
        mapper = self._make()
        coords = mapper._get_coordinates_for_location("xylophonic_nexus", set())
        assert isinstance(coords, tuple)
        assert len(coords) == 2
        assert -10 <= coords[0] <= 10
        assert -10 <= coords[1] <= 10

    def test_hash_is_deterministic(self):
        m1 = self._make()
        m2 = self._make()
        assert m1._hash_to_coordinates("test_loc") == m2._hash_to_coordinates("test_loc")

    # -- Collision avoidance --

    def test_collision_avoidance(self):
        mapper = self._make()
        used = {(0, 0)}
        coords = mapper._find_free_position((0, 0), used)
        assert coords != (0, 0)
        assert coords not in used

    def test_collision_avoidance_spiral(self):
        mapper = self._make()
        # Fill up center area
        used = {(x, y) for x in range(-1, 2) for y in range(-1, 2)}
        coords = mapper._find_free_position((0, 0), used)
        assert coords not in used

    # -- assign_coordinates_to_storylets --

    def test_assign_coordinates_mutates_input(self):
        mapper = self._make()
        storylets = [
            {"title": "Forest Path", "requires": {"location": "forest"}},
            {"title": "Cave Entrance", "requires": {"location": "cave"}},
        ]
        result = mapper.assign_coordinates_to_storylets(storylets)
        assert result[0]["spatial_x"] == -3
        assert result[0]["spatial_y"] == 0
        assert "spatial_x" in result[1]

    def test_assign_no_location_leaves_unchanged(self):
        mapper = self._make()
        storylets = [{"title": "No Location", "requires": {"has_key": True}}]
        result = mapper.assign_coordinates_to_storylets(storylets)
        assert "spatial_x" not in result[0]

    # -- Cache --

    def test_cache_returns_same_coords(self):
        mapper = self._make()
        c1 = mapper._get_coordinates_for_location("forest", set())
        c2 = mapper._get_coordinates_for_location("forest", set())
        assert c1 == c2

    # -- Visualization --

    def test_visualize_empty(self):
        mapper = self._make()
        result = mapper.visualize_locations({})
        assert result == "No locations mapped."

    def test_visualize_produces_grid(self):
        mapper = self._make()
        locations = {"forest": (-3, 0), "cave": (-4, -1), "hub": (0, 0)}
        result = mapper.visualize_locations(locations)
        assert "Location Map:" in result
        assert "forest" in result
        assert "cave" in result

    # -- get_location_map --

    def test_get_location_map_returns_copy(self):
        mapper = self._make()
        mapper._get_coordinates_for_location("forest", set())
        map_copy = mapper.get_location_map()
        assert "forest" in map_copy
        # Modifying copy shouldn't affect original
        map_copy["forest"] = (999, 999)
        assert mapper.location_cache["forest"] != (999, 999)
