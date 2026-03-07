"""
Story Smoothing Algorithm
Automatically detects and fixes narrative flow problems in storylet graphs.
"""

import logging
import sqlite3
import json
import random
from collections import defaultdict
from typing import Dict, List, Tuple

from ..database import db_file as _default_db_file

logger = logging.getLogger(__name__)


class StorySmoother:
    """
    Recursive story graph analyzer and fixer.
    Detects isolated locations, dead-end variables, and navigation bottlenecks,
    then automatically generates fixes.
    """

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or _default_db_file
        self.storylets = []
        self.locations = set()
        self.location_storylets = defaultdict(list)
        self.location_connections = defaultdict(set)
        self.reverse_connections = defaultdict(set)
        self.variables_required = defaultdict(list)  # var -> storylets that need it
        self.variables_set = defaultdict(list)  # var -> storylets that set it
        self.dead_end_vars = set()
        self.isolated_locations = set()
        self.one_way_connections = set()

    def load_storylets(self):
        """Load all storylets from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, title, text_template, requires, choices, weight 
            FROM storylets
        """)

        self.storylets = []
        for row in cursor.fetchall():
            storylet = {
                "id": row[0],
                "title": row[1],
                "text": row[2],
                "requires": json.loads(row[3]) if row[3] else {},
                "choices": json.loads(row[4]) if row[4] else [],
                "weight": row[5],
            }
            self.storylets.append(storylet)

        conn.close()
        logger.info(f"📚 Loaded {len(self.storylets)} storylets")

    def analyze_graph(self):
        """Analyze the storylet graph for problems."""
        logger.info("🔍 Analyzing storylet graph...")

        # Reset analysis data
        self.locations.clear()
        self.location_storylets.clear()
        self.location_connections.clear()
        self.reverse_connections.clear()
        self.variables_required.clear()
        self.variables_set.clear()

        # Analyze each storylet
        for storylet in self.storylets:
            # Extract location
            location = storylet["requires"].get("location", "No Location")
            self.locations.add(location)
            self.location_storylets[location].append(storylet)

            # Track variable requirements
            for var, value in storylet["requires"].items():
                if var != "location":
                    self.variables_required[var].append(storylet)

            # Analyze choices for connections and variable setting
            for choice in storylet["choices"]:
                choice_sets = choice.get("set", {})

                # Track variables being set
                for var, value in choice_sets.items():
                    if var != "location":
                        self.variables_set[var].append((storylet, choice))

                # Track location connections
                new_location = choice_sets.get("location")
                if new_location and new_location != location:
                    self.location_connections[location].add(new_location)
                    self.reverse_connections[new_location].add(location)

        self._identify_problems()

    def _identify_problems(self):
        """Identify specific problems in the story graph."""
        # Find dead-end variables
        all_set_vars = set(self.variables_set.keys())
        all_required_vars = set(self.variables_required.keys())
        self.dead_end_vars = all_set_vars - all_required_vars

        # Find isolated locations (no incoming or outgoing connections)
        self.isolated_locations = set()
        for location in self.locations:
            has_outgoing = len(self.location_connections[location]) > 0
            has_incoming = len(self.reverse_connections[location]) > 0

            if not has_outgoing and not has_incoming and location != "No Location":
                self.isolated_locations.add(location)

        # Find one-way connections
        self.one_way_connections = set()
        for from_loc, to_locs in self.location_connections.items():
            for to_loc in to_locs:
                if from_loc not in self.location_connections.get(to_loc, set()):
                    self.one_way_connections.add((from_loc, to_loc))

        logger.warning(f"⚠️  Found {len(self.dead_end_vars)} dead-end variables")
        logger.warning(f"🏝️ Found {len(self.isolated_locations)} isolated locations")
        logger.warning(f"➡️  Found {len(self.one_way_connections)} one-way connections")

    def generate_exit_choices(self, storylet: Dict, target_locations: List[str]) -> List[Dict]:
        """Generate exit choices for a storylet to connect it to other locations."""
        exit_choices = []

        current_location = storylet["requires"].get("location", "No Location")

        for target_location in target_locations:
            if target_location != current_location:
                # Generate thematic choice text based on locations
                choice_text = self._generate_travel_text(current_location, target_location)

                exit_choice = {
                    "text": choice_text,
                    "set": {"location": target_location},
                    "condition": None,
                }
                exit_choices.append(exit_choice)

        return exit_choices

    def _generate_travel_text(self, from_loc: str, to_loc: str) -> str:
        """Generate thematic travel text between locations."""
        travel_phrases = {
            (
                "Clan Hall",
                "Neon Caverns",
            ): "Venture into the glowing depths of the caverns",
            (
                "Clan Hall",
                "Corporate Stronghold",
            ): "March toward the corporate district",
            ("Clan Hall", "Old Clan Library"): "Return to the ancient archives",
            ("Clan Hall", "Rusted Halls"): "Explore the abandoned industrial sector",
            ("Neon Caverns", "Clan Hall"): "Return to the clan gathering place",
            ("Neon Caverns", "Corporate Stronghold"): "Ascend to the corporate towers",
            ("Neon Caverns", "Old Clan Library"): "Seek knowledge in the old archives",
            ("Neon Caverns", "Rusted Halls"): "Investigate the rusted machinery",
            ("Corporate Stronghold", "Clan Hall"): "Retreat to clan territory",
            (
                "Corporate Stronghold",
                "Neon Caverns",
            ): "Descend into the neon-lit depths",
            (
                "Corporate Stronghold",
                "Old Clan Library",
            ): "Research in the ancient library",
            (
                "Corporate Stronghold",
                "Rusted Halls",
            ): "Investigate the industrial ruins",
            ("Old Clan Library", "Clan Hall"): "Return to the main clan area",
            (
                "Old Clan Library",
                "Neon Caverns",
            ): "Venture into the illuminated caverns",
            (
                "Old Clan Library",
                "Corporate Stronghold",
            ): "Confront the corporate power",
            ("Old Clan Library", "Rusted Halls"): "Explore the forgotten machinery",
            ("Rusted Halls", "Clan Hall"): "Head back to clan territory",
            ("Rusted Halls", "Neon Caverns"): "Enter the glowing underground",
            (
                "Rusted Halls",
                "Corporate Stronghold",
            ): "Challenge the corporate authority",
            ("Rusted Halls", "Old Clan Library"): "Consult the ancient texts",
        }

        # Try to find specific travel text
        specific_text = travel_phrases.get((from_loc, to_loc))
        if specific_text:
            return specific_text

        # Generate generic travel text
        generic_travels = [
            f"Travel to {to_loc}",
            f"Journey toward {to_loc}",
            f"Head to {to_loc}",
            f"Move to {to_loc}",
            f"Explore {to_loc}",
        ]

        return random.choice(generic_travels)

    def generate_variable_requirement_storylets(self) -> List[Dict]:
        """Generate new storylets that require the dead-end variables."""
        new_storylets = []

        for var in self.dead_end_vars:
            # Find where this variable is set to understand its purpose
            setting_storylets = self.variables_set[var]
            if not setting_storylets:
                continue

            # Analyze the variable to create thematic requirements
            storylet_title, storylet_text = self._generate_variable_storylet(var, setting_storylets)

            # Choose a location that makes sense for this variable
            target_location = self._choose_location_for_variable(var)

            new_storylet = {
                "title": storylet_title,
                "text_template": storylet_text,
                "requires": {
                    "location": target_location,
                    var: 1,  # Require the variable to be set
                },
                "choices": [{"text": "Continue your journey", "set": {}, "condition": None}],
                "weight": 1.0,
            }

            new_storylets.append(new_storylet)
            logger.info(f"📝 Generated storylet requiring '{var}' in {target_location}")

        return new_storylets

    def _generate_variable_storylet(self, var: str, setting_info: List[Tuple]) -> Tuple[str, str]:
        """Generate storylet content based on the variable type."""
        var_themes = {
            "corp_reputation": {
                "title": "Corporate Recognition",
                "text": "Your reputation within the corporate hierarchy opens new doors. Security nodes recognize your clearance level and grant access to restricted areas.",
            },
            "quantum_weaving_skill": {
                "title": "Quantum Mastery",
                "text": "Your understanding of quantum weaving allows you to manipulate the fabric of reality here. The ancient mechanisms respond to your skilled touch.",
            },
            "underground_contacts": {
                "title": "Underground Network",
                "text": "Your connections in the underground network prove invaluable. Hidden allies emerge from the shadows to provide assistance.",
            },
            "player_role": {
                "title": "Role Recognition",
                "text": "Your established role within the dwarven community grants you special privileges and responsibilities in this situation.",
            },
        }

        theme = var_themes.get(
            var,
            {
                "title": f'{var.replace("_", " ").title()} Advantage',
                "text": f'Your {var.replace("_", " ")} proves beneficial in this situation.',
            },
        )

        return theme["title"], theme["text"]

    def _choose_location_for_variable(self, var: str) -> str:
        """Choose an appropriate location for a variable-dependent storylet."""
        var_locations = {
            "corp_reputation": "Corporate Stronghold",
            "quantum_weaving_skill": "Old Clan Library",
            "underground_contacts": "Rusted Halls",
            "player_role": "Clan Hall",
        }

        # Get location or pick a random one if variable not in dictionary
        if var in var_locations:
            return var_locations[var]
        else:
            available_locations = list(self.locations - {"No Location"})
            return random.choice(available_locations) if available_locations else "Clan Hall"

    def fix_spatial_integration(self, dry_run: bool = False) -> Dict:
        """
        Fix spatial integration by assigning locations to storylets with 'No Location'
        and creating movement connections between locations.
        """
        logger.info("🗺️  Fixing spatial integration...")

        # Define new thematic locations for spatial expansion
        new_locations = [
            "Diagnostic Laboratory",
            "Testing Grounds",
            "Protocol Chamber",
            "Stability Core",
            "Insight Archive",
            "Discovery Vault",
            "Analysis Station",
            "Evaluation Center",
            "Transition Hub",
            "Data Observatory",
            "Anomaly Chamber",
            "Deep Dive Center",
            "Evaluation Plaza",
            "Insight Nexus",
            "Progress Hall",
        ]

        fixes_applied = {
            "locations_assigned": 0,
            "connections_created": 0,
            "modified_storylets": [],
        }

        # Find storylets with no location
        no_location_storylets = [s for s in self.storylets if s["requires"].get("location", "No Location") == "No Location"]

        if not no_location_storylets:
            logger.info("✅ All storylets already have locations assigned")
            return fixes_applied

        logger.info(f"📍 Found {len(no_location_storylets)} storylets without locations")

        # Assign locations intelligently based on content
        location_index = 0
        for storylet in no_location_storylets:
            title_lower = storylet["title"].lower()

            # Smart location assignment based on content
            if "diagnostic" in title_lower:
                location = "Diagnostic Laboratory"
            elif "stability" in title_lower or "stable" in title_lower:
                location = "Stability Core"
            elif "insight" in title_lower:
                location = "Insight Archive"
            elif "discovery" in title_lower or "reveal" in title_lower:
                location = "Discovery Vault"
            elif "analysis" in title_lower or "analyze" in title_lower:
                location = "Analysis Station"
            elif "evaluation" in title_lower or "evaluate" in title_lower:
                location = "Evaluation Center"
            elif "transition" in title_lower:
                location = "Transition Hub"
            elif "data" in title_lower or "stream" in title_lower:
                location = "Data Observatory"
            elif "anomal" in title_lower:
                location = "Anomaly Chamber"
            elif "deep" in title_lower:
                location = "Deep Dive Center"
            elif "progress" in title_lower:
                location = "Progress Hall"
            elif "protocol" in title_lower:
                location = "Protocol Chamber"
            elif "test" in title_lower:
                location = "Testing Grounds"
            else:
                # Round-robin assignment for generic storylets
                all_locations = list(self.locations - {"No Location"}) + new_locations
                location = all_locations[location_index % len(all_locations)]
                location_index += 1

            # Update the storylet's requirements
            storylet["requires"]["location"] = location

            if not dry_run:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE storylets 
                    SET requires = ? 
                    WHERE id = ?
                """,
                    (json.dumps(storylet["requires"]), storylet["id"]),
                )
                conn.commit()
                conn.close()

            fixes_applied["locations_assigned"] += 1
            fixes_applied["modified_storylets"].append(storylet["id"])

        # Create movement connections between locations
        if fixes_applied["locations_assigned"] > 0:
            # Reload to get updated location data
            self.load_storylets()
            self.analyze_graph()

            # Add movement choices to representative storylets
            locations = list(self.locations - {"No Location"})
            for location in locations:
                storylets_in_location = self.location_storylets[location]

                if storylets_in_location:
                    # Use first storylet as representative for movement
                    representative = storylets_in_location[0]

                    # Add movement options to 2-3 other locations
                    other_locations = [loc for loc in locations if loc != location]
                    nearby_locations = random.sample(other_locations, min(3, len(other_locations)))

                    for target_location in nearby_locations:
                        movement_choice = {
                            "text": f"Travel to {target_location}",
                            "set": {"location": target_location},
                            "condition": None,
                        }
                        representative["choices"].append(movement_choice)
                        fixes_applied["connections_created"] += 1

                    if not dry_run and nearby_locations:
                        conn = sqlite3.connect(self.db_path)
                        cursor = conn.cursor()
                        cursor.execute(
                            """
                            UPDATE storylets 
                            SET choices = ? 
                            WHERE id = ?
                        """,
                            (
                                json.dumps(representative["choices"]),
                                representative["id"],
                            ),
                        )
                        conn.commit()
                        conn.close()

                        if representative["id"] not in fixes_applied["modified_storylets"]:
                            fixes_applied["modified_storylets"].append(representative["id"])

        logger.info(f"✅ Assigned {fixes_applied['locations_assigned']} locations")
        logger.info(f"✅ Created {fixes_applied['connections_created']} movement connections")
        return fixes_applied

    def smooth_story(
        self,
        dry_run: bool = False,
        apply_spatial_fixes: bool = False,
    ) -> Dict:
        """
        Main smoothing algorithm - recursively fix story problems.
        """
        logger.info("🔧 Starting story smoothing algorithm...")

        # Load and analyze current state
        self.load_storylets()
        self.analyze_graph()

        fixes_applied = {
            "exit_choices_added": 0,
            "variable_storylets_created": 0,
            "bidirectional_connections": 0,
            "spatial_locations_assigned": 0,
            "spatial_connections_created": 0,
            "modified_storylets": [],
        }

        if dry_run:
            logger.info("🧪 DRY RUN MODE - No changes will be saved")

        spatial_fixes = {
            "locations_assigned": 0,
            "connections_created": 0,
            "modified_storylets": [],
        }
        if apply_spatial_fixes:
            spatial_fixes = self.fix_spatial_integration(dry_run)
            fixes_applied["spatial_locations_assigned"] = spatial_fixes["locations_assigned"]
            fixes_applied["spatial_connections_created"] = spatial_fixes["connections_created"]
            fixes_applied["modified_storylets"].extend(spatial_fixes["modified_storylets"])

            # Reload and re-analyze after spatial fixes
            if spatial_fixes["locations_assigned"] > 0 or spatial_fixes["connections_created"] > 0:
                self.load_storylets()
                self.analyze_graph()

        # Fix 1: Add exit choices to isolated locations
        for location in self.isolated_locations:
            storylets_in_location = self.location_storylets[location]

            for storylet in storylets_in_location:
                # Find nearby locations to connect to
                other_locations = list(self.locations - {location, "No Location"})[:2]

                if other_locations:
                    new_choices = self.generate_exit_choices(storylet, other_locations)

                    if not dry_run:
                        self._update_storylet_choices(storylet["id"], storylet["choices"] + new_choices)

                    fixes_applied["exit_choices_added"] += len(new_choices)
                    fixes_applied["modified_storylets"].append(storylet["id"])

                    logger.info(f"✅ Added {len(new_choices)} exit choices to '{storylet['title']}'")

        # Fix 2: Create storylets that require dead-end variables
        if self.dead_end_vars:
            new_storylets = self.generate_variable_requirement_storylets()

            if not dry_run:
                for new_storylet in new_storylets:
                    self._insert_storylet(new_storylet)

            fixes_applied["variable_storylets_created"] = len(new_storylets)

        # Fix 3: Add return paths for one-way connections
        for from_loc, to_loc in self.one_way_connections:
            # Find a storylet in to_loc to add a return path
            target_storylets = self.location_storylets[to_loc]

            if target_storylets:
                storylet = target_storylets[0]  # Pick first storylet
                return_choice = {
                    "text": f"Return to {from_loc}",
                    "set": {"location": from_loc},
                    "condition": None,
                }

                if not dry_run:
                    updated_choices = storylet["choices"] + [return_choice]
                    self._update_storylet_choices(storylet["id"], updated_choices)

                fixes_applied["bidirectional_connections"] += 1
                fixes_applied["modified_storylets"].append(storylet["id"])

                logger.info(f"🔄 Added return path from {to_loc} to {from_loc}")

        # Calculate total fixes (excluding the list of modified storylets)
        total_fixes = fixes_applied["exit_choices_added"] + fixes_applied["variable_storylets_created"] + fixes_applied["bidirectional_connections"] + fixes_applied["spatial_locations_assigned"] + fixes_applied["spatial_connections_created"]

        logger.info(f"🎉 Story smoothing complete! Applied {total_fixes} fixes")
        return fixes_applied

    def _update_storylet_choices(self, storylet_id: int, new_choices: List[Dict]):
        """Update a storylet's choices in the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE storylets 
            SET choices = ? 
            WHERE id = ?
        """,
            (json.dumps(new_choices), storylet_id),
        )

        conn.commit()
        conn.close()

    def _insert_storylet(self, storylet: Dict):
        """Insert a new storylet into the database."""
        new_storylet_id = None
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO storylets (title, text_template, requires, choices, weight)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        storylet["title"],
                        storylet["text_template"],
                        json.dumps(storylet["requires"]),
                        json.dumps(storylet["choices"]),
                        storylet["weight"],
                    ),
                )
                new_storylet_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            logger.warning(
                "Skipping smoother-generated duplicate storylet title: %s",
                storylet.get("title", "<untitled>"),
            )
            return

        # Auto-assign spatial coordinates if the storylet has a location
        if new_storylet_id is not None:
            try:
                from sqlalchemy.orm import sessionmaker
                from ..database import engine

                Session = sessionmaker(bind=engine)
                db_session = Session()

                from .spatial_navigator import SpatialNavigator

                updates = SpatialNavigator.auto_assign_coordinates(db_session, [new_storylet_id])
                if updates > 0:
                    logger.info(f"📍 Auto-assigned coordinates to new storylet: {storylet['title']}")

                db_session.close()
            except Exception as e:
                logger.warning(f"⚠️ Warning: Could not auto-assign coordinates to storylet '{storylet['title']}': {e}")
