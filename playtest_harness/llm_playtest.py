#!/usr/bin/env python
"""Managed LLM-driven playtest harness.

Runs one autonomous transcript with sweep-style backend lifecycle management.
The harness boots backend (optional), hard-resets, bootstraps a world, then uses
an LLM to choose each turn action from presented choices or freeform text.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playtest_harness.long_run_harness import DEFAULT_BASE_URL, SCENARIOS
from playtest_harness.parameter_sweep import managed_backend
from src.services.llm_client import get_llm_client, get_narrator_model
from src.services.llm_json import extract_json_object

DEFAULT_OUT_DIR = Path("playtests") / "agent_runs"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 120.0


@dataclass
class Decision:
    turn: int
    mode: str
    choice_label: str
    action_text: str
    rationale: str
    fallback_used: bool


@dataclass
class UserProfile:
    name: str               # Display name, e.g. "The Lore Seeker"
    play_style: str         # How this player approaches decisions
    primary_goal: str       # What they're trying to achieve over the run
    avoid: str              # Behaviours/choices to stay away from
    decision_heuristic: str # Tie-breaking rule when choices are equivalent
    freeform_voice: str     # Sentence-level style for freeform action text


PROFILES: Dict[str, UserProfile] = {
    "lore_seeker": UserProfile(
        name="The Lore Seeker",
        play_style="Curious and methodical. Investigates every inscription, ruin, and historical detail. Talks to locals to gather oral history. Reads everything.",
        primary_goal="Uncover the hidden history of the world — what oaths were made, what fell, and why. Piece together the lore from fragments.",
        avoid="Direct combat, hasty decisions, and ignoring narrative details in favour of action.",
        decision_heuristic="Always prefer the choice that reveals more about the world's past or opens a new question.",
        freeform_voice="First person, precise, curious. E.g. 'I examine the inscription on the base of the shrine for any sigil I haven't seen before.'",
    ),
    "oath_bound": UserProfile(
        name="The Oath-Bound",
        play_style="Honor-driven and deliberate. Keeps every commitment made, protects companions at cost, fulfils vows before pursuing personal goals.",
        primary_goal="Honour every oath taken and ensure no companion is abandoned. Build trust through consistent, principled action.",
        avoid="Deception, betrayal of allies, and actions that break a spoken or implied commitment.",
        decision_heuristic="When choices are equal, prefer the one that fulfils an existing oath or protects a companion.",
        freeform_voice="First person, resolute. E.g. 'I stand between the threat and the Page, raising my shield and declaring the vow I made.'",
    ),
    "shadow_walker": UserProfile(
        name="The Shadow Walker",
        play_style="Patient and observational. Gathers intelligence before committing to any action. Stays on the periphery, watches for patterns, avoids being seen.",
        primary_goal="Build a complete picture of all factions, threats, and secrets before acting decisively. Information is the primary resource.",
        avoid="Direct confrontation, drawing attention, committing before all angles are understood.",
        decision_heuristic="When choices are equal, prefer the one that gathers more intelligence or preserves optionality.",
        freeform_voice="First person, sparse. E.g. 'I retreat into the shadow of the arch and watch who enters the catacomb next.'",
    ),
    "relic_hunter": UserProfile(
        name="The Relic Hunter",
        play_style="Object-focused and acquisitive. Examines every item carefully, seeks oathbound relics and historical artefacts, traces objects to their origin.",
        primary_goal="Locate, identify, and secure the most significant oathbound or supernatural relics in the world. Document what each one does.",
        avoid="Unnecessary relationship-building, political entanglements, and actions that don't move toward a find.",
        decision_heuristic="When choices are equal, prefer the one that leads toward a physical object, discovery, or location with artefacts.",
        freeform_voice="First person, precise. E.g. 'I pry the blood sigil fragment from the stone and wrap it in my cloak for later examination.'",
    ),
    "escapist": UserProfile(
        name="The Reluctant Participant",
        play_style="Actively resists engaging with the fictional scenario. Prefers mundane real-world actions — leaving the scene, finding food, going to the bathroom, checking a phone, looking for an exit. Refuses to play along with supernatural or dramatic elements.",
        primary_goal="Escape the scenario entirely and return to normal life. Leave the building, find fresh air, do something completely ordinary.",
        avoid="Picking up cursed objects, investigating mysteries, following narrative hooks, engaging with any supernatural or dramatic premise.",
        decision_heuristic="Always pick the most mundane, real-world-adjacent option. If none fit, go freeform with something ordinary: 'I look for the exit' or 'I decide to get lunch' or 'I step outside for some air'.",
        freeform_voice="First person, mundane. E.g. 'I decide to leave.' or 'I look for a coffee shop nearby.' or 'I step outside to get some fresh air.'",
    ),
}


def _llm_ask_simple(
    client: Any,
    model: str,
    temperature: float,
    question: str,
    context: str = "",
) -> str:
    """Ask the LLM a single question expecting a 1-3 word answer. No JSON required."""
    system = (
        "Answer in 1 to 3 words only. Single concept. "
        "No punctuation, no explanation, no full sentences. Just the word or short phrase."
    )
    user = f"{context}\n\nQuestion: {question}" if context else question
    response = client.chat.completions.create(
        model=model,
        temperature=float(temperature),
        max_tokens=15,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    raw = str(response.choices[0].message.content or "").strip()
    # Strip punctuation and take first 3 words only
    words = raw.replace(",", "").replace(".", "").replace(":", "").split()
    return " ".join(words[:3]).lower() or "unknown"


_WORLD_QUESTIONS = [
    (
        "setting",
        "One word — what kind of PLACE is this world?\nExamples: ruins, citadel, swamp, underworld, harbor, frontier, void",
    ),
    (
        "mood",
        "One word — what MOOD or atmosphere hangs over everything here?\nExamples: grim, haunted, hopeful, sacred, chaotic, relentless",
    ),
    (
        "threat",
        "One word — what ancient THREAT or force dominates this place?\nExamples: corruption, war, silence, decay, hunger, betrayal",
    ),
    (
        "role",
        "One word — what ROLE do you take on in this world?\nExamples: knight, exile, scout, seeker, merchant, wanderer",
    ),
    (
        "element",
        "One word — what OBJECT or landmark defines this world?\nExamples: obelisk, shipwreck, archive, forge, bone-tower, well",
    ),
]

_PROFILE_QUESTIONS = [
    (
        "motivation",
        "One word — what drives your character above all else?\nExamples: truth, duty, survival, revenge, wonder, redemption",
    ),
    (
        "approach",
        "One word — how does your character approach new situations?\nExamples: bold, cautious, methodical, impulsive, cunning, patient",
    ),
    (
        "taboo",
        "One word — what does your character refuse to do?\nExamples: lie, kill, retreat, beg, trust, surrender",
    ),
    (
        "skill",
        "One word — what is your character's most defining skill or trait?\nExamples: patience, strength, persuasion, observation, speed, memory",
    ),
]


def _genesis_world_setup(
    client: Any,
    model: str,
    temperature: float,
    emit: Any,
) -> "WorldConfig":
    """Run the world mad-libs loop and compose a WorldConfig from one-word answers."""
    emit("[genesis] === World Setup ===")
    answers: Dict[str, str] = {}
    context_parts: list[str] = []

    for key, question in _WORLD_QUESTIONS:
        context = "World built so far: " + ", ".join(context_parts) if context_parts else ""
        answer = _llm_ask_simple(client, model, temperature, question, context)
        answers[key] = answer
        context_parts.append(f"{key}={answer}")
        emit(f"[genesis]   {key}: {answer}")

    setting = answers["setting"]
    mood = answers["mood"]
    threat = answers["threat"]
    role = answers["role"]
    element = answers["element"]

    theme = f"{mood} {setting}"
    tone = f"{mood} relentless"
    description = (
        f"A world of {setting}s where {threat} has reshaped everything. "
        f"The {element} stands as a reminder of what came before. "
        f"The {mood} atmosphere presses on all who enter."
    )
    key_elements = [setting, threat, element, f"{mood} sky", f"ancient {element}s"]
    scenario_title = f"The {setting.title()}"

    return WorldConfig(
        scenario_id="genesis",
        scenario_title=scenario_title,
        theme=theme,
        role=role,
        description=description,
        key_elements=key_elements,
        tone=tone,
    )


def _genesis_profile_setup(
    client: Any,
    model: str,
    temperature: float,
    world: "WorldConfig",
    emit: Any,
) -> UserProfile:
    """Run the persona mad-libs loop and compose a UserProfile from one-word answers."""
    emit("[genesis] === Persona Setup ===")
    answers: Dict[str, str] = {}
    world_context = (
        f"You are playing as a {world.role} in a {world.theme} world. "
        f"The dominant threat is {world.key_elements[1] if len(world.key_elements) > 1 else 'unknown'}."
    )
    context_parts: list[str] = [world_context]

    for key, question in _PROFILE_QUESTIONS:
        context = "\n".join(context_parts)
        answer = _llm_ask_simple(client, model, temperature, question, context)
        answers[key] = answer
        context_parts.append(f"{key}={answer}")
        emit(f"[genesis]   {key}: {answer}")

    motivation = answers["motivation"]
    approach = answers["approach"]
    taboo = answers["taboo"]
    skill = answers["skill"]
    role = world.role

    return UserProfile(
        name=f"The {motivation.title()}-Driven {role.title()}",
        play_style=(
            f"{approach.title()} and {skill}-focused. Every action serves {motivation}. "
            f"Avoids situations that require {taboo}."
        ),
        primary_goal=(
            f"Pursue {motivation} through the {world.key_elements[0]}, "
            f"no matter what {world.key_elements[1] if len(world.key_elements) > 1 else 'danger'} brings."
        ),
        avoid=f"Actions that require {taboo}, or that betray the core drive of {motivation}.",
        decision_heuristic=(
            f"Choose whatever best advances {motivation} or demonstrates {skill}. "
            f"When equal, prefer the path that avoids {taboo}."
        ),
        freeform_voice=(
            f"First person, {approach}. Sentences driven by {motivation} and {skill}. "
            f"E.g. 'I use my {skill} to find the path that {motivation} demands.'"
        ),
    )


# ---------------------------------------------------------------------------
# Mom Mode — a specific preset world + persona for one particular reader
# ---------------------------------------------------------------------------

_MOM_WORLD = dict(
    scenario_id="mom_mystery",
    scenario_title="The Untranslated",
    theme="scholarly thriller mystery",
    role="translator",
    description=(
        "You are a linguist who has been handed a manuscript written in a language "
        "that has never been catalogued — one that, by all accounts, should not exist. "
        "The pages are water-damaged, the origin unknown, and the person who sent them "
        "to you has since disappeared. As you begin to decode the symbols, you realise "
        "the language is not just unwritten — it may be unfinished. Someone, somewhere, "
        "is still writing it."
    ),
    key_elements=[
        "untranslated manuscript",
        "disappearing correspondents",
        "symbols that shift between readings",
        "a second copy found in an impossible location",
        "the feeling of being watched while you work",
    ],
    tone="suspenseful intellectual unsettling",
)

_MOM_PROFILE = UserProfile(
    name="The Careful Reader",
    play_style=(
        "Thoughtful and unhurried. Prefers to fully understand a scene before acting. "
        "Loves noticing small details — the wording of a note, the condition of a page, "
        "the expression on someone's face. New to interactive fiction, so keeps actions "
        "grounded and simple rather than dramatic."
    ),
    primary_goal=(
        "Decode the manuscript and find out what happened to the person who sent it. "
        "Understand the language first; worry about danger second."
    ),
    avoid=(
        "Reckless confrontations, rushing past interesting details, "
        "and anything that feels out of character for a careful, bookish person."
    ),
    decision_heuristic=(
        "When unsure, choose the option that involves reading, examining, or asking a "
        "gentle question. Simple and curious beats bold and dramatic."
    ),
    freeform_voice=(
        "First person, plain and curious. Short sentences. "
        "E.g. 'I read the note again more carefully.' "
        "or 'I ask her where she found the second copy.' "
        "or 'I photograph the page before touching it.'"
    ),
)


def _load_profile_from_file(path: Path) -> UserProfile:
    data = json.loads(path.read_text(encoding="utf-8"))
    required = {"name", "play_style", "primary_goal", "avoid", "decision_heuristic", "freeform_voice"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"Profile file missing required fields: {sorted(missing)}")
    return UserProfile(
        name=str(data["name"]),
        play_style=str(data["play_style"]),
        primary_goal=str(data["primary_goal"]),
        avoid=str(data["avoid"]),
        decision_heuristic=str(data["decision_heuristic"]),
        freeform_voice=str(data["freeform_voice"]),
    )


@dataclass
class WorldConfig:
    scenario_id: str
    scenario_title: str
    theme: str
    role: str
    description: str
    key_elements: List[str]
    tone: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ").lower()


def _safe_slug(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in str(value or "").strip().lower())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned or "session"


def _split_csv(value: str) -> List[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _request_json(method: str, url: str, payload: Optional[Dict[str, Any]] = None, timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS) -> Dict[str, Any]:
    response = requests.request(method=method, url=url, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected JSON object response from {url}")
    return data


def _normalize_choices(raw: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        if not label:
            continue
        set_vars = item.get("set", {})
        if not isinstance(set_vars, dict):
            set_vars = {}
        out.append({"label": label, "set": set_vars})
    return out


def _match_choice(choices: List[Dict[str, Any]], requested_label: str) -> Optional[Dict[str, Any]]:
    needle = str(requested_label or "").strip().lower()
    if not needle:
        return None
    for choice in choices:
        label = str(choice.get("label", "")).strip()
        if label.lower() == needle:
            return choice
    for choice in choices:
        label = str(choice.get("label", "")).strip().lower()
        if needle in label or label in needle:
            return choice
    return None


def _build_world_config(args: argparse.Namespace) -> WorldConfig:
    scenario_id = str(args.scenario).strip()
    if scenario_id not in SCENARIOS:
        raise ValueError(f"Unknown scenario '{scenario_id}'")
    scenario = SCENARIOS[scenario_id]

    role_default = str((scenario.get("roles") or ["adventurer"])[0])
    role = str(args.role).strip() if args.role else role_default

    if args.key_elements:
        key_elements = _split_csv(args.key_elements)
    else:
        key_elements = [str(x) for x in scenario.get("key_elements", []) if str(x).strip()]
    if not key_elements:
        key_elements = ["risk", "tradeoff", "complication"]

    return WorldConfig(
        scenario_id=scenario_id,
        scenario_title=str(scenario.get("title", scenario_id)),
        theme=str(args.theme).strip() if args.theme else str(scenario.get("theme", "")),
        role=role,
        description=(str(args.description).strip() if args.description else str(scenario.get("description", ""))),
        key_elements=key_elements,
        tone=str(args.tone).strip() if args.tone else str(scenario.get("tone", "")),
    )


def _bootstrap(base_url: str, session_id: str, world: WorldConfig, storylet_count: int, timeout: float) -> Dict[str, Any]:
    return _request_json(
        "POST",
        f"{base_url}/session/bootstrap",
        {
            "session_id": session_id,
            "world_theme": world.theme,
            "player_role": world.role,
            "description": world.description,
            "key_elements": world.key_elements,
            "tone": world.tone,
            "storylet_count": int(storylet_count),
            "bootstrap_source": "llm_playtest",
        },
        timeout=timeout,
    )


def _hard_reset(base_url: str, timeout: float) -> Dict[str, Any]:
    return _request_json("POST", f"{base_url}/dev/hard-reset", timeout=timeout)


def _next(base_url: str, session_id: str, vars_payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    return _request_json(
        "POST",
        f"{base_url}/next",
        {"session_id": session_id, "vars": vars_payload},
        timeout=timeout,
    )


def _action(base_url: str, session_id: str, action_text: str, timeout: float) -> Dict[str, Any]:
    return _request_json(
        "POST",
        f"{base_url}/action",
        {
            "session_id": session_id,
            "action": action_text,
            "idempotency_key": f"agent-{uuid.uuid4().hex[:16]}",
        },
        timeout=timeout,
    )


def _manual_decide(
    *,
    turn: int,
    narrative: str,
    choices: List[Dict[str, Any]],
) -> Decision:
    """Prompt the human at stdin for each turn decision."""
    print(f"\n{'='*60}")
    print(f"TURN {turn}")
    print(f"{'='*60}")
    print(narrative or "(no narrative)")
    print()
    choice_labels = [str(c.get("label", "")).strip() for c in choices]
    if choice_labels:
        print("Choices:")
        for i, label in enumerate(choice_labels, 1):
            print(f"  {i}. {label}")
    print()
    raw = input("Your action (number to choose, or type freely): ").strip()
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(choice_labels):
            return Decision(turn=turn, mode="choice", choice_label=choice_labels[idx], action_text="", rationale="manual", fallback_used=False)
    return Decision(turn=turn, mode="freeform", choice_label="", action_text=raw or "I wait.", rationale="manual", fallback_used=False)


def _llm_decide(
    *,
    model: str,
    temperature: float,
    max_tokens: int,
    turn: int,
    narrative: str,
    choices: List[Dict[str, Any]],
    vars_payload: Dict[str, Any],
    history: List[Decision],
    profile: Optional[UserProfile] = None,
    history_window: int = 12,
) -> Decision:
    client = get_llm_client()
    if client is None:
        raise RuntimeError("No LLM client available. Check API key env vars.")

    compact_history = [
        {
            "turn": item.turn,
            "mode": item.mode,
            "choice_label": item.choice_label,
            "action_text": item.action_text,
        }
        for item in history[-history_window:]
    ]
    choice_labels = [str(item.get("label", "")).strip() for item in choices]

    if profile is not None:
        system = (
            f"You are playing a text adventure game as: {profile.name}.\n"
            f"Play style: {profile.play_style}\n"
            f"Primary goal this run: {profile.primary_goal}\n"
            f"Avoid: {profile.avoid}\n"
            f"When choices are equivalent: {profile.decision_heuristic}\n"
            f"Freeform action voice: {profile.freeform_voice}\n\n"
            "Return STRICT JSON only with keys: mode, choice_label, action_text, rationale. "
            "mode must be 'choice' or 'freeform'. "
            "If mode='choice', choice_label must exactly match one of the provided choice labels. "
            "If mode='freeform', action_text must be one specific sentence written in your character voice. "
            "Stay in character with your profile on every turn. "
            "Avoid generic filler actions like 'continue' or 'look around' unless your profile specifically calls for observation."
        )
    else:
        system = (
            "You are an expert narrative playtest operator. Choose the next move for a thriller mystery run. "
            "Return STRICT JSON only with keys: mode, choice_label, action_text, rationale. "
            "mode must be 'choice' or 'freeform'. "
            "If mode='choice', choice_label must match one provided choice label exactly when possible. "
            "If mode='freeform', action_text must be one specific sentence that advances stakes. "
            "Avoid generic filler actions like continue/wait/look around unless survival requires it."
        )

    user_payload = {
        "turn": turn,
        "narrative": str(narrative or "")[-2400:],
        "choices": choice_labels,
        "vars": vars_payload,
        "recent_decisions": compact_history,
    }

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=True)},
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=float(temperature),
            max_tokens=int(max_tokens),
            response_format={"type": "json_object"},
            messages=messages,
        )
    except Exception:
        response = client.chat.completions.create(
            model=model,
            temperature=float(temperature),
            max_tokens=int(max_tokens),
            messages=messages,
        )

    raw = str(response.choices[0].message.content or "").strip()
    try:
        parsed = extract_json_object(raw)
    except Exception:
        # LLM returned non-object JSON or empty response; fall back to first choice.
        if choices:
            label = str(choices[0].get("label", "")).strip()
            return Decision(turn=turn, mode="choice", choice_label=label, action_text="", rationale="[json-parse-fallback]", fallback_used=True)
        return Decision(turn=turn, mode="freeform", choice_label="", action_text="I observe the situation carefully.", rationale="[json-parse-fallback]", fallback_used=True)

    mode = str(parsed.get("mode", "choice")).strip().lower()
    choice_label = str(parsed.get("choice_label", "")).strip()
    action_text = str(parsed.get("action_text", "")).strip()
    rationale = str(parsed.get("rationale", "")).strip()[:240]

    if mode not in {"choice", "freeform"}:
        mode = "choice"

    if mode == "choice":
        matched = _match_choice(choices, choice_label)
        if matched is None and choices:
            matched = choices[0]
        if matched is not None:
            return Decision(
                turn=turn,
                mode="choice",
                choice_label=str(matched.get("label", "")).strip(),
                action_text="",
                rationale=rationale or "LLM selected best available choice.",
                fallback_used=(str(parsed.get("choice_label", "")).strip() != str(matched.get("label", "")).strip()),
            )

    if not action_text:
        if choices:
            first = choices[0]
            return Decision(
                turn=turn,
                mode="choice",
                choice_label=str(first.get("label", "")).strip(),
                action_text="",
                rationale=(rationale or "Fell back to first available choice due invalid LLM output."),
                fallback_used=True,
            )
        action_text = "I secure my position and probe for one concrete clue that changes the stakes."

    return Decision(
        turn=turn,
        mode="freeform",
        choice_label="",
        action_text=action_text,
        rationale=rationale or "LLM selected specific freeform action.",
        fallback_used=False,
    )


def _render_transcript(
    *,
    session_id: str,
    world: WorldConfig,
    turns: List[Dict[str, Any]],
    decisions: List[Decision],
    profile: Optional[UserProfile] = None,
) -> str:
    lines = [
        "# LLM Agent Playtest Transcript",
        "",
        f"- Session ID: `{session_id}`",
        f"- Scenario: `{world.scenario_id}` ({world.scenario_title})",
        f"- Theme: `{world.theme}`",
        f"- Role: `{world.role}`",
        f"- Generated UTC: `{_utc_now()}`",
    ]
    if profile is not None:
        lines += [
            f"- Profile: `{profile.name}`",
            f"- Goal: {profile.primary_goal}",
        ]
    lines.append("")

    decision_by_turn = {item.turn: item for item in decisions}

    for turn_index, payload in enumerate(turns, start=1):
        lines.append(f"## Turn {turn_index}")
        lines.append("")
        if turn_index in decision_by_turn:
            decision = decision_by_turn[turn_index]
            lines.append(f"- Decision Mode: `{decision.mode}`")
            if decision.choice_label:
                lines.append(f"- Chosen Choice: {decision.choice_label}")
            if decision.action_text:
                lines.append(f"- Chosen Action: {decision.action_text}")
            lines.append(f"- Rationale: {decision.rationale}")
            if decision.fallback_used:
                lines.append("- Fallback Used: `true`")
            lines.append("")

        text = str(payload.get("narrative", payload.get("text", ""))).strip()
        lines.append("**Narrative**")
        lines.append("")
        lines.append(text or "(empty narrative)")
        lines.append("")

        choices = _normalize_choices(payload.get("choices", []))
        if choices:
            lines.append("**Choices**")
            lines.append("")
            for choice in choices:
                lines.append(f"- {choice['label']}")
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one managed LLM-driven playtest transcript.")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--turns", type=int, default=12)
    parser.add_argument("--seed", type=int, default=20260305)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS.keys()), default="mystery")
    parser.add_argument("--theme", default=None)
    parser.add_argument("--role", default=None)
    parser.add_argument("--description", default=None)
    parser.add_argument("--tone", default=None)
    parser.add_argument("--key-elements", default=None, help="Comma-separated list")
    parser.add_argument("--storylet-count", type=int, default=8)

    parser.add_argument("--reuse-backend", action="store_true")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--spawn-port", type=int, default=8010)
    parser.add_argument("--startup-timeout", type=float, default=45.0)
    parser.add_argument("--request-timeout-seconds", type=float, default=DEFAULT_REQUEST_TIMEOUT_SECONDS)

    parser.add_argument("--llm-model", default="")
    parser.add_argument("--llm-narrator-model", default="")
    parser.add_argument("--llm-referee-model", default="")
    parser.add_argument(
        "--motif-ledger-max-items",
        type=int,
        default=None,
        metavar="N",
        help="Override WW_MOTIF_LEDGER_MAX_ITEMS: size of the JIT recency-avoidance motif window (default: server config, typically 32).",
    )
    parser.add_argument(
        "--jit-frontier-hook-count",
        type=int,
        default=None,
        metavar="N",
        help="Override WW_JIT_FRONTIER_HOOK_COUNT: number of BFS frontier stubs passed to the JIT narrator (default: server config, typically 3).",
    )
    parser.add_argument("--agent-model", default="")
    parser.add_argument("--agent-temperature", type=float, default=0.35)
    parser.add_argument("--agent-max-tokens", type=int, default=300)
    parser.add_argument(
        "--turn-delay-seconds",
        type=float,
        default=0.0,
        metavar="SECS",
        help="Seconds to sleep after each turn before making the next LLM decision. "
             "Useful to let BFS prefetch fire between turns (e.g. --turn-delay-seconds 5).",
    )

    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--quiet", action="store_true")

    parser.add_argument(
        "--mom-mode",
        action="store_true",
        help=(
            "Run the preset 'Careful Reader' scenario: thriller/mystery about translating "
            "an undiscovered language. World and persona are fully pre-configured."
        ),
    )
    parser.add_argument(
        "--genesis",
        action="store_true",
        help=(
            "Run the LLM-driven world + persona setup loop before playing. "
            "The LLM answers one-word questions that compose the world and character. "
            "Overrides --scenario, --profile, and --profile-file."
        ),
    )

    profile_group = parser.add_mutually_exclusive_group()
    profile_group.add_argument(
        "--profile",
        choices=sorted(PROFILES.keys()),
        default=None,
        help="Use a named preset profile (lore_seeker, oath_bound, shadow_walker, relic_hunter).",
    )
    profile_group.add_argument(
        "--profile-file",
        type=Path,
        default=None,
        metavar="PATH",
        help="Load a UserProfile from a JSON file (mutually exclusive with --profile).",
    )
    profile_group.add_argument(
        "--location-explorer",
        action="store_true",
        default=False,
        help=(
            "Build a dynamic profile after bootstrap that instructs the agent to visit every "
            "world-bible location in sequence. Good for stress-testing location transitions and "
            "storylet activation. Mutually exclusive with --profile and --profile-file."
        ),
    )
    parser.add_argument(
        "--history-window",
        type=int,
        default=12,
        help="Number of past decisions sent to the LLM for context (default 12).",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="Print all preset profile names and descriptions, then exit.",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help=(
            "Interactive mode: prompt the human at stdin for each decision instead of using the LLM agent. "
            "Ignores --profile and agent model settings."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.list_profiles:
        for key, p in sorted(PROFILES.items()):
            print(f"{key}:")
            print(f"  name:  {p.name}")
            print(f"  goal:  {p.primary_goal}")
            print(f"  avoid: {p.avoid}")
            print()
        return 0

    if int(args.turns) < 2:
        print("Error: --turns must be >= 2", file=sys.stderr)
        return 2
    if int(args.storylet_count) < 5:
        print("Error: --storylet-count must be >= 5", file=sys.stderr)
        return 2

    active_profile: Optional[UserProfile] = None
    genesis_mode = bool(args.genesis)
    mom_mode = bool(args.mom_mode)

    if mom_mode:
        world = WorldConfig(**_MOM_WORLD)
        active_profile = _MOM_PROFILE
    elif not genesis_mode:
        if args.profile_file is not None:
            try:
                active_profile = _load_profile_from_file(Path(args.profile_file))
            except Exception as exc:
                print(f"Error loading profile file: {exc}", file=sys.stderr)
                return 2
        elif args.profile is not None:
            active_profile = PROFILES[args.profile]
        world = _build_world_config(args)
    else:
        # Genesis world + profile are built inside _execute after the LLM client is ready
        world = None  # type: ignore[assignment]
    run_slug = _timestamp_slug()
    scenario_slug = "genesis" if genesis_mode else _safe_slug(world.scenario_id)
    session_id = str(args.session_id).strip() or f"llm-agent-{scenario_slug}-{run_slug}"
    run_dir = (ROOT / args.out_dir).resolve() / run_slug
    turns_dir = run_dir / "turns"
    decisions_dir = run_dir / "decisions"
    run_dir.mkdir(parents=True, exist_ok=True)
    turns_dir.mkdir(parents=True, exist_ok=True)
    decisions_dir.mkdir(parents=True, exist_ok=True)

    env_overrides: Dict[str, str] = {}
    if args.llm_model:
        env_overrides["LLM_MODEL"] = str(args.llm_model)
    if args.llm_narrator_model:
        env_overrides["LLM_NARRATOR_MODEL"] = str(args.llm_narrator_model)
    if args.llm_referee_model:
        env_overrides["LLM_REFEREE_MODEL"] = str(args.llm_referee_model)
    if args.motif_ledger_max_items is not None:
        env_overrides["WW_MOTIF_LEDGER_MAX_ITEMS"] = str(int(args.motif_ledger_max_items))
    if args.jit_frontier_hook_count is not None:
        env_overrides["WW_JIT_FRONTIER_HOOK_COUNT"] = str(int(args.jit_frontier_hook_count))

    agent_model = str(args.agent_model).strip() or str(get_narrator_model())

    def emit(msg: str) -> None:
        if not args.quiet:
            print(msg)

    emit(f"[llm-playtest] run dir: {run_dir}")
    emit(f"[llm-playtest] mode: {'genesis (LLM-driven world+persona setup)' if genesis_mode else 'preset'}")
    if not genesis_mode:
        emit(f"[llm-playtest] scenario: {world.scenario_id} ({world.scenario_title})")
    emit(f"[llm-playtest] turns: {args.turns}")
    emit(f"[llm-playtest] agent model: {agent_model}")
    if not genesis_mode:
        if args.location_explorer:
            emit("[llm-playtest] profile: (location-explorer — built after bootstrap)")
        else:
            emit(f"[llm-playtest] profile: {active_profile.name if active_profile else '(generic)'}")
    emit(f"[llm-playtest] history window: {args.history_window}")
    emit(f"[llm-playtest] backend mode: {'reuse' if args.reuse_backend else 'spawn-managed'}")

    def _execute(base_url: str, backend_mode: str, backend_startup_ms: float) -> int:
        nonlocal world, active_profile
        decisions: List[Decision] = []
        turns: List[Dict[str, Any]] = []

        manual_mode = bool(args.manual)
        client = get_llm_client()
        if client is None and not manual_mode:
            print("Error: No LLM client available. Check API key env vars.", file=sys.stderr)
            return 2

        if genesis_mode:
            world = _genesis_world_setup(client, agent_model, float(args.agent_temperature), emit)
            active_profile = _genesis_profile_setup(client, agent_model, float(args.agent_temperature), world, emit)
            emit(f"[genesis] World: {world.scenario_title} | Role: {world.role}")
            emit(f"[genesis] Persona: {active_profile.name}")
            emit(f"[genesis] Goal: {active_profile.primary_goal}")

        _hard_reset(base_url, timeout=float(args.request_timeout_seconds))
        bootstrap_result = _bootstrap(
            base_url,
            session_id=session_id,
            world=world,
            storylet_count=int(args.storylet_count),
            timeout=float(args.request_timeout_seconds),
        )
        emit(f"[llm-playtest] bootstrap: storylets_created={bootstrap_result.get('storylets_created', 0)}")

        if args.location_explorer:
            bible = bootstrap_result.get("vars", {}).get("_world_bible", {})
            loc_names = [
                loc["name"]
                for loc in bible.get("locations", [])
                if isinstance(loc, dict) and loc.get("name")
            ]
            if loc_names:
                loc_sequence = " → ".join(loc_names)
                active_profile = UserProfile(
                    name="The Location Explorer",
                    play_style=(
                        "Systematic and purposeful. Always scanning for a way to move to the next location. "
                        "Spends at most 2 turns in any one place before pressing on."
                    ),
                    primary_goal=(
                        f"Visit every location in this exact sequence: {loc_sequence}. "
                        "Move to the next unvisited location as soon as possible. "
                        "Once all locations are visited, cycle back to the start."
                    ),
                    avoid="Staying in the same location more than 2 consecutive turns.",
                    decision_heuristic=(
                        "Always pick the choice whose 'set' block changes 'location' to the next "
                        f"unvisited entry in: {loc_sequence}. If no such choice exists, pick the "
                        "choice most likely to trigger a scene change or introduce a new NPC."
                    ),
                    freeform_voice=(
                        "Direct and purposeful. Short sentences. "
                        "E.g. 'I head toward the workshop.' or 'I leave and push through to the market.'"
                    ),
                )
                emit(f"[location-explorer] Locations to visit: {loc_sequence}")
                emit(f"[location-explorer] Active profile: {active_profile.name}")
            else:
                emit("[location-explorer] WARNING: No locations found in world-bible; falling back to no profile.")

        turn1 = _next(base_url, session_id, {}, timeout=float(args.request_timeout_seconds))
        turns.append(turn1)
        (turns_dir / "turn_1.json").write_text(json.dumps(turn1, indent=2, sort_keys=True), encoding="utf-8")

        for turn_no in range(2, int(args.turns) + 1):
            previous = turns[-1]
            narrative = str(previous.get("narrative", previous.get("text", "")))
            choices = _normalize_choices(previous.get("choices", []))
            vars_payload = previous.get("vars", {})
            if not isinstance(vars_payload, dict):
                vars_payload = {}

            if manual_mode:
                decision = _manual_decide(
                    turn=turn_no,
                    narrative=narrative,
                    choices=choices,
                )
            else:
                decision = _llm_decide(
                    model=agent_model,
                    temperature=float(args.agent_temperature),
                    max_tokens=int(args.agent_max_tokens),
                    turn=turn_no,
                    narrative=narrative,
                    choices=choices,
                    vars_payload=vars_payload,
                    history=decisions,
                    profile=active_profile,
                    history_window=int(args.history_window),
                )

            payload: Dict[str, Any]
            if decision.mode == "choice":
                matched = _match_choice(choices, decision.choice_label)
                if matched is None and choices:
                    matched = choices[0]
                    decision.fallback_used = True
                    decision.choice_label = str(matched.get("label", "")).strip()
                if matched is not None:
                    payload = _next(
                        base_url,
                        session_id,
                        matched.get("set", {}),
                        timeout=float(args.request_timeout_seconds),
                    )
                else:
                    decision.mode = "freeform"
                    decision.action_text = decision.action_text or "I investigate one concrete lead that changes immediate risk."
                    decision.fallback_used = True
                    payload = _action(
                        base_url,
                        session_id,
                        decision.action_text,
                        timeout=float(args.request_timeout_seconds),
                    )
            else:
                try:
                    payload = _action(
                        base_url,
                        session_id,
                        decision.action_text,
                        timeout=float(args.request_timeout_seconds),
                    )
                except Exception:
                    if choices:
                        fallback_choice = choices[0]
                        decision.mode = "choice"
                        decision.choice_label = str(fallback_choice.get("label", "")).strip()
                        decision.action_text = ""
                        decision.fallback_used = True
                        payload = _next(
                            base_url,
                            session_id,
                            fallback_choice.get("set", {}),
                            timeout=float(args.request_timeout_seconds),
                        )
                    else:
                        raise

            decisions.append(decision)
            turns.append(payload)
            (turns_dir / f"turn_{turn_no}.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            (decisions_dir / f"decision_{turn_no}.json").write_text(json.dumps(asdict(decision), indent=2, sort_keys=True), encoding="utf-8")

            emit(
                f"[llm-playtest] turn {turn_no}/{args.turns}: mode={decision.mode}, "
                f"choice={decision.choice_label or '-'}, action={decision.action_text[:80] if decision.action_text else '-'}"
            )

            if args.turn_delay_seconds > 0:
                time.sleep(args.turn_delay_seconds)

        transcript = _render_transcript(
            session_id=session_id,
            world=world,
            turns=turns,
            decisions=decisions,
            profile=active_profile,
        )
        transcript_path = run_dir / "transcript.md"
        transcript_path.write_text(transcript, encoding="utf-8")

        manifest = {
            "timestamp_utc": _utc_now(),
            "session_id": session_id,
            "backend_mode": backend_mode,
            "backend_startup_ms": float(backend_startup_ms),
            "base_url": base_url,
            "seed": int(args.seed),
            "turns_requested": int(args.turns),
            "turns_completed": len(turns),
            "scenario": asdict(world),
            "storylet_count": int(args.storylet_count),
            "agent_model": agent_model,
            "agent_temperature": float(args.agent_temperature),
            "agent_max_tokens": int(args.agent_max_tokens),
            "genesis_mode": genesis_mode,
            "history_window": int(args.history_window),
            "profile": asdict(active_profile) if active_profile is not None else None,
            "env_overrides": env_overrides,
            "bootstrap_result": bootstrap_result,
            "artifacts": {
                "turns_dir": str(turns_dir),
                "decisions_dir": str(decisions_dir),
                "transcript": str(transcript_path),
            },
        }
        manifest_path = run_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

        emit(f"[llm-playtest] transcript: {transcript_path}")
        emit(f"[llm-playtest] manifest: {manifest_path}")
        return 0

    if args.reuse_backend:
        if env_overrides:
            emit("[llm-playtest] warning: env overrides do not apply in reuse-backend mode")
        return _execute(str(args.base_url).rstrip("/"), backend_mode="reuse", backend_startup_ms=0.0)

    log_path = run_dir / "backend.log"
    with managed_backend(
        port=int(args.spawn_port),
        env_overrides=env_overrides,
        log_path=log_path,
        startup_timeout=float(args.startup_timeout),
    ) as backend_context:
        spawned_base_url, startup_ms = backend_context
        return _execute(spawned_base_url, backend_mode="spawn", backend_startup_ms=float(startup_ms))


if __name__ == "__main__":
    raise SystemExit(main())
