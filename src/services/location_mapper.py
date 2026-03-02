"""Location mapping service for converting location names to spatial coordinates."""

import hashlib
import logging
import re

logger = logging.getLogger(__name__)
from typing import Dict, Tuple, List, Optional
from dataclasses import dataclass


@dataclass
class LocationInfo:
    """Information about a location for coordinate assignment."""

    name: str
    category: str
    suggested_position: Tuple[int, int]
    adjacency_hints: List[str]


class LocationMapper:
    """Maps location names to spatial coordinates using semantic rules."""

    def __init__(self):
        self.location_cache: Dict[str, Tuple[int, int]] = {}
        self.location_patterns = self._initialize_location_patterns()

    def _initialize_location_patterns(self) -> Dict[str, LocationInfo]:
        """Initialize semantic patterns for common location types."""
        return {
            # Central/Hub locations (origin area)
            "starting_area": LocationInfo("starting_area", "hub", (0, 0), []),
            "center": LocationInfo("center", "hub", (0, 0), []),
            "hub": LocationInfo("hub", "hub", (0, 0), []),
            "plaza": LocationInfo("plaza", "hub", (0, 0), []),
            "square": LocationInfo("square", "hub", (0, 0), []),
            "courtyard": LocationInfo("courtyard", "hub", (0, 0), []),
            "main_hall": LocationInfo("main_hall", "hub", (0, 0), []),
            # Northern locations (negative Y)
            "north": LocationInfo("north", "direction", (0, -2), []),
            "northern": LocationInfo("northern", "direction", (0, -2), []),
            "mountain": LocationInfo("mountain", "nature", (0, -3), ["peak", "summit"]),
            "peak": LocationInfo("peak", "nature", (0, -4), ["mountain"]),
            "summit": LocationInfo("summit", "nature", (0, -4), ["mountain"]),
            "highlands": LocationInfo("highlands", "nature", (0, -3), ["mountain"]),
            "tower": LocationInfo(
                "tower", "structure", (0, -2), ["castle", "fortress"]
            ),
            # Southern locations (positive Y)
            "south": LocationInfo("south", "direction", (0, 2), []),
            "southern": LocationInfo("southern", "direction", (0, 2), []),
            "valley": LocationInfo("valley", "nature", (0, 3), ["river", "stream"]),
            "lowlands": LocationInfo("lowlands", "nature", (0, 3), ["valley"]),
            "swamp": LocationInfo("swamp", "nature", (0, 4), ["marsh", "bog"]),
            "marsh": LocationInfo("marsh", "nature", (0, 4), ["swamp"]),
            "bog": LocationInfo("bog", "nature", (0, 4), ["swamp"]),
            # Eastern locations (positive X)
            "east": LocationInfo("east", "direction", (2, 0), []),
            "eastern": LocationInfo("eastern", "direction", (2, 0), []),
            "sunrise": LocationInfo("sunrise", "direction", (3, 0), []),
            "dawn": LocationInfo("dawn", "direction", (3, 0), []),
            "coast": LocationInfo("coast", "nature", (4, 0), ["shore", "beach"]),
            "shore": LocationInfo("shore", "nature", (4, 0), ["coast", "beach"]),
            "beach": LocationInfo("beach", "nature", (4, 0), ["coast", "shore"]),
            # Western locations (negative X)
            "west": LocationInfo("west", "direction", (-2, 0), []),
            "western": LocationInfo("western", "direction", (-2, 0), []),
            "sunset": LocationInfo("sunset", "direction", (-3, 0), []),
            "dusk": LocationInfo("dusk", "direction", (-3, 0), []),
            "forest": LocationInfo("forest", "nature", (-3, 0), ["woods", "grove"]),
            "woods": LocationInfo("woods", "nature", (-3, 0), ["forest"]),
            "grove": LocationInfo("grove", "nature", (-2, 0), ["forest"]),
            # Diagonal locations
            "northeast": LocationInfo("northeast", "direction", (2, -2), []),
            "northwest": LocationInfo("northwest", "direction", (-2, -2), []),
            "southeast": LocationInfo("southeast", "direction", (2, 2), []),
            "southwest": LocationInfo("southwest", "direction", (-2, 2), []),
            # Settlement locations (spread around center)
            "tavern": LocationInfo("tavern", "settlement", (-1, 1), ["inn", "pub"]),
            "inn": LocationInfo("inn", "settlement", (-1, 1), ["tavern"]),
            "pub": LocationInfo("pub", "settlement", (-1, 1), ["tavern"]),
            "market": LocationInfo("market", "settlement", (1, 1), ["shop", "vendor"]),
            "shop": LocationInfo("shop", "settlement", (1, 1), ["market"]),
            "vendor": LocationInfo("vendor", "settlement", (1, 1), ["market"]),
            "forge": LocationInfo(
                "forge", "settlement", (1, -1), ["smithy", "workshop"]
            ),
            "smithy": LocationInfo("smithy", "settlement", (1, -1), ["forge"]),
            "workshop": LocationInfo("workshop", "settlement", (1, -1), ["forge"]),
            "temple": LocationInfo(
                "temple", "settlement", (-1, -1), ["shrine", "altar"]
            ),
            "shrine": LocationInfo("shrine", "settlement", (-1, -1), ["temple"]),
            "altar": LocationInfo("altar", "settlement", (-1, -1), ["temple"]),
            "castle": LocationInfo(
                "castle", "settlement", (0, -1), ["fortress", "palace"]
            ),
            "fortress": LocationInfo("fortress", "settlement", (0, -1), ["castle"]),
            "palace": LocationInfo("palace", "settlement", (0, -1), ["castle"]),
            # Underground/hidden locations (far from center)
            "cave": LocationInfo("cave", "underground", (-4, -1), ["cavern", "grotto"]),
            "cavern": LocationInfo("cavern", "underground", (-4, -1), ["cave"]),
            "grotto": LocationInfo("grotto", "underground", (-4, -1), ["cave"]),
            "dungeon": LocationInfo(
                "dungeon", "underground", (-4, 2), ["crypt", "tomb"]
            ),
            "crypt": LocationInfo("crypt", "underground", (-4, 2), ["dungeon"]),
            "tomb": LocationInfo("tomb", "underground", (-4, 2), ["dungeon"]),
            "underground": LocationInfo(
                "underground", "underground", (-4, 0), ["depths"]
            ),
            "depths": LocationInfo("depths", "underground", (-4, 0), ["underground"]),
            # Water locations (eastern bias)
            "river": LocationInfo("river", "water", (2, 1), ["stream", "brook"]),
            "stream": LocationInfo("stream", "water", (2, 1), ["river"]),
            "brook": LocationInfo("brook", "water", (2, 1), ["river"]),
            "lake": LocationInfo("lake", "water", (3, 2), ["pond"]),
            "pond": LocationInfo("pond", "water", (3, 2), ["lake"]),
            "waterfall": LocationInfo("waterfall", "water", (3, -2), ["cascade"]),
            "cascade": LocationInfo("cascade", "water", (3, -2), ["waterfall"]),
        }

    def assign_coordinates_to_storylets(self, storylets: List[Dict]) -> List[Dict]:
        """Assign spatial coordinates to storylets based on their location requirements."""
        self.location_cache.clear()  # Fresh start for each world

        # First pass: identify all unique locations
        locations = set()
        for storylet in storylets:
            requires = storylet.get("requires", {})
            location = requires.get("location")
            if isinstance(location, str):
                locations.add(location.lower().strip())

        # Assign coordinates to each location
        location_coords = {}
        used_positions = set()

        for location in locations:
            coords = self._get_coordinates_for_location(location, used_positions)
            location_coords[location] = coords
            used_positions.add(coords)

        # Second pass: update storylets with coordinates
        updated_storylets = []
        for storylet in storylets:
            updated = storylet.copy()
            requires = storylet.get("requires", {})
            location = requires.get("location")

            if isinstance(location, str):
                location_key = location.lower().strip()
                if location_key in location_coords:
                    x, y = location_coords[location_key]
                    updated["spatial_x"] = x
                    updated["spatial_y"] = y
                    logger.info(f"📍 Assigned ({x}, {y}) to location '{location}'")

            updated_storylets.append(updated)

        return updated_storylets

    def _get_coordinates_for_location(
        self, location: str, used_positions: set
    ) -> Tuple[int, int]:
        """Get coordinates for a specific location name."""
        location = location.lower().strip()

        # Check if we've already assigned this location
        if location in self.location_cache:
            return self.location_cache[location]

        # Try exact pattern match first
        if location in self.location_patterns:
            base_coords = self.location_patterns[location].suggested_position
        else:
            # Try partial matches
            base_coords = self._find_partial_match(location)

        # Ensure position is free
        final_coords = self._find_free_position(base_coords, used_positions)

        # Cache the result
        self.location_cache[location] = final_coords

        return final_coords

    def _find_partial_match(self, location: str) -> Tuple[int, int]:
        """Find coordinates using partial string matching."""
        location_words = set(re.findall(r"\w+", location.lower()))

        best_match = None
        best_score = 0

        for pattern_name, pattern_info in self.location_patterns.items():
            pattern_words = set(re.findall(r"\w+", pattern_name.lower()))

            # Calculate word overlap score
            common_words = location_words.intersection(pattern_words)
            if common_words:
                score = len(common_words) / len(pattern_words)
                if score > best_score:
                    best_score = score
                    best_match = pattern_info

        if best_match:
            return best_match.suggested_position

        # Fallback: generate deterministic coordinates from hash
        return self._hash_to_coordinates(location)

    def _hash_to_coordinates(self, location: str) -> Tuple[int, int]:
        """Generate deterministic coordinates from location name hash."""
        # Create a hash of the location name
        hash_obj = hashlib.md5(location.encode())
        hash_int = int(hash_obj.hexdigest()[:8], 16)

        # Convert to coordinates in reasonable range (-10 to 10)
        x = (hash_int % 21) - 10
        y = ((hash_int // 21) % 21) - 10

        return (x, y)

    def _find_free_position(
        self, preferred: Tuple[int, int], used_positions: set
    ) -> Tuple[int, int]:
        """Find the nearest free position to the preferred coordinates."""
        x, y = preferred

        if (x, y) not in used_positions:
            return (x, y)

        # Spiral outward to find free position
        for radius in range(1, 20):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    if abs(dx) == radius or abs(dy) == radius:  # Only check perimeter
                        candidate = (x + dx, y + dy)
                        if candidate not in used_positions:
                            return candidate

        # Ultimate fallback
        return (x + 20, y + 20)

    def get_location_map(self) -> Dict[str, Tuple[int, int]]:
        """Get the current location to coordinate mapping."""
        return self.location_cache.copy()

    def visualize_locations(self, locations: Dict[str, Tuple[int, int]]) -> str:
        """Create a simple ASCII visualization of location placement."""
        if not locations:
            return "No locations mapped."

        # Find bounds
        min_x = min(coords[0] for coords in locations.values())
        max_x = max(coords[0] for coords in locations.values())
        min_y = min(coords[1] for coords in locations.values())
        max_y = max(coords[1] for coords in locations.values())

        # Create grid
        width = max_x - min_x + 1
        height = max_y - min_y + 1
        grid = [["." for _ in range(width)] for _ in range(height)]

        # Place locations
        location_list = []
        for i, (location, (x, y)) in enumerate(locations.items()):
            grid_x = x - min_x
            grid_y = y - min_y
            symbol = str(i % 10)
            grid[grid_y][grid_x] = symbol
            location_list.append(f"{symbol}: {location} ({x}, {y})")

        # Create visualization
        lines = ["Location Map:"]
        for row in grid:
            lines.append("".join(row))
        lines.append("")
        lines.extend(location_list)

        return "\n".join(lines)
