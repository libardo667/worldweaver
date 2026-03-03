"""
Story Deepener Algorithm
Analyzes storylet connections and generates intermediate storylets to create
more coherent, engaging narrative flow with meaningful choice consequences.
"""

import logging
import sqlite3
import json
from collections import defaultdict

logger = logging.getLogger(__name__)
from typing import Dict, List, Set, Tuple, Optional
import random

from ..database import db_file as _default_db_file
from . import prompt_library


class StoryDeepener:
    """
    Narrative flow enhancer that adds depth, context, and meaningful transitions
    between storylets to create a more engaging player experience.
    """

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or _default_db_file
        self.storylets = []
        self.choice_transitions = []  # (from_storylet, choice, to_storylet)
        self.weak_transitions = []  # Transitions that need deepening
        self.missing_context = []  # Storylets that need setup

    def load_and_analyze(self):
        """Load storylets and analyze narrative flow."""
        logger.info("📚 Loading storylets for deepening analysis...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all storylets
        cursor.execute(
            "SELECT id, title, text_template, requires, choices FROM storylets"
        )
        self.storylets = []
        storylet_map = {}

        for row in cursor.fetchall():
            storylet = {
                "id": row[0],
                "title": row[1],
                "text": row[2],
                "requires": json.loads(row[3]) if row[3] else {},
                "choices": json.loads(row[4]) if row[4] else [],
            }
            self.storylets.append(storylet)
            storylet_map[storylet["id"]] = storylet

        # Analyze choice-to-storylet connections
        self._analyze_transitions(storylet_map)
        conn.close()

        logger.info(f"🔍 Found {len(self.choice_transitions)} choice transitions")
        logger.warning(f"⚠️  Identified {len(self.weak_transitions)} weak transitions")

    def _insert_bridge_storylet(self, cursor, bridge: Dict) -> Optional[int]:
        """Insert a bridge storylet, retrying with suffix if title collides."""
        base_title = str(bridge.get("title", "")).strip() or "Generated Bridge"
        base_title = base_title[:180]

        for attempt in range(5):
            title = base_title if attempt == 0 else f"{base_title} [bridge-{attempt + 1}]"
            try:
                cursor.execute(
                    """
                    INSERT INTO storylets (title, text_template, requires, choices, weight)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        title,
                        bridge["text_template"],
                        json.dumps(bridge["requires"]),
                        json.dumps(bridge["choices"]),
                        bridge["weight"],
                    ),
                )
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                continue

        logger.warning("Skipping deepener bridge after duplicate retries: %s", base_title)
        return None

    def _analyze_transitions(self, storylet_map: Dict):
        """Analyze how choices connect to resulting storylets."""
        self.choice_transitions = []
        self.weak_transitions = []

        for storylet in self.storylets:
            current_location = storylet["requires"].get("location", "No Location")

            for choice_idx, choice in enumerate(storylet["choices"]):
                choice_sets = choice.get("set", {})
                choice_text = choice.get(
                    "label", choice.get("text", "")
                )  # Try both label and text

                # Find what storylets this choice could lead to
                possible_next = self._find_matching_storylets(choice_sets, storylet_map)

                if possible_next:
                    for next_storylet in possible_next:
                        transition = {
                            "from": storylet,
                            "choice": choice,
                            "choice_idx": choice_idx,
                            "to": next_storylet,
                            "coherence_score": self._rate_transition_coherence(
                                storylet, choice, next_storylet
                            ),
                        }

                        self.choice_transitions.append(transition)

                        # Flag weak transitions for deepening
                        if transition["coherence_score"] < 0.6:
                            self.weak_transitions.append(transition)
                else:
                    # Choice leads nowhere - needs a destination storylet
                    self.weak_transitions.append(
                        {
                            "from": storylet,
                            "choice": choice,
                            "choice_idx": choice_idx,
                            "to": None,
                            "coherence_score": 0.0,
                        }
                    )

    def _find_matching_storylets(
        self, choice_sets: Dict, storylet_map: Dict
    ) -> List[Dict]:
        """Find storylets that could be reached by this choice."""
        matches = []

        for storylet in self.storylets:
            # Check if choice sets match storylet requirements
            requirements_met = True

            for req_key, req_value in storylet["requires"].items():
                if req_key in choice_sets:
                    if choice_sets[req_key] != req_value:
                        requirements_met = False
                        break
                elif req_key == "location" and choice_sets.get("location"):
                    # Location is being set by choice
                    if choice_sets["location"] != req_value:
                        requirements_met = False
                        break

            if requirements_met:
                matches.append(storylet)

        return matches

    def _rate_transition_coherence(
        self, from_storylet: Dict, choice: Dict, to_storylet: Dict
    ) -> float:
        """Rate how coherent a transition is (0.0 = nonsensical, 1.0 = perfect)."""
        score = 0.5  # Base score

        choice_text = choice.get(
            "label", choice.get("text", "")
        ).lower()  # Try both label and text
        from_text = from_storylet.get(
            "text_template", from_storylet.get("text", "")
        ).lower()
        to_text = to_storylet.get("text_template", to_storylet.get("text", "")).lower()

        # Check for thematic consistency
        if "crystal" in choice_text and "crystal" in to_text:
            score += 0.3
        if "library" in choice_text and "library" in to_text:
            score += 0.3
        if "corporate" in choice_text and "corporate" in to_text:
            score += 0.3

        # Check for narrative continuity keywords
        continuity_words = ["ask", "investigate", "examine", "talk", "look"]
        if any(word in choice_text for word in continuity_words):
            if any(word in to_text for word in ["respond", "explain", "show", "tell"]):
                score += 0.2

        # Penalize abrupt topic changes
        from_topics = self._extract_topics(from_text)
        to_topics = self._extract_topics(to_text)

        if from_topics and to_topics:
            overlap = len(from_topics.intersection(to_topics)) / len(
                from_topics.union(to_topics)
            )
            score += overlap * 0.3

        return min(score, 1.0)

    def _extract_topics(self, text: str) -> Set[str]:
        """Extract key topics from text."""
        topics = set()
        topic_keywords = {
            "crystals": ["crystal", "gem", "stone", "mineral"],
            "technology": ["quantum", "tech", "device", "machine", "computer"],
            "corporate": ["corp", "company", "business", "suit"],
            "clan": ["clan", "family", "tradition", "ancestor"],
            "underground": ["tunnel", "cave", "underground", "hidden"],
            "library": ["book", "text", "library", "archive", "knowledge"],
        }

        text_lower = text.lower()
        for topic, keywords in topic_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                topics.add(topic)

        return topics

    def _call_llm(self, prompt: str) -> str:
        """Make a call to the LLM API."""
        try:
            from .llm_client import get_llm_client, get_model

            client = get_llm_client()
            if not client:
                return ""

            response = client.chat.completions.create(
                model=get_model(),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500,
            )

            content = response.choices[0].message.content
            logger.debug(
                f"🔍 DEBUG Bridge: Raw response length: {len(content) if content else 0}"
            )
            logger.debug(f"🔍 DEBUG Bridge: Full response: {content}")

            # Extract JSON from markdown code blocks if present
            if content and "```json" in content:
                json_start = content.find("```json") + 7  # Skip "```json"
                json_end = content.find("```", json_start)
                if json_end != -1:
                    content = content[json_start:json_end].strip()
            elif content and content.strip().startswith("```"):
                # Handle cases where it's just ``` without json
                lines = content.strip().split("\n")
                if (
                    len(lines) > 2
                    and lines[0].startswith("```")
                    and lines[-1].strip() == "```"
                ):
                    content = "\n".join(lines[1:-1])  # Remove first and last lines

            # Clean up any remaining whitespace
            if content:
                content = content.strip()

            return (
                content
                if content is not None
                else '{"title": "Generated Content", "text": "Content generated."}'
            )
        except Exception as e:
            logger.warning(f"⚠️  LLM call failed: {e}")
            return '{"title": "Generated Content", "text": "Content generated."}'

    def generate_bridge_storylets(self) -> List[Dict]:
        """Generate intermediate storylets to bridge weak transitions."""
        logger.info("🌉 Generating bridge storylets for weak transitions...")

        bridge_storylets = []

        # Limit to prevent overwhelming number of bridges
        weak_sample = self.weak_transitions[:3]  # Process only top 3 weak transitions

        for transition in weak_sample:
            if transition["to"] is None:
                # Choice leads nowhere - create a destination
                bridge = self._create_choice_destination(transition)
            else:
                # Weak transition - create intermediate storylet
                bridge = self._create_transition_bridge(transition)

            if bridge:
                bridge_storylets.append(bridge)
                logger.info(f"🌉 Created bridge: '{bridge['title']}'")

        return bridge_storylets

    def _create_choice_destination(self, transition: Dict) -> Optional[Dict]:
        """Create a storylet that responds to a choice that currently leads nowhere."""
        from_storylet = transition["from"]
        choice = transition["choice"]

        # Safely get text content
        from_text = from_storylet.get("text_template", from_storylet.get("text", ""))

        # Use prompt library for contextual bridge prompt
        prompt = prompt_library.build_bridge_prompt(
            from_text=from_text[:200],
            choice_label=choice.get('label', choice.get('text', 'Unknown choice')),
            to_text=None,  # no destination — we're creating one
        )

        try:
            response = self._call_llm(prompt)
            # Parse AI response (simplified - assumes proper JSON)
            ai_content = json.loads(response)

            # Create the new storylet
            new_storylet = {
                "title": ai_content.get(
                    "title",
                    f"Response to {choice.get('label', choice.get('text', 'choice'))[:20]}...",
                ),
                "text_template": ai_content.get(
                    "text",
                    f"You {choice.get('label', choice.get('text', 'act')).lower()}.",
                ),
                "requires": choice.get("set", {}),
                "choices": [{"text": "Continue", "set": {}, "condition": None}],
                "weight": 1.0,
            }

            return new_storylet

        except Exception as e:
            logger.warning(f"⚠️  AI generation failed: {e}")
            # Fallback to template
            return {
                "title": f"Following Up",
                "text_template": f"You {choice.get('label', choice.get('text', 'take action')).lower()}. The situation develops further.",
                "requires": choice.get("set", {}),
                "choices": [{"text": "Continue", "set": {}, "condition": None}],
                "weight": 1.0,
            }

    def _create_transition_bridge(self, transition: Dict) -> Optional[Dict]:
        """Create an intermediate storylet to smooth the transition."""
        from_storylet = transition["from"]
        choice = transition["choice"]
        to_storylet = transition["to"]

        # Safely get text content
        from_text = from_storylet.get("text_template", from_storylet.get("text", ""))
        to_text = to_storylet.get("text_template", to_storylet.get("text", ""))

        # Use prompt library for contextual bridge prompt
        prompt = prompt_library.build_bridge_prompt(
            from_text=from_text[:150],
            choice_label=choice.get('label', choice.get('text', 'Unknown choice')),
            to_text=to_text[:150],
        )

        try:
            response = self._call_llm(prompt)
            ai_content = json.loads(response)

            bridge_storylet = {
                "title": ai_content.get("title", "Transition"),
                "text_template": ai_content.get(
                    "text",
                    f"You {choice.get('label', choice.get('text', 'act')).lower()}.",
                ),
                "requires": choice.get("set", {}),
                "choices": [
                    {
                        "text": "Continue",
                        "set": to_storylet["requires"],
                        "condition": None,
                    }
                ],
                "weight": 1.0,
            }

            return bridge_storylet

        except Exception as e:
            logger.warning(f"⚠️  Bridge generation failed: {e}")
            return None

    def add_choice_previews(self):
        """Add preview text to choices showing what they might lead to."""
        logger.info("👁️  Adding choice previews...")

        updates = 0
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            for storylet in self.storylets:
                updated_choices = []
                choice_updated = False

                for choice in storylet["choices"]:
                    choice_sets = choice.get("set", {})

                    # Find what this choice leads to
                    next_location = choice_sets.get("location")
                    preview_hint = ""

                    if next_location:
                        preview_hint = f" (→ {next_location})"
                    elif choice_sets:
                        # Show what variables are set
                        var_changes = [
                            f"{k}+{v}" for k, v in choice_sets.items() if k != "location"
                        ]
                        if var_changes:
                            preview_hint = f" ({', '.join(var_changes[:2])})"

                    if preview_hint and not choice.get(
                        "label", choice.get("text", "")
                    ).endswith(")"):
                        updated_choice = choice.copy()
                        updated_choice["label"] = (
                            choice.get("label", choice.get("text", "")) + preview_hint
                        )
                        updated_choices.append(updated_choice)
                        choice_updated = True
                    else:
                        updated_choices.append(choice)

                if choice_updated:
                    cursor.execute(
                        """
                        UPDATE storylets 
                        SET choices = ? 
                        WHERE id = ?
                    """,
                        (json.dumps(updated_choices), storylet["id"]),
                    )
                    updates += 1

        logger.info(f"✅ Updated {updates} storylets with choice previews")

    def deepen_story(self, add_previews: bool = True) -> Dict:
        """Main deepening process."""
        logger.info("🕳️  Starting story deepening process...")

        # Load and analyze current state
        self.load_and_analyze()

        results = {
            "bridge_storylets_created": 0,
            "choice_previews_added": 0,
            "coherence_improved": 0,
        }

        # Generate bridge storylets
        bridge_storylets = self.generate_bridge_storylets()

        if bridge_storylets:
            new_storylet_ids = []
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                for bridge in bridge_storylets:
                    new_id = self._insert_bridge_storylet(cursor, bridge)
                    if new_id is not None:
                        new_storylet_ids.append(new_id)

            # Auto-assign spatial coordinates to newly created bridge storylets
            if new_storylet_ids:
                try:
                    from sqlalchemy.orm import sessionmaker
                    from ..database import engine

                    Session = sessionmaker(bind=engine)
                    db_session = Session()

                    from .spatial_navigator import SpatialNavigator

                    updates = SpatialNavigator.auto_assign_coordinates(
                        db_session, new_storylet_ids
                    )
                    if updates > 0:
                        logger.info(
                            f"📍 Auto-assigned coordinates to {updates} bridge storylets"
                        )

                    db_session.close()
                except Exception as e:
                    logger.warning(
                        f"⚠️ Warning: Could not auto-assign coordinates to bridge storylets: {e}"
                    )

            results["bridge_storylets_created"] = len(new_storylet_ids)
        # Add choice previews
        if add_previews:
            self.add_choice_previews()
            results["choice_previews_added"] = 1

        total_improvements = sum(results.values())
        logger.info(f"🎉 Story deepening complete! Made {total_improvements} improvements")

        return results
