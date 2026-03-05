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

WORLD VARIABLE DESIGN:
- Extract 3-5 key concepts from the description and make them trackable variables.
- Use location names that fit this specific world.
- Create resource/status/relationship variables meaningful to this universe.
- Ensure variables connect storylets into a narrative web where choices matter.

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
            "- Weave in recent events naturally, don't just append them.",
            "- Match the environment (weather, time, danger) in your descriptions.",
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
            "- The player cannot teleport to a location they haven't traveled to.",
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
            "- Keep narration to 2-4 sentences.",
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
    {"name": "location_key", "description": "One evocative sentence about this place."}
  ],
  "npcs": [
    {"name": "Full Name", "role": "Their function in the world", "motivation": "What drives them."}
  ],
  "central_tension": "The one question or conflict that gives this world its energy.",
  "entry_point": "Where and how the player arrives. One sentence, present tense."
}
RULES:
- 3–5 locations. Location names should be snake_case (used as variable keys).
- 2–4 NPCs. Each NPC must have all three fields.
- central_tension should be a single sentence — the dramatic engine of the world.
- entry_point must place the player immediately mid-scene, no exposition.
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
            "You are a world-builder creating a compact, evocative world bible for " "an interactive fiction engine. Your output will be used as the persistent " "ground truth for every scene that follows — so make it specific, consistent, " "and full of narrative potential.",
            "",
            NARRATIVE_VOICE_SPEC,
            "",
            "Focus on SPECIFICITY over quantity. Named things are better than generic " "categories. A world with three vivid, distinct locations beats one with " "ten generic ones.",
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
  "text": "Narrative prose. 2-4 sentences. Second person, present tense. Open mid-action.",
  "tension": "A single sentence describing the current dramatic tension or immediate stakes.",
  "unresolved_threads": [
    "A short phrase describing a narrative loose end or unpursued lead."
  ],
  "choices": [
    {"label": "Choice label hinting at consequence", "set": {"variable_key": "value"}}
  ]
}
RULES:
- 2–3 choices. Each choice MUST set at least one variable differently from the others.
- The text must causally follow from the most recent event — not a random jump.
- tension and unresolved_threads must be populated based on the scene's stakes and dropped hints. Keep unresolved_threads to 1-3 items.
- Do NOT include a 'requires' field — beats are generated contextually so they are always relevant.
- Do NOT wrap in markdown fences. Output raw JSON only.""".strip()


def build_beat_generation_prompt(
    world_bible: Dict[str, Any],
    recent_events: List[str],
    scene_card: Dict[str, Any],
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for JIT beat generation.

    Generates the *next* narrative scene causally from what just happened,
    replacing the pick_storylet_enhanced → adapt_storylet_to_context two-step.
    """
    system_prompt = "\n".join(
        [
            "You are the narrator of a living interactive fiction world. "
            "Your job is to write the NEXT scene that causally follows from "
            "what just happened to the player. You have access to the world bible "
            "(the persistent ground truth), recent events, and a highly focused "
            "Scene Card detailing the player's immediate 'Here and Now'.",
            "",
            NARRATIVE_VOICE_SPEC,
            "",
            "CAUSAL CONTINUITY RULES:",
            "- The scene MUST reference or follow from at least one recent event.",
            "- Do not teleport the player — location changes need in-scene justification.",
            "- Every choice must have a distinct consequence (different variable changes).",
            "- Formulate the narrative around the constraints and cast currently ON STAGE (from the Scene Card).",
            "- The scene MUST respect the player's active goal and its stated urgency. Introduce complications if urgency is high or stakes are raised.",
        ]
    )

    user_prompt = json.dumps(
        {
            "world_bible": world_bible,
            "recent_events": recent_events[-5:] if recent_events else [],
            "scene_card_now": scene_card,
            "instruction": ("Write the next scene that causally follows from these events. " "Ground it in the world bible. Ensure the narrative reflects and reacts to the player's active goal, physical constraints, and the immediate stakes."),
            "output_schema": _BEAT_OUTPUT_SCHEMA,
        },
        ensure_ascii=False,
        default=str,
    )

    return system_prompt, user_prompt
