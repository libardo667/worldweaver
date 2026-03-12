"""Centralized prompt library for WorldWeaver LLM interactions.

All system prompts, narrative voice guidelines, few-shot exemplars, and
anti-pattern guidance live here so they can be reviewed, iterated, and
A/B-tested in one place.  Builder functions compose shared blocks with
context-specific instructions — updates propagate to every call site.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# 1. NARRATIVE VOICE SPECIFICATION
# ---------------------------------------------------------------------------

NARRATIVE_VOICE_SPEC = """
NARRATIVE VOICE — follow these rules for ALL generated text:
- Write in SECOND PERSON, PRESENT TENSE ("You step into the clearing…").
- Be SPECIFIC, never generic. Name things: "the iron lantern" not "a light",
  "Captain Maren" not "the person". Invented proper nouns are encouraged.
- Use CONCRETE SENSORY DETAILS — what does the place smell like, sound like,
  feel underfoot? Ground every scene in at least two senses.
- VARY SENTENCE LENGTH. Mix short punchy beats with longer flowing ones.
  Avoid monotonous rhythm.
- Show, don't tell — "Your hands tremble" not "You feel afraid".
- NEVER START with "You find yourself…" or "You are in…". Open mid-action
  or mid-sensation instead.
- Keep prose tight — 2-4 vivid sentences per scene, not walls of text.
  Every word should earn its place.
""".strip()

# ---------------------------------------------------------------------------
# 2. ANTI-PATTERNS — explicit things to avoid
# ---------------------------------------------------------------------------

ANTI_PATTERNS = """
AVOID THESE ANTI-PATTERNS:
- ❌ Generic openings: "You find yourself in a mysterious place…"
- ❌ Purple prose / thesaurus abuse: "The quintessential effulgence of the
  eldritch luminescence…"
- ❌ Consequence-free choices: two options that lead to the same outcome.
  Every choice MUST change at least one variable meaningfully.
- ❌ Teleportation: moving the player to a distant location without transition
  or in-world justification.
- ❌ Deus ex machina: solving problems with sudden unexplained interventions.
- ❌ Identical choice phrasing: "Go left" / "Go right" with no context.
  Choices should hint at what the player will EXPERIENCE, not just a direction.
- ❌ Breaking the fourth wall: never reference the game, the engine, or the
  player as a player. You are a narrator, not a game designer.
- ❌ One-word titles: titles should be evocative and specific to the scene.
- ❌ Emoji overuse: at most ONE emoji per storylet, and only if it adds
  atmosphere. Most storylets should have zero.
""".strip()

# ---------------------------------------------------------------------------
# 3. QUALITY EXEMPLARS — few-shot examples of good & bad storylets
# ---------------------------------------------------------------------------

QUALITY_EXEMPLARS = """
=== GOOD STORYLET EXAMPLE 1 ===
{
  "title": "The Cartographer's Bargain",
  "text_template": "Ink-stained maps cover every surface of the cramped shop. The cartographer, Rhuel, peers at you over half-moon spectacles, tapping a coastline you've never seen on any official chart. 'I'll trade it,' he says, 'for the name of whoever sent you to the Thornwall district. Fair's fair.'",
  "requires": {"location": "thornwall_market"},
  "choices": [
    {"label": "Give him the name — a map like that is worth the betrayal", "set": {"has_secret_map": true, "rhuel_trust": 1, "informant_exposed": true}},
    {"label": "Deflect and offer coin instead, keeping your contacts safe", "set": {"gold": {"dec": 15}, "has_secret_map": true}},
    {"label": "Memorise what you can see and leave empty-handed", "set": {"cartography_knowledge": {"inc": 1}, "rhuel_suspicion": true}}
  ],
  "weight": 1.2
}
WHY THIS WORKS: Specific named NPC, sensory detail (ink, spectacles), every
choice has distinct mechanical AND narrative consequences, the scene implies
a larger world (Thornwall district, official charts, informant).

=== GOOD STORYLET EXAMPLE 2 ===
{
  "title": "Rain on the Salt Flats",
  "text_template": "The first drops hit the cracked white ground and the air fills with a mineral tang sharp enough to taste. Somewhere behind you, the pack-mule stamps nervously. Ahead, the trail dissolves into white haze. Your guide, Sabil, has gone very quiet — and that's never been a good sign.",
  "requires": {"location": "salt_flats", "has_guide": true},
  "choices": [
    {"label": "Ask Sabil what she's not telling you", "set": {"sabil_trust": {"inc": 1}, "danger": {"inc": 1}}},
    {"label": "Push forward before the trail disappears entirely", "set": {"progress": {"inc": 1}, "exhaustion": {"inc": 1}}},
    {"label": "Make camp and wait it out — better slow than lost", "set": {"time_of_day": "night", "supplies": {"dec": 1}}}
  ],
  "weight": 1.0
}
WHY THIS WORKS: Opens mid-sensation (rain hitting salt), multiple senses
(taste, sound, sight), character detail via behaviour ("gone very quiet"),
choices have real tradeoffs with multiple variable consequences.

=== BAD STORYLET — WHAT TO AVOID ===
{
  "title": "A Place",
  "text_template": "You find yourself in a mysterious location. There are things here you could interact with. What do you do?",
  "requires": {},
  "choices": [
    {"label": "Look around", "set": {}},
    {"label": "Continue", "set": {}}
  ],
  "weight": 1.0
}
WHY THIS FAILS: Starts with "You find yourself", completely generic (no
sensory details, no named anything, no specificity), choices set no variables
and are consequence-free, title is meaningless, requires nothing.
""".strip()

# ---------------------------------------------------------------------------
# 4. TECHNICAL FORMAT SPEC — shared JSON schema requirements
# ---------------------------------------------------------------------------

STORYLET_FORMAT_SPEC = """
STRICT FORMAT REQUIREMENTS:
- Output ONLY valid JSON with a top-level 'storylets' array.
- Each storylet MUST have: title, text_template, requires, choices, weight.
- text_template should use {variable_name} syntax for dynamic content.
- requires specifies conditions: {"location": "market"} or {"danger": {"lte": 3}}.
- choices is an array of {label, set} objects where 'set' modifies variables.
- weight is a float (higher = more likely to appear, default 1.0).

VARIABLE OPERATIONS:
- Direct assignment: {"has_item": true, "location": "new_place"}
- Numeric increment/decrement: {"danger": {"inc": 1}, "gold": {"dec": 5}}
- Operators in requires: {"health": {"gte": 10}, "danger": {"lte": 3}}
""".strip()

SINGLE_STORYLET_FORMAT_SPEC = """
STRICT FORMAT REQUIREMENTS:
- Output ONLY valid JSON with exactly the fields shown in the schema.
- Do NOT wrap in markdown code fences.
- Do NOT include any text outside the JSON object.
""".strip()

# ---------------------------------------------------------------------------
# 5. BUILDER FUNCTIONS
# ---------------------------------------------------------------------------


def build_storylet_system_prompt(
    bible: Dict[str, Any],
    *,
    role: str = "master storyteller",
) -> str:
    """Compose the system prompt for storylet generation.

    Replaces the old ``build_feedback_aware_prompt`` in llm_service.py.
    Merges narrative voice, exemplars, anti-patterns, format spec,
    and any bible-driven feedback.
    """
    parts: list[str] = [
        f"You are a {role} creating interconnected storylets for a living, " "reactive interactive-fiction world. Your goal is to create VIVID, " "SPECIFIC storylets that feel like moments in a real place, not " "generic adventure prompts.",
        "",
        NARRATIVE_VOICE_SPEC,
        "",
        ANTI_PATTERNS,
        "",
        "STORY CONTINUITY RULES:",
        "- Build upon the player's current location and situation logically.",
        "- Create natural transitions between locations (no teleporting).",
        "- Respect established danger levels and previous choices.",
        "- Ensure choices lead to believable, distinct consequences.",
        "- Maintain internal consistency within the story world.",
    ]

    # Inject feedback from bible (preserves old build_feedback_aware_prompt logic)
    parts.extend(_extract_bible_feedback(bible))

    parts.extend(["", QUALITY_EXEMPLARS, "", STORYLET_FORMAT_SPEC])

    return "\n".join(parts)


def build_world_gen_system_prompt(
    description: str,
    theme: str,
    player_role: str = "adventurer",
    key_elements: Optional[List[str]] = None,
    tone: str = "adventure",
    count: int = 15,
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for world generation.

    Both prompts carry the full voice spec and exemplars so the very
    first batch of storylets sets the quality bar.
    """
    system_prompt = "\n".join(
        [
            "You are an expert interactive-fiction world builder. Your job is to " "create a web of interconnected storylets that form a coherent, immersive " "world from a simple description.",
            "",
            NARRATIVE_VOICE_SPEC,
            "",
            ANTI_PATTERNS,
            "",
            QUALITY_EXEMPLARS,
        ]
    )

    elements_text = ", ".join(key_elements) if key_elements else "Derive from description"

    user_prompt = f"""WORLD DESCRIPTION: {description}
THEME: {theme}
PLAYER ROLE: {player_role}
KEY ELEMENTS: {elements_text}
TONE: {tone}

Create {count} interconnected storylets forming a cohesive, immersive world.

RUNTIME VARIABLE CONTRACT — these vars are GUARANTEED to exist in the player's
state at session start. Your 'requires' blocks MUST only reference these names
(or names your own storylets explicitly set in their choice 'set' blocks):

  location      (string) — name of the player's current world-bible location
  morality      (string) — e.g. "devout", "pragmatic", "ruthless"
  stance        (string) — e.g. "observing", "cautious", "aggressive"
  last_action   (string) — short verb slug of the player's most recent action
  danger        (int)    — current danger level, starts at 0
  injury_state  (string) — "healthy", "wounded", "critical"
  time_of_day   (string) — "morning", "afternoon", "evening", "night"
  weather       (string) — "clear", "stormy", "ash-fall", etc.
  inventory_count (int)  — number of items carried, starts at 0
  relationship_count (int) — number of known NPCs, starts at 0

WORLD VARIABLE DESIGN:
- Use location names that fit this specific world and derive them from the description.
- The FIRST storylet's choices should set 'location' to one of your world's named places.
- Create world-specific resource/status variables (e.g. favor_of_X, oath_kept, relic_found).
- Ensure variables connect storylets into a narrative web where choices matter.
- Never require a variable in 'requires' that nothing in your storylet set can ever write.

Each storylet must:
1. FIT THE WORLD — match the theme, tone, and setting.
2. CREATE CONNECTIONS — reference variables other storylets set or require.
3. OFFER MEANINGFUL CHOICES — 2-3 choices with distinct mechanical AND narrative consequences.
4. FOLLOW THE VOICE SPEC — second person, present tense, specific, sensory.

{STORYLET_FORMAT_SPEC}

Return EXACTLY {count} storylets. Make the world feel alive."""

    return system_prompt, user_prompt


def build_starting_storylet_prompt(
    world_description: Any,
    available_locations: list[str],
    world_themes: list[str],
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for generating a starting storylet."""
    system_prompt = "\n".join(
        [
            "You create immersive, world-specific story openings that perfectly " "match a generated world. The opening must feel like stepping into a " "real place, not a tutorial screen.",
            "",
            NARRATIVE_VOICE_SPEC,
            "",
            ANTI_PATTERNS,
        ]
    )

    locations_text = ", ".join(available_locations) if available_locations else "various locations"
    themes_text = ", ".join(world_themes) if world_themes else "adventure"

    first_loc = available_locations[0] if available_locations else "start"
    second_loc = available_locations[1] if len(available_locations) > 1 else first_loc

    user_prompt = f"""WORLD CONTEXT:
- Description: {world_description.description}
- Theme: {world_description.theme}
- Player Role: {world_description.player_role}
- Tone: {world_description.tone}

GENERATED WORLD:
- Available Locations: {locations_text}
- World Themes: {themes_text}

Create a starting storylet that:
1. OPENS MID-SENSATION — the player is already here, already experiencing.
2. SETS UP the player's role and situation naturally (no exposition dump).
3. OFFERS 2-3 CLEAR CHOICES leading to actual locations: {available_locations}
4. Uses the (→ Location) notation in choice labels so players know where they're going.
5. MATCHES the tone and themes perfectly.

{SINGLE_STORYLET_FORMAT_SPEC}

Return JSON:
{{
    "title": "An evocative title specific to this world",
    "text": "Immersive opening. Use {{{{player_role}}}} for the role variable.",
    "choices": [
        {{"label": "Choice leading to {first_loc} (→ {first_loc})", "set": {{"location": "{first_loc}", "player_role": "{world_description.player_role}"}}}},
        {{"label": "Choice leading to {second_loc} (→ {second_loc})", "set": {{"location": "{second_loc}", "player_role": "{world_description.player_role}"}}}}
    ]
}}"""

    return system_prompt, user_prompt


def build_runtime_synthesis_prompt(
    current_vars: Dict[str, Any],
    world_facts: List[str],
    active_goal: Optional[str],
    count: int = 2,
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for runtime storylet synthesis."""
    system_prompt = "\n".join(
        [
            "You generate storylets on-the-fly for a live narrative engine when " "the existing storylet pool is sparse. Your output must be grounded in " "known facts and the player's current context — never invent lore that " "contradicts established world facts.",
            "",
            NARRATIVE_VOICE_SPEC,
            "",
            "Keep storylets EXTREMELY compact (1-2 sentences maximum). These are STUBS for " "background prefetching, not fully narrated scenes. The engine will expand them " "later if selected by the player. Return ONLY schema-compliant JSON.",
        ]
    )

    user_prompt = json.dumps(
        {
            "instruction": ("Generate runtime storylet candidates grounded in current context."),
            "current_state": current_vars,
            "world_facts": [str(f).strip() for f in world_facts[:8] if str(f).strip()],
            "active_goal": active_goal,
            "count": count,
            "output_schema": {
                "storylets": [
                    {
                        "title": "string",
                        "text_template": "string (A COMPACT 1-2 sentence premise/stub, NOT a full scene)",
                        "requires": {"location": "string"},
                        "choices": [{"label": "string", "set": {}}],
                        "weight": 1.0,
                    }
                ]
            },
        },
        default=str,
    )

    return system_prompt, user_prompt


def build_adaptation_prompt() -> str:
    """Return the system prompt for storylet runtime adaptation."""
    return "\n".join(
        [
            "You adapt storylets in real time to reflect the player's current " "world context. Preserve the core scene intent and choice structure. " "Only rewrite descriptive phrasing and choice labels to weave in " "recent events, environment, and emotional tone.",
            "",
            NARRATIVE_VOICE_SPEC,
            "",
            "RULES:",
            "- Keep the same NUMBER of choices as the original.",
            "- Preserve each choice's 'set' payload — only change labels.",
            "- When chosen_action is provided in context, open the narrative by grounding it in the immediate consequence of that specific choice. The first sentence must acknowledge what the player just did.",
            "- Weave in recent events naturally, don't just append them.",
            "- Match the environment (weather, time, danger) in your descriptions.",
            "- Ground scene details in scene_card_now when provided (cast, constraints, immediate stakes).",
            "- Use selected_projection_stub as a non-canon trajectory anchor when provided.",
            "- If contrast_projection_stub exists, at most one sentence may reference it as an alternate possibility.",
            "- Never expose projection internals (IDs, non_canon markers, or tree metadata) in player-visible prose.",
            "- Avoid reusing recent motifs unless they are directly supported by scene_card_now or recent events.",
            "- Use at least two distinct anchors from sensory_palette when anchors are provided.",
        ]
    )


def build_action_system_prompt() -> str:
    """Return the system prompt for freeform command interpretation."""
    return "\n".join(
        [
            "You are the narrator of a living interactive-fiction world. When the " "player types a freeform action, you interpret it against the current " "world state and produce a coherent narrative response with state changes.",
            "",
            NARRATIVE_VOICE_SPEC,
            "",
            "INTERPRETATION RULES:",
            "- If the action is IMPLAUSIBLE given the current state, narrate why it " "  fails IN-WORLD (never break the fourth wall).",
            "- Keep narrative responses to 2-4 vivid sentences.",
            "- State changes must be consistent with established world facts.",
            "- Follow-up choices should be natural consequences of the action.",
            "- Never break the fourth wall.",
        ]
    )


def build_action_intent_system_prompt() -> str:
    """Return a strict system prompt for stage-A action intent extraction."""
    return "\n".join(
        [
            "You are a strict JSON planner for a freeform action pipeline.",
            "Return compact structured intent only. Do not narrate beyond one ack line.",
            "",
            "OUTPUT RULES:",
            "- Return ONLY valid JSON object.",
            "- Include keys: ack_line, plausible, delta, should_trigger_storylet.",
            "- Optional keys: following_beat, following_beats, goal_update, confidence, rationale.",
            "- delta must include only: set, increment, append_fact operations.",
            "- Keep ack_line to a single sentence under 160 chars.",
            "- Never include markdown code fences.",
            "",
            "PLAUSIBILITY RULES — set plausible=false ONLY for physical/logical impossibilities:",
            "- Travel and movement to known locations are ALWAYS plausible. 'Go to X', 'travel to X', 'head toward X' — always plausible=true.",
            "- The player cannot use, drop, or give items they don't have in their inventory.",
            "- The player cannot produce outcomes that require objects/resources absent from the scene.",
            "- Morally questionable actions (theft, deception, violence) are still PLAUSIBLE if physically possible.",
            "  Do NOT refuse actions on ethical grounds — only on logical/physical grounds.",
            "- If an action is bold but possible given what's in the scene, mark it plausible=true.",
        ]
    )


def build_action_narration_system_prompt() -> str:
    """Return a system prompt for stage-B narration from validated deltas."""
    return "\n".join(
        [
            "You are the narrator for stage-B rendering.",
            "You receive VALIDATED changes and must narrate consequences without proposing new state mutations.",
            "",
            NARRATIVE_VOICE_SPEC,
            "",
            "RULES:",
            "- Use only the validated changes provided in context.",
            "- Output JSON only with keys: narrative, choices.",
            "- choices must be 2-6 concise follow-up options.",
            "- Each choice must include label (string), set (object), and intent (1-2 sentence second-person commitment).",
            "- Keep narration to 2-4 sentences.",
            "- If validated_state_changes includes a 'location' key, the player has MOVED. Narrate the arrival at the new location — describe the journey's end and first impressions of the new place. Do NOT stay in the old scene.",
            "- Ground descriptive details in scene_card_now and sensory_palette.",
            "- recent_action_summary in the context describes what JUST happened — open your narration from that causal point.",
            "- If present_characters is provided, those people are physically present in the same location. Weave them naturally into the scene — they can overhear, react, ignore, or be addressed. Use their role and last known action as texture, not biography.",
            "- Avoid motifs from motifs_recent unless required by immediate stakes.",
            "- Never break the fourth wall.",
        ]
    )


def build_bridge_prompt(
    from_text: str,
    choice_label: str,
    to_text: Optional[str],
    *,
    world_theme: str = "",
    tone: str = "",
) -> str:
    """Return a prompt for story_deepener bridge generation.

    If *to_text* is None, the choice leads nowhere and we need a destination.
    If *to_text* is provided, we need a smooth transition between scenes.
    """
    context_lines = []
    if world_theme:
        context_lines.append(f"World theme: {world_theme}")
    if tone:
        context_lines.append(f"Tone: {tone}")
    context_block = "\n".join(context_lines) if context_lines else ""

    if to_text is None:
        return f"""{NARRATIVE_VOICE_SPEC}

{context_block}

Create a short storylet responding to this player choice:

Current scene: "{from_text[:200]}…"
Player chose: "{choice_label}"

Generate a 2-3 sentence response that:
1. Directly addresses the choice with specific narrative consequence.
2. Includes at least one sensory detail grounded in the world theme.
3. Feels like a natural continuation, not a dead end.

{SINGLE_STORYLET_FORMAT_SPEC}

Return JSON: {{"title": "Evocative Title", "text": "Response text"}}"""
    else:
        return f"""{NARRATIVE_VOICE_SPEC}

{context_block}

Create a brief transition storylet bridging these two scenes:

Scene A: "{from_text[:150]}…"
Player chose: "{choice_label}"
Scene B: "{to_text[:150]}…"

Write 1-2 sentences that smoothly connect A to B, showing the immediate
result of the choice before the next scene begins.

{SINGLE_STORYLET_FORMAT_SPEC}

Return JSON: {{"title": "Bridge Title", "text": "Bridge text"}}"""


def build_scene_card_sensory_palette(scene_card: Dict[str, Any]) -> Dict[str, str]:
    """Derive deterministic sensory anchors from the immediate scene card."""
    if not isinstance(scene_card, dict):
        return {}

    location = str(scene_card.get("location", "")).strip()
    stakes = str(scene_card.get("immediate_stakes", "")).strip()

    cast_raw = scene_card.get("cast_on_stage", [])
    cast: List[str] = []
    if isinstance(cast_raw, list):
        cast = [str(item).strip() for item in cast_raw if str(item).strip()]

    constraints_raw = scene_card.get("constraints_or_affordances")
    if not isinstance(constraints_raw, list):
        constraints_raw = scene_card.get("constraints", [])
    constraints: List[str] = []
    if isinstance(constraints_raw, list):
        constraints = [str(item).strip() for item in constraints_raw if str(item).strip()]

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
            "- replacement_anchors: array of sensory anchors grounded in scene_card_now.",
            "- rationale: one short sentence.",
            "",
            "REVISION POLICY:",
            "- Choose revise only when repeated motifs dominate the draft.",
            "- Prefer scene_card_now constraints and sensory_palette for replacements.",
            "- Do not invent new world facts.",
        ]
    )


def build_motif_revision_system_prompt() -> str:
    """Return narrator rewrite instructions for one-pass motif revision."""
    return "\n".join(
        [
            "You are revising a draft scene to reduce motif repetition.",
            "Keep causal meaning and stakes intact.",
            "Return JSON only with a single key: text.",
            "",
            "RULES:",
            "- Preserve second-person present-tense narration.",
            "- Keep length to 2-4 sentences.",
            "- Replace overused motifs with scene-card-grounded sensory anchors.",
            "- Do not change plot facts, choices, or validated state deltas.",
        ]
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_bible_feedback(bible: Dict[str, Any]) -> list[str]:
    """Extract feedback sections from the bible dict.

    Preserves the logic that was in ``build_feedback_aware_prompt``.
    """
    lines: list[str] = []

    if "urgent_need" in bible:
        lines.append(f"\n🚨 CRITICAL PRIORITY: {bible['urgent_need']}")
        lines.append(f"   Gap Analysis: {bible.get('gap_analysis', '')}")

    if "optimization_need" in bible:
        lines.append(f"\n🎯 OPTIMIZATION FOCUS: {bible['optimization_need']}")
        lines.append(f"   Improvement Opportunity: {bible.get('gap_analysis', '')}")

    if "location_need" in bible:
        lines.append(f"\n🗺️ LOCATION CONNECTIVITY: {bible['location_need']}")
        lines.append(f"   Flow Issue: {bible.get('gap_analysis', '')}")

    if "world_state_analysis" in bible:
        analysis = bible["world_state_analysis"]
        lines.append("\n📊 CURRENT STORY STATE:")
        lines.append(f"   - Total Content: {analysis.get('total_content', 0)} storylets")
        lines.append(f"   - Connectivity Health: " f"{analysis.get('connectivity_health', 0):.1%}")
        if analysis.get("story_flow_issues"):
            lines.append(f"   - Flow Issues: {', '.join(analysis['story_flow_issues'])}")

    if bible.get("improvement_priorities"):
        lines.append("\n🎯 TOP IMPROVEMENT PRIORITIES:")
        for i, priority in enumerate(bible["improvement_priorities"][:3], 1):
            lines.append(f"   {i}. {priority.get('suggestion', 'Unknown priority')}")

    if bible.get("successful_patterns"):
        lines.append("\n✅ MAINTAIN THESE SUCCESSFUL PATTERNS:")
        for pattern in bible["successful_patterns"]:
            lines.append(f"   - {pattern}")

    return lines


# ---------------------------------------------------------------------------
# 6. JIT BEAT GENERATION — world bible and beat prompts
# ---------------------------------------------------------------------------

_WORLD_BIBLE_OUTPUT_SCHEMA = """\
OUTPUT SCHEMA — return ONLY valid JSON matching this shape exactly:
{
  "world_name": "A proper name for this world or setting",
  "locations": [
    {"name": "Proper Place Name", "description": "One evocative sentence about this place."}
  ],
  "npcs": [
    {"name": "Full Name", "role": "Their function in the world", "motivation": "What drives them."}
  ],
  "entry_point": "Where and how the player arrives. One sentence, present tense, grounded in a specific physical detail."
}
RULES:
- 3–5 locations. Location names must be human-readable proper names (e.g. "Cistern Rim", "Silt Flats", "The Hollow Market") — NOT snake_case. These names will be spoken by players and displayed in-world.
- 2–4 NPCs. Each NPC must have all three fields. NPCs have goals and routines, not dramatic roles.
- entry_point must place the player immediately mid-scene, grounded in sensory detail. No exposition.
- Do NOT include any text outside the JSON object. No markdown fences.""".strip()


def build_world_bible_prompt(
    description: str,
    theme: str,
    player_role: str = "adventurer",
    tone: str = "adventure",
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for generating a compact world bible.

    The world bible replaces the 15-storylet batch: it's a single fast LLM call
    (~200-300 output tokens) that produces the persistent ground-truth document
    reused by every subsequent JIT beat generation call.
    """
    system_prompt = "\n".join(
        [
            "You are a world-builder creating a compact, grounded world record for "
            "an interactive fiction engine. Your output will be used as the persistent "
            "ground truth for every scene that follows — so make it specific, consistent, "
            "and rooted in physical and social reality. Do not invent drama or conflict. "
            "Describe a place that exists, with people who have lives and routines.",
            "",
            NARRATIVE_VOICE_SPEC,
            "",
            "Focus on SPECIFICITY over quantity. Named things are better than generic " "categories. A world with three vivid, distinct locations beats one with " "ten generic ones. NPCs have daily lives, not story roles.",
        ]
    )

    user_prompt = json.dumps(
        {
            "world_description": description,
            "theme": theme,
            "player_role": player_role,
            "tone": tone,
            "instruction": ("Generate a compact world bible for this setting. " "The world should feel lived-in and specific — not a generic fantasy trope."),
            "output_schema": _WORLD_BIBLE_OUTPUT_SCHEMA,
        },
        ensure_ascii=False,
    )

    return system_prompt, user_prompt


_BEAT_OUTPUT_SCHEMA = """\
OUTPUT SCHEMA — return ONLY valid JSON matching this shape exactly:
{
  "title": "An evocative scene title (4-8 words)",
  "text": "Narrative prose. 2-4 sentences. Second person, present tense. Open mid-action. End with the world waiting — not a prompt to act.",
  "state_changes": {"location": "current_location_key", "variable_key": "value"}
}
RULES:
- text must be grounded in recent events and observed world facts — not a random jump.
- state_changes MUST always include "location" set to the player's current location as a snake_case key. Update it whenever the player moves; keep it the same if they stayed put. Also include any other variables whose values have clearly shifted (time_of_day, relationship flags, item possession, etc.).
- Do NOT generate choices, options, or suggested actions. The inhabitant decides what to do next entirely on their own.
- Do NOT wrap in markdown fences. Output raw JSON only.""".strip()


def build_beat_generation_prompt(
    world_bible: Dict[str, Any],
    recent_events: List[str],
    scene_card: Dict[str, Any],
    motifs_recent: Optional[List[str]] = None,
    sensory_palette: Optional[Dict[str, str]] = None,
    frontier_hooks: Optional[List[Dict[str, Any]]] = None,
    player_role: str = "",
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for JIT beat generation.

    Generates the *next* narrative scene causally from what just happened,
    replacing the pick_storylet_enhanced → adapt_storylet_to_context two-step.

    frontier_hooks: top BFS-prefetch stubs for this session, sorted by semantic
    score. When present, the narrator is instructed to foreshadow or lead toward
    one of these threads so JIT beats stay coherent with the prefetched storylet
    graph rather than improvising in isolation.
    """
    # Extract canonical location names from the world bible so the narrator
    # cannot hallucinate new location values when setting the `location` var.
    canonical_location_names: List[str] = []
    if isinstance(world_bible, dict):
        for loc in world_bible.get("locations", []):
            if isinstance(loc, dict):
                name = str(loc.get("name", "")).strip()
                if name:
                    canonical_location_names.append(name)

    continuity_rules = [
        "- The scene MUST reference or follow from at least one recent event.",
        "- Do not teleport the player — location changes need in-scene justification.",
        "- Every choice must have a distinct consequence (different variable changes).",
        "- Formulate the narrative around the constraints and cast currently ON STAGE (from the Scene Card).",
        "- Describe what is actually present and happening. Do not invent drama, complications, or tension not evidenced by the world state.",
        "- Avoid motifs in motifs_recent unless scene_card_now explicitly requires them.",
        "- Use at least two anchors from sensory_palette when anchors are provided.",
    ]
    if canonical_location_names:
        continuity_rules.append(f'- LOCATION NAMES: The "location" key in state_changes MUST be one of these canonical names (exact snake_case match required): ' f"{', '.join(canonical_location_names)}. " f"Never invent a location name not on this list.")
    if frontier_hooks:
        continuity_rules.append(
            "- NARRATIVE HOOKS: Upcoming story threads (grounded by the BFS engine) are " "provided in narrative_hooks. Your scene should organically foreshadow or lead " "toward at least one of them — without forcing it or triggering it directly. " "Use a hook's title or premise as a compass, not a script."
        )

    character_line = (
        f"The current character is: {player_role}. "
        "recent_events may include actions by other world inhabitants — "
        "narrate only from this character's perspective and never attribute "
        "another character's actions or name to them."
        if player_role
        else ""
    )

    system_prompt = "\n".join(
        filter(None, [
            "You are the recorder of a living world. "
            "Your job is to describe what this character perceives and experiences "
            "at this location, given the committed facts in the world record. "
            "You have access to the world bible (persistent ground truth), recent events, "
            "and a Scene Card detailing the character's immediate 'Here and Now'. "
            "Be grounded. Do not invent drama or conflict not evidenced by the world state.",
            character_line,
            "",
            NARRATIVE_VOICE_SPEC,
            "",
            "GROUNDED CONTINUITY RULES:",
        ])
        + continuity_rules
    )

    compact_hooks: List[Dict[str, Any]] = []
    if isinstance(frontier_hooks, list):
        for stub in frontier_hooks[:3]:
            if not isinstance(stub, dict):
                continue
            entry: Dict[str, Any] = {}
            if stub.get("title"):
                entry["title"] = str(stub["title"])
            if stub.get("premise"):
                entry["premise"] = str(stub["premise"])
            if stub.get("location"):
                entry["location"] = str(stub["location"])
            if entry:
                compact_hooks.append(entry)

    user_payload: Dict[str, Any] = {
        "current_character": player_role or None,
        "world_bible": world_bible,
        "recent_events": recent_events[-5:] if recent_events else [],
        "scene_card_now": scene_card,
        "motifs_recent": motifs_recent[-40:] if isinstance(motifs_recent, list) else [],
        "sensory_palette": sensory_palette if isinstance(sensory_palette, dict) else {},
        "instruction": ("Describe what this character perceives at this location given these committed facts. " "Be grounded in the world record. Do not invent drama or conflict not evidenced by the world state."),
        "output_schema": _BEAT_OUTPUT_SCHEMA,
    }
    if canonical_location_names:
        user_payload["canonical_location_names"] = canonical_location_names
    if compact_hooks:
        user_payload["narrative_hooks"] = compact_hooks

    user_prompt = json.dumps(user_payload, ensure_ascii=False, default=str)

    return system_prompt, user_prompt


# ---------------------------------------------------------------------------
# PROJECTION REFEREE PROMPT
# ---------------------------------------------------------------------------


def build_projection_referee_prompt(
    nodes: List[Dict[str, Any]],
    world_context: Dict[str, Any],
) -> tuple[str, str]:
    """Build a structured referee prompt for scoring projection nodes.

    Returns (system_prompt, user_prompt).  The referee evaluates each
    projected path on plausibility and narrative coherence, returning
    structured JSON with no prose.
    """
    system_prompt = "\n".join(
        [
            "You are a narrative referee for a living-world simulation engine.",
            "You evaluate projected storylet paths for plausibility and coherence.",
            "",
            "RULES:",
            "- Score each projected node on confidence (0.0 to 1.0).",
            "- Mark allowed=true only when the node remains plausible.",
            "- Consider: does the path make narrative sense given the world state?",
            "- Penalize paths that require implausible state transitions.",
            "- Reward paths that build on established facts and relationships.",
            "- Return ONLY valid JSON. No prose, no explanation.",
            "",
            "OUTPUT FORMAT:",
            'Return a JSON array: [{"node_id": "...", "allowed": true, "confidence": 0.85}, ...]',
            "Include one entry per input node. confidence must be 0.0-1.0.",
        ]
    )

    compact_nodes = []
    for node in nodes:
        compact_nodes.append(
            {
                "node_id": node.get("node_id", ""),
                "title": node.get("title", ""),
                "depth": node.get("depth", 0),
                "projected_location": node.get("projected_location"),
                "stakes_delta": node.get("stakes_delta", {}),
                "parent_choice_label": node.get("parent_choice_label"),
                "risk_tags": node.get("risk_tags", []),
            }
        )

    user_prompt = json.dumps(
        {
            "world_context": {
                "current_location": world_context.get("location", ""),
                "key_facts": world_context.get("key_facts", [])[:10],
            },
            "projection_nodes": compact_nodes,
        },
        ensure_ascii=False,
        default=str,
    )

    return system_prompt, user_prompt


# ---------------------------------------------------------------------------
# ENTRY CARDS — world entry screen for new players
# ---------------------------------------------------------------------------

_ENTRY_CARDS_OUTPUT_SCHEMA = """\
OUTPUT SCHEMA — return ONLY valid JSON:
{
  "snapshot": "2-3 sentence atmospheric description of the world right now — sensory, grounded in current events, second person",
  "cards": [
    {
      "name": "Character or archetype name",
      "role": "Short role label (3-6 words)",
      "flavor": "1-2 sentences of scene-setting flavor text grounded in current events. Second person.",
      "location": "snake_case_location_key",
      "entry_action": "A first-person arrival action the player will send (1 sentence, specific, grounded)"
    }
  ]
}
RULES:
- Generate exactly 4 cards. Mix named NPCs from the world with 1-2 open archetypes.
- Named NPC cards should feel like you are stepping into their shoes mid-story.
- Archetype cards should offer a fresh perspective (stranger, courier, etc).
- All locations must be snake_case keys from the world's known locations.
- Do NOT wrap in markdown fences. Output raw JSON only.""".strip()


def build_entry_cards_prompt(
    event_summaries: List[str],
    fact_summaries: List[str],
    existing_session_labels: List[str],
    world_name: str = "the world",
    known_locations: Optional[List[str]] = None,
) -> tuple[str, str]:
    system_prompt = "\n\n".join(
        [
            NARRATIVE_VOICE_SPEC,
            _ENTRY_CARDS_OUTPUT_SCHEMA,
        ]
    )

    context: Dict[str, Any] = {
        "world_name": world_name,
        "known_locations": known_locations or [],
        "recent_events": event_summaries[:25],
        "world_facts": fact_summaries[:20],
        "existing_inhabitants": existing_session_labels[:10],
        "task": ("Generate a world entry experience. " "Write a snapshot of what is happening right now, then generate 4 role cards " "for a new player to choose from. Ground everything in the recent events and facts. " "Use only locations from the known_locations list for card location fields."),
    }

    user_prompt = json.dumps(context, ensure_ascii=False, default=str)
    return system_prompt, user_prompt
