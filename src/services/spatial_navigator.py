"""Spatial navigation system for storylets with 8-directional movement."""

import json
import logging
import math

logger = logging.getLogger(__name__)
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import text


@dataclass
class Position:
    """Represents a position in 2D space."""

    x: int
    y: int

    def __hash__(self):
        return hash((self.x, self.y))

    def distance_to(self, other: "Position") -> float:
        """Calculate Euclidean distance to another position."""
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)


@dataclass
class Direction:
    """Represents a directional movement."""

    name: str
    dx: int
    dy: int
    symbol: str


# Define the 8 cardinal and intercardinal directions
DIRECTIONS = {
    "north": Direction("north", 0, -1, "↑"),
    "northeast": Direction("northeast", 1, -1, "↗"),
    "east": Direction("east", 1, 0, "→"),
    "southeast": Direction("southeast", 1, 1, "↘"),
    "south": Direction("south", 0, 1, "↓"),
    "southwest": Direction("southwest", -1, 1, "↙"),
    "west": Direction("west", -1, 0, "←"),
    "northwest": Direction("northwest", -1, -1, "↖"),
}


class SpatialNavigator:
    """Manages spatial relationships between storylets."""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.storylet_positions: Dict[int, Position] = {}
        self.position_storylets: Dict[Position, int] = {}
        self._load_positions()

    @staticmethod
    def auto_assign_coordinates(
        db_session: Session, storylet_ids: Optional[List[int]] = None
    ) -> int:
        """
        Automatically assign coordinates to storylets that have locations but no coordinates.

        Args:
            db_session: Database session
            storylet_ids: Optional list of specific storylet IDs to process. If None, processes all storylets.

        Returns:
            Number of storylets updated with coordinates
        """
        from .location_mapper import LocationMapper

        # Build query based on whether specific IDs are provided
        # Now, we check for position field being null or missing
        if storylet_ids:
            id_placeholders = ",".join([":id" + str(i) for i in range(len(storylet_ids))])
            query = f"""
                SELECT id, title, requires, position 
                FROM storylets 
                WHERE id IN ({id_placeholders})
                AND (position IS NULL OR json_type(position, '$.x') IS NULL OR json_type(position, '$.y') IS NULL)
                AND requires IS NOT NULL 
                AND requires != '{{}}'
            """
            params = {f"id{i}": storylet_id for i, storylet_id in enumerate(storylet_ids)}
            result = db_session.execute(text(query), params)
        else:
            result = db_session.execute(
                text(
                    """
                SELECT id, title, requires, position 
                FROM storylets 
                WHERE (position IS NULL OR json_type(position, '$.x') IS NULL OR json_type(position, '$.y') IS NULL)
                AND requires IS NOT NULL 
                AND requires != '{}'
            """
                )
            )

        storylets_to_fix = []
        for row in result.fetchall():
            id_val, title, requires_json, position_json = row
            try:
                requires = json.loads(requires_json) if requires_json else {}
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning("Bad requires JSON for storylet %s: %s", id_val, e)
                requires = {}
            location = requires.get("location")
            if location:
                storylets_to_fix.append(
                    {
                        "id": id_val,
                        "title": title,
                        "requires": requires,
                        "choices": [],
                        "weight": 1.0,
                        "position": json.loads(position_json) if position_json else None,
                    }
                )

        if not storylets_to_fix:
            return 0

        # Use LocationMapper to assign coordinates
        mapper = LocationMapper()
        storylets_with_coords = mapper.assign_coordinates_to_storylets(storylets_to_fix)

        # Update database with coordinates
        updates_made = 0
        for storylet_data in storylets_with_coords:
            if "position" in storylet_data and storylet_data["position"]:
                position = storylet_data["position"]
                storylet_id = storylet_data["id"]
                db_session.execute(
                    text(
                        """
                    UPDATE storylets 
                    SET position = :position 
                    WHERE id = :id
                """
                    ),
                    {"position": json.dumps(position), "id": storylet_id},
                )
                updates_made += 1

        if updates_made > 0:
            db_session.commit()
            logger.info(f"📍 Auto-assigned coordinates to {updates_made} storylets")

        return updates_made

    @staticmethod
    def ensure_all_coordinates(db_session: Session) -> int:
        """
        Ensure all storylets with locations have spatial coordinates.
        This is a convenience method for bulk operations.

        Returns:
            Number of storylets updated with coordinates
        """
        return SpatialNavigator.auto_assign_coordinates(db_session, None)

    def _load_positions(self):
        """Load storylet positions from database."""
        try:
            result = self.db.execute(
                text(
                    """
                SELECT id, position 
                FROM storylets 
                WHERE position IS NOT NULL
            """
                )
            )

            for row in result.fetchall():
                storylet_id, position_json = row
                try:
                    position = json.loads(position_json) if position_json else None
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning("Bad position JSON for storylet %s: %s", storylet_id, e)
                    position = None
                if position and "x" in position and "y" in position:
                    pos = Position(position["x"], position["y"])
                    self.storylet_positions[storylet_id] = pos
                    self.position_storylets[pos] = storylet_id

        except Exception as e:
            logger.warning(f"⚠️ Warning: Could not load spatial positions: {e}")
            # Initialize empty if table doesn't have spatial columns yet
            self.storylet_positions = {}
            self.position_storylets = {}

    def assign_spatial_positions(
        self, storylets: List[Dict[str, Any]], start_pos: Optional[Position] = None
    ) -> Dict[int, Position]:
        """Assign spatial positions to storylets based on their connections and locations."""
        if start_pos is None:
            start_pos = Position(0, 0)

        # Clear existing positions for new world generation
        self.storylet_positions.clear()
        self.position_storylets.clear()

        # Use LocationMapper to assign coordinates to storylets based on location names
        from .location_mapper import LocationMapper

        mapper = LocationMapper()
        storylets_with_coords = mapper.assign_coordinates_to_storylets(storylets)

        # Build title -> id map from database
        storylet_map: Dict[str, int] = {}
        cursor = self.db.execute(text("SELECT id, title FROM storylets"))
        for row in cursor.fetchall():
            storylet_map[row[1]] = row[0]

        if not storylets_with_coords:
            return {}

        # Place storylets at their assigned coordinates
        positions_assigned = {}
        for storylet_data in storylets_with_coords:
            title = storylet_data.get("title", "")
            storylet_id = storylet_map.get(title)

            if not storylet_id:
                continue

            # Use assigned coordinates if available
            if "spatial_x" in storylet_data and "spatial_y" in storylet_data:
                x, y = storylet_data["spatial_x"], storylet_data["spatial_y"]
                position = Position(x, y)

                # Ensure position is free (in case of conflicts)
                final_position = self._find_free_position(position)
                self._place_storylet(storylet_id, final_position)
                positions_assigned[storylet_id] = final_position

                logger.info(
                    f"📍 Placed '{title}' at ({final_position.x}, {final_position.y})"
                )

        # If we have storylets without coordinates, place them using the old algorithm
        unplaced_storylets = []
        for storylet_data in storylets_with_coords:
            title = storylet_data.get("title", "")
            storylet_id = storylet_map.get(title)

            if storylet_id and storylet_id not in positions_assigned:
                unplaced_storylets.append(storylet_data)

        if unplaced_storylets:
            logger.info(
                f"📍 Using connection-based placement for {len(unplaced_storylets)} unplaced storylets"
            )
            self._place_by_connections(unplaced_storylets, storylet_map, start_pos)

        return self.storylet_positions

    def _place_by_connections(
        self,
        storylets: List[Dict[str, Any]],
        storylet_map: Dict[str, int],
        start_pos: Position,
    ):
        """Place storylets using the connection-based algorithm for those without coordinates."""
        # Index storylets by required location
        location_index: Dict[str, List[int]] = {}
        id_list: List[int] = []
        for s in storylets:
            sid = storylet_map.get(s.get("title", ""))
            if not sid:
                continue
            id_list.append(sid)
            req = s.get("requires") or {}
            req_loc = req.get("location")
            if isinstance(req_loc, str):
                location_index.setdefault(req_loc, []).append(sid)

        # Build adjacency graph using both 'set' and legacy 'set_vars'
        adjacency: Dict[int, List[int]] = {sid: [] for sid in id_list}
        degree: Dict[int, int] = {sid: 0 for sid in id_list}
        for s in storylets:
            sid = storylet_map.get(s.get("title", ""))
            if not sid:
                continue
            for choice in s.get("choices") or []:
                set_obj = choice.get("set") or choice.get("set_vars") or {}
                target_loc = set_obj.get("location")
                if isinstance(target_loc, str):
                    for tid in location_index.get(target_loc, []):
                        if tid not in adjacency[sid]:
                            adjacency[sid].append(tid)
                            degree[sid] += 1

        # Choose a starting node: prefer one with highest degree, fallback to first
        starting_id: Optional[int] = None
        if degree:
            starting_id = max(degree.keys(), key=lambda k: degree[k])
        if starting_id is None and id_list:
            starting_id = id_list[0]
        if starting_id is None:
            return

        # BFS/spiral placement across the graph
        positioned: set[int] = set()
        to_position: List[Tuple[int, Position]] = [(starting_id, start_pos)]

        while to_position:
            node_id, pos = to_position.pop(0)
            if node_id in positioned:
                continue

            final_pos = self._find_free_position(pos)
            self._place_storylet(node_id, final_pos)
            positioned.add(node_id)

            # Enqueue neighbors
            for neighbor_id in adjacency.get(node_id, []):
                if neighbor_id not in positioned:
                    to_position.append(
                        (neighbor_id, self._suggest_nearby_position(final_pos))
                    )

        # Place any remaining disconnected nodes in a spiral around start
        for sid in id_list:
            if sid not in positioned:
                start_pos = self._find_free_position(start_pos)
                self._place_storylet(sid, start_pos)
                positioned.add(sid)

    def _find_free_position(self, preferred_pos: Position) -> Position:
        """Find the nearest free position to the preferred position."""
        if preferred_pos not in self.position_storylets:
            return preferred_pos

        # Spiral outward to find a free position
        for radius in range(1, 20):  # Max search radius
            for angle in range(0, 360, 45):  # Check 8 directions
                x = preferred_pos.x + int(radius * math.cos(math.radians(angle)))
                y = preferred_pos.y + int(radius * math.sin(math.radians(angle)))
                pos = Position(x, y)

                if pos not in self.position_storylets:
                    return pos

        # Fallback: use a random nearby position
        import random

        offset = random.randint(-10, 10)
        return Position(preferred_pos.x + offset, preferred_pos.y + offset)

    def _suggest_nearby_position(self, center: Position) -> Position:
        """Suggest a position near the center for connected storylets."""
        # Use the 8 cardinal directions for natural placement
        directions = list(DIRECTIONS.values())
        import random

        direction = random.choice(directions)

        return Position(center.x + direction.dx, center.y + direction.dy)

    def _place_storylet(self, storylet_id: int, position: Position):
        """Place a storylet at a specific position."""
        self.storylet_positions[storylet_id] = position
        self.position_storylets[position] = storylet_id

        # Update database (position is a JSON column)
        self.db.execute(
            text(
                """
            UPDATE storylets
            SET position = json_object('x', :x, 'y', :y)
            WHERE id = :id
        """
            ),
            {"x": position.x, "y": position.y, "id": storylet_id},
        )
        self.db.commit()

    def _get_connected_storylets(
        self, storylet_id: int, storylets: List[Dict], storylet_map: Dict[str, int]
    ) -> List[int]:
        """Get storylets that are connected to the given storylet through choices."""
        connected = []

        # Find the storylet data
        storylet_data = None
        for s in storylets:
            if storylet_map.get(s["title"]) == storylet_id:
                storylet_data = s
                break

        if not storylet_data:
            return connected

        # Check choices for location changes
        for choice in storylet_data.get("choices", []):
            # Support both normalized 'set' and legacy 'set_vars' keys
            choice_set = choice.get("set") or choice.get("set_vars") or {}
            if "location" in choice_set:
                target_location = choice_set["location"]

                # Find storylets that require this location
                for s in storylets:
                    if s.get("requires", {}).get("location") == target_location:
                        target_id = storylet_map.get(s["title"])
                        if target_id and target_id not in connected:
                            connected.append(target_id)

        return connected

    def get_directional_navigation(
        self, current_storylet_id: int
    ) -> Dict[str, Optional[Dict]]:
        """Get available navigation options in 8 directions from current position."""
        if current_storylet_id not in self.storylet_positions:
            return {direction: None for direction in DIRECTIONS.keys()}

        current_pos = self.storylet_positions[current_storylet_id]
        navigation = {}

        for direction_name, direction in DIRECTIONS.items():
            target_pos = Position(
                current_pos.x + direction.dx, current_pos.y + direction.dy
            )

            if target_pos in self.position_storylets:
                target_id = self.position_storylets[target_pos]

                # Get storylet details
                cursor = self.db.execute(
                    text(
                        """
                    SELECT id, title, text_template, requires 
                    FROM storylets 
                    WHERE id = :target_id
                """
                    ),
                    {"target_id": target_id},
                )

                row = cursor.fetchone()
                if row:
                    navigation[direction_name] = {
                        "id": row[0],
                        "title": row[1],
                        "text": row[2][:100] + "..." if len(row[2]) > 100 else row[2],
                        "requires": json.loads(row[3]) if row[3] else {},
                        "symbol": direction.symbol,
                        "position": {"x": target_pos.x, "y": target_pos.y},
                    }
                else:
                    navigation[direction_name] = None
            else:
                navigation[direction_name] = None

        return navigation

    def can_move_to_direction(
        self, current_storylet_id: int, direction: str, player_vars: Dict[str, Any]
    ) -> bool:
        """Check if the player can move in the specified direction."""
        nav_options = self.get_directional_navigation(current_storylet_id)
        target = nav_options.get(direction)

        if not target:
            return False

        # Check requirements
        requirements = target.get("requires", {})
        return self._check_requirements(requirements, player_vars)

    def _check_requirements(
        self, requirements: Dict[str, Any], player_vars: Dict[str, Any]
    ) -> bool:
        """Check if player variables meet the requirements."""
        for req_key, req_value in requirements.items():
            if req_key not in player_vars:
                return False

            player_value = player_vars[req_key]

            if isinstance(req_value, dict):
                # Handle operators like {'gte': 5}
                for op, val in req_value.items():
                    if op == "gte" and player_value < val:
                        return False
                    elif op == "lte" and player_value > val:
                        return False
                    elif op == "gt" and player_value <= val:
                        return False
                    elif op == "lt" and player_value >= val:
                        return False
            else:
                # Direct comparison
                if player_value != req_value:
                    return False

        return True

    def get_spatial_map_data(self) -> Dict[str, Any]:
        """Get data for rendering a spatial map."""
        storylets = []

        for storylet_id, position in self.storylet_positions.items():
            cursor = self.db.execute(
                text(
                    """
                SELECT title, text_template, requires 
                FROM storylets 
                WHERE id = :storylet_id
            """
                ),
                {"storylet_id": storylet_id},
            )

            row = cursor.fetchone()
            if row:
                storylets.append(
                    {
                        "id": storylet_id,
                        "title": row[0],
                        "text": row[1][:50] + "..." if len(row[1]) > 50 else row[1],
                        "requires": json.loads(row[2]) if row[2] else {},
                        "position": {"x": position.x, "y": position.y},
                    }
                )

        return {"storylets": storylets, "bounds": self._calculate_bounds()}

    def _calculate_bounds(self) -> Dict[str, int]:
        """Calculate the bounds of the spatial map."""
        if not self.storylet_positions:
            return {"min_x": 0, "max_x": 0, "min_y": 0, "max_y": 0}

        positions = list(self.storylet_positions.values())
        return {
            "min_x": min(pos.x for pos in positions),
            "max_x": max(pos.x for pos in positions),
            "min_y": min(pos.y for pos in positions),
            "max_y": max(pos.y for pos in positions),
        }
