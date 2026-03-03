"""Spatial navigation system for storylets with 8-directional movement."""

import json
import logging
import math

logger = logging.getLogger(__name__)
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import text

from .embedding_service import cosine_similarity, embed_text
from .db_json import dumps_if_dict, safe_json_dict
from .requirements import evaluate_requirements


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
_DEFAULT_SEMANTIC_FLOOR = 0.05
_LEAD_LIMIT = 8
_PHYSICAL_WEIGHT = 0.3
_SEMANTIC_WEIGHT = 0.55
_DIRECTIONAL_WEIGHT = 0.15


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
            requires = safe_json_dict(requires_json)
            location = requires.get("location")
            if location:
                storylets_to_fix.append(
                    {
                        "id": id_val,
                        "title": title,
                        "requires": requires,
                        "choices": [],
                        "weight": 1.0,
                        "position": safe_json_dict(position_json) or None,
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
                    {"position": dumps_if_dict(position), "id": storylet_id},
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
        self.storylet_positions.clear()
        self.position_storylets.clear()
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
                position = safe_json_dict(position_json)
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

        positions_assigned: Dict[int, Position] = {}
        try:
            # Place storylets at their assigned coordinates
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
                        "Placed '%s' at (%s, %s)",
                        title,
                        final_position.x,
                        final_position.y,
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
                    "Using connection-based placement for %s unplaced storylets",
                    len(unplaced_storylets),
                )
                self._place_by_connections(unplaced_storylets, storylet_map, start_pos)

            self.db.commit()
            return self.storylet_positions
        except Exception:
            self.db.rollback()
            self._load_positions()
            raise

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
                set_obj = self._choice_set(choice)
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
            choice_set = self._choice_set(choice)
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
                        "requires": safe_json_dict(row[3]),
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
        return evaluate_requirements(requirements, player_vars)

    def _choice_set(self, choice: Any) -> Dict[str, Any]:
        """Normalize choice mutations for spatial navigation wiring."""
        if not isinstance(choice, dict):
            return {}
        set_values = choice.get("set")
        if isinstance(set_values, dict):
            return set_values
        legacy_set_values = choice.get("set_vars")
        if isinstance(legacy_set_values, dict):
            return legacy_set_values
        return {}

    def _normalize_embedding(self, value: Any) -> Optional[List[float]]:
        if isinstance(value, list):
            try:
                return [float(x) for x in value]
            except Exception:
                return None
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return None
            if isinstance(parsed, list):
                try:
                    return [float(x) for x in parsed]
                except Exception:
                    return None
        return None

    def _direction_for_offset(self, dx: float, dy: float) -> str:
        if dx == 0.0 and dy == 0.0:
            return "north"

        mag = math.sqrt((dx * dx) + (dy * dy))
        if mag == 0.0:
            return "north"

        best_name = "north"
        best_score = -1.0
        for name, direction in DIRECTIONS.items():
            dmag = math.sqrt((direction.dx * direction.dx) + (direction.dy * direction.dy))
            if dmag == 0.0:
                continue
            dot = ((dx / mag) * (direction.dx / dmag)) + ((dy / mag) * (direction.dy / dmag))
            if dot > best_score:
                best_score = dot
                best_name = name
        return best_name

    def _direction_alignment(
        self,
        preferred_direction: Optional[str],
        dx: float,
        dy: float,
    ) -> float:
        if not preferred_direction:
            return 1.0

        direction_key = preferred_direction.lower()
        if direction_key not in DIRECTIONS:
            return 0.0

        mag = math.sqrt((dx * dx) + (dy * dy))
        if mag == 0.0:
            return 0.0

        preferred = DIRECTIONS[direction_key]
        pmag = math.sqrt((preferred.dx * preferred.dx) + (preferred.dy * preferred.dy))
        if pmag == 0.0:
            return 0.0

        cosine = ((dx / mag) * (preferred.dx / pmag)) + ((dy / mag) * (preferred.dy / pmag))
        return max(0.0, cosine)

    def _lead_hint(self, direction: str, semantic_goal: Optional[str]) -> str:
        direction_title = direction.title()
        goal_text = str(semantic_goal or "").strip()
        if goal_text and "blacksmith" in goal_text.lower():
            return f"The sound of hammers rings from the {direction_title}."
        if goal_text:
            return f"Traces of {goal_text} seem strongest to the {direction_title}."
        return f"The strongest lead lies to the {direction_title}."

    def get_semantic_leads(
        self,
        current_storylet_id: int,
        player_vars: Dict[str, Any],
        context_vector: Optional[List[float]] = None,
        preferred_direction: Optional[str] = None,
        semantic_goal: Optional[str] = None,
        limit: int = _LEAD_LIMIT,
    ) -> List[Dict[str, Any]]:
        """Rank nearby narrative leads using semantic relevance and physical distance."""
        if current_storylet_id not in self.storylet_positions:
            return []

        current_pos = self.storylet_positions[current_storylet_id]
        leads: List[Dict[str, Any]] = []
        query = text(
            """
            SELECT id, title, text_template, requires, position, embedding
            FROM storylets
            WHERE position IS NOT NULL
        """
        )
        rows = self.db.execute(query).fetchall()

        effective_context = list(context_vector or [])
        if not effective_context and semantic_goal:
            effective_context = embed_text(semantic_goal)
        goal_vector = embed_text(semantic_goal) if semantic_goal else None

        for row in rows:
            storylet_id, title, text_val, requires_json, pos_json, embedding_json = row
            if storylet_id == current_storylet_id:
                continue

            position = safe_json_dict(pos_json)
            if not position or "x" not in position or "y" not in position:
                continue

            requirements = safe_json_dict(requires_json)
            if not self._check_requirements(requirements, player_vars):
                continue

            candidate_pos = Position(int(position["x"]), int(position["y"]))
            dx = float(candidate_pos.x - current_pos.x)
            dy = float(candidate_pos.y - current_pos.y)
            distance = current_pos.distance_to(candidate_pos)
            physical_score = 1.0 / (1.0 + distance)
            direction_name = self._direction_for_offset(dx, dy)
            directional_score = self._direction_alignment(preferred_direction, dx, dy)

            embedding = self._normalize_embedding(embedding_json)
            semantic_score = _DEFAULT_SEMANTIC_FLOOR
            if embedding and effective_context and len(embedding) == len(effective_context):
                semantic_score = max(
                    semantic_score,
                    cosine_similarity(effective_context, embedding),
                )
            if embedding and goal_vector and len(embedding) == len(goal_vector):
                semantic_score = max(
                    semantic_score,
                    cosine_similarity(goal_vector, embedding),
                )

            blended_score = (
                (semantic_score * _SEMANTIC_WEIGHT)
                + (physical_score * _PHYSICAL_WEIGHT)
                + (directional_score * _DIRECTIONAL_WEIGHT)
            )

            leads.append(
                {
                    "id": int(storylet_id),
                    "title": str(title),
                    "direction": direction_name,
                    "distance": round(float(distance), 3),
                    "semantic_score": round(float(semantic_score), 4),
                    "blended_score": round(float(blended_score), 4),
                    "score": round(float(blended_score), 4),
                    "position": {"x": candidate_pos.x, "y": candidate_pos.y},
                    "hint": self._lead_hint(direction_name, semantic_goal),
                    "text": str(text_val)[:100] + "..." if len(str(text_val)) > 100 else str(text_val),
                }
            )

        leads.sort(key=lambda lead: (-lead["blended_score"], lead["distance"], lead["title"]))
        return leads[: max(1, int(limit))]

    def get_semantic_goal_hint(
        self,
        current_storylet_id: int,
        player_vars: Dict[str, Any],
        semantic_goal: str,
        context_vector: Optional[List[float]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Resolve a single best lead and hint line for a semantic destination."""
        leads = self.get_semantic_leads(
            current_storylet_id=current_storylet_id,
            player_vars=player_vars,
            context_vector=context_vector,
            semantic_goal=semantic_goal,
            limit=1,
        )
        if not leads:
            return None

        best = leads[0]
        return {
            "direction": best["direction"],
            "hint": best["hint"],
            "lead": best,
        }

    def get_navigation_options(
        self,
        current_storylet_id: int,
        player_vars: Dict[str, Any],
        context_vector: Optional[List[float]] = None,
        preferred_direction: Optional[str] = None,
        semantic_goal: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build navigation metadata for a storylet.

        Returns a dict with:
          - position: {x, y} of the current storylet
          - directions: list of direction names with a reachable target
          - available_directions: full map of direction -> target info or None
          - leads: ranked semantic+spatial leads
        """
        directions = self.get_directional_navigation(current_storylet_id)
        available_directions: Dict[str, Any] = {}
        for direction, target in directions.items():
            if target is None:
                available_directions[direction] = None
            else:
                can_access = self.can_move_to_direction(
                    current_storylet_id, direction, player_vars
                )
                available_directions[direction] = {
                    **target,
                    "accessible": can_access,
                    "reason": "Requirements not met" if not can_access else None,
                }

        pos = self.storylet_positions.get(
            current_storylet_id, Position(0, 0)
        )
        directions_list = [
            d
            for d, t in available_directions.items()
            if t is not None and bool(t.get("accessible"))
        ]
        leads = self.get_semantic_leads(
            current_storylet_id=current_storylet_id,
            player_vars=player_vars,
            context_vector=context_vector,
            preferred_direction=preferred_direction,
            semantic_goal=semantic_goal,
        )

        return {
            "position": {"x": pos.x, "y": pos.y},
            "directions": directions_list,
            "available_directions": available_directions,
            "leads": leads,
        }

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
                        "requires": safe_json_dict(row[2]),
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
