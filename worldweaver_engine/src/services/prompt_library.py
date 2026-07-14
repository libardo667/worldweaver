# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Prompts used by live action and world-entry inference surfaces."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

NARRATIVE_VOICE_SPEC = """
NARRATIVE VOICE — follow these rules for ALL generated text:
- Write in SECOND PERSON, PRESENT TENSE ("You step into the clearing…").
- Be SPECIFIC, never generic. Name concrete things already supported by context.
- Use CONCRETE SENSORY DETAILS. Ground every scene in at least two senses.
- VARY SENTENCE LENGTH. Mix short beats with longer flowing ones.
- Show, don't tell — "Your hands tremble" not "You feel afraid".
- NEVER START with "You find yourself…" or "You are in…". Open mid-action
  or mid-sensation instead.
- Keep prose tight — 2-4 vivid sentences per scene, not walls of text.
""".strip()


def build_action_system_prompt() -> str:
    """Return the system prompt for freeform command interpretation."""
    return "\n".join(
        [
            "You narrate a living world. Interpret a player's freeform action against " "the supplied world state and return a coherent response with proposed changes.",
            "",
            NARRATIVE_VOICE_SPEC,
            "",
            "INTERPRETATION RULES:",
            "- If the action is implausible, explain the failure in-world.",
            "- State changes must be consistent with established world facts.",
            "- Follow-up choices should be natural consequences of the action.",
            "- Never break the fourth wall.",
        ]
    )


def build_action_intent_system_prompt() -> str:
    """Return strict instructions for stage-A action intent extraction."""
    return "\n".join(
        [
            "You are a strict JSON planner for a freeform action.",
            "Return compact structured intent only. Do not narrate beyond one ack line.",
            "",
            "OUTPUT RULES:",
            "- Return ONLY a valid JSON object.",
            "- Include keys: ack_line, plausible, delta.",
            "- Optional keys: following_beat, following_beats, goal_update, confidence, rationale.",
            "- delta may include only set, increment, and append_fact operations.",
            "- Keep ack_line to one sentence under 160 characters.",
            "- Never include markdown code fences.",
            "",
            "PLAUSIBILITY RULES:",
            "- Set plausible=false only for physical or logical impossibilities.",
            "- Travel is handled by the map surface, not by action deltas.",
            "- The player cannot use, drop, or give absent items.",
            "- Morally questionable actions remain plausible when physically possible.",
        ]
    )


def build_action_narration_system_prompt() -> str:
    """Return instructions for rendering narration from validated changes."""
    return "\n".join(
        [
            "You render the observable consequences of one validated action.",
            "You may not propose new state mutations.",
            "",
            NARRATIVE_VOICE_SPEC,
            "",
            "RULES:",
            "- Use only the validated changes and evidence supplied in context.",
            "- Output JSON only with keys: narrative, public_summary, choices.",
            "- public_summary is one outward-facing observation, without hidden inner experience.",
            "- choices must be 2-6 concise follow-up options.",
            "- Each choice includes label, set, and a short second-person intent.",
            "- Ground details in scene_card_now and sensory_palette.",
            "- recent_action_summary describes what just happened; begin from that causal point.",
            "- Treat present_characters as physically present, without inventing biographies.",
            "- Avoid motifs from motifs_recent unless immediate evidence requires them.",
            "- Never break the fourth wall.",
        ]
    )


def build_scene_card_sensory_palette(scene_card: Dict[str, Any]) -> Dict[str, str]:
    """Derive deterministic sensory anchors from the immediate scene card."""
    if not isinstance(scene_card, dict):
        return {}

    location = str(scene_card.get("location", "")).strip()
    stakes = str(scene_card.get("immediate_stakes", "")).strip()
    raw_cast = scene_card.get("cast_on_stage", [])
    cast = [str(item).strip() for item in raw_cast if str(item).strip()] if isinstance(raw_cast, list) else []
    raw_constraints = scene_card.get("constraints_or_affordances")
    if not isinstance(raw_constraints, list):
        raw_constraints = scene_card.get("constraints", [])
    constraints = [str(item).strip() for item in raw_constraints if str(item).strip()] if isinstance(raw_constraints, list) else []

    lead_cast = cast[0] if cast else "nearby actors"
    lead_constraint = constraints[0] if constraints else "ambient pressure"
    object_anchor = cast[1] if len(cast) > 1 else (location or "the surrounding space")
    stakes_clause = stakes.lower() if stakes else "unstable silence"
    return {
        "smell": f"The air around {location or 'the scene'} carries {lead_constraint.lower()}.",
        "sound": f"Sound pressure centers on {lead_cast.lower()} amid {stakes_clause}.",
        "tactile": f"Surfaces feel affected by {lead_constraint.lower()}.",
        "material": f"Materials nearby reflect {location or 'local terrain'} conditions.",
        "object_hint": f"A tangible focal object is {object_anchor}.",
    }


def build_motif_auditor_system_prompt() -> str:
    """Return strict referee instructions for motif repetition auditing."""
    return "\n".join(
        [
            "You are a strict motif auditor for interactive-fiction narration.",
            "Inspect the draft for repeated motif gravity against recent motif history.",
            "Return JSON only.",
            "",
            "OUTPUT CONTRACT:",
            '- decision: "ok" or "revise".',
            "- overused_motifs: array of short motif strings.",
            "- replacement_anchors: array grounded in scene_card_now.",
            "- rationale: one short sentence.",
            "",
            "Choose revise only when repeated motifs dominate the draft. Do not invent facts.",
        ]
    )


def build_motif_revision_system_prompt() -> str:
    """Return narrator instructions for one-pass motif revision."""
    return "\n".join(
        [
            "Revise a draft scene to reduce motif repetition while preserving cause and stakes.",
            "Return JSON only with a single key: text.",
            "Use second-person present tense, keep 2-4 sentences, and do not change facts or deltas.",
        ]
    )


_ENTRY_CARDS_OUTPUT_SCHEMA = """
OUTPUT SCHEMA — return ONLY valid JSON:
{
  "snapshot": "2-3 sensory sentences grounded in current events",
  "cards": [
    {
      "name": "Character or archetype name",
      "role": "Short role label",
      "flavor": "1-2 grounded sentences",
      "location": "one known location",
      "entry_action": "one specific first-person arrival action"
    }
  ]
}
RULES:
- Generate exactly 4 cards, mixing known inhabitants with open archetypes.
- Use only locations supplied in known_locations.
- Do not wrap the JSON in markdown fences.
""".strip()


def build_entry_cards_prompt(
    event_summaries: List[str],
    fact_summaries: List[str],
    existing_session_labels: List[str],
    world_name: str = "the world",
    known_locations: Optional[List[str]] = None,
) -> tuple[str, str]:
    """Build the world-entry snapshot and role-card prompt."""
    system_prompt = "\n\n".join([NARRATIVE_VOICE_SPEC, _ENTRY_CARDS_OUTPUT_SCHEMA])
    context: Dict[str, Any] = {
        "world_name": world_name,
        "known_locations": known_locations or [],
        "recent_events": event_summaries[:25],
        "world_facts": fact_summaries[:20],
        "existing_inhabitants": existing_session_labels[:10],
        "task": ("Describe what is happening now, then generate four possible entry roles. " "Ground every claim in the supplied events and facts."),
    }
    return system_prompt, json.dumps(context, ensure_ascii=False, default=str)
