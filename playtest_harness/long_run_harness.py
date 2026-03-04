#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import requests

DEFAULT_BASE_URL = os.getenv("WW_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/")
DEFAULT_OUTPUT_DIR = Path("playtests") / "long_runs"
DEFAULT_TURNS = 100
DEFAULT_SEED = 20260304
DEFAULT_STORYLET_COUNT = 15

SCENARIOS: Dict[str, Dict[str, Any]] = {
    "cyberpunk": {
        "title": "Neon Pursuit",
        "theme": "cyberpunk noir",
        "roles": [
            "rogue AI hunter",
            "memory broker",
            "street medic with a black-market license",
            "drone courier running encrypted drops",
        ],
        "description": "A rain-soaked megacity of enforcers, fixers, and unstable AI traces.",
        "key_elements": [
            "neon reflections in rain",
            "memory core extraction",
            "terminal intrusion traces",
            "patrol drones overhead",
            "industrial filtration plants",
        ],
        "tone": "gritty, suspenseful, desperate",
    },
    "space_opera": {
        "title": "Shatter-Belt Run",
        "theme": "space opera",
        "roles": [
            "smuggler captain",
            "salvage pilot",
            "nav-officer turned deserter",
            "station ghost mechanic",
        ],
        "description": "A contested star frontier with patrol sweeps and fragile alliances.",
        "key_elements": [
            "damaged reactor housing",
            "debris shadow approaches",
            "encrypted cargo manifests",
            "patrol scanner sweeps",
            "cold-dark drift maneuvers",
        ],
        "tone": "high-pressure and cinematic",
    },
    "gothic": {
        "title": "Clockwork Decay",
        "theme": "gothic clockwork alchemy",
        "roles": [
            "outcast alchemist",
            "cathedral archivist",
            "gearwright saboteur",
            "state enforcer with a failing prosthetic",
        ],
        "description": "A gear-driven city where alchemical risk and faction politics dominate.",
        "key_elements": [
            "whirring gears",
            "glowing vials",
            "soot-stained gargoyles",
            "clockwork prosthetics",
            "the Great Gear",
        ],
        "tone": "opulent and decaying",
    },
    "dark_fantasy": {
        "title": "Ashen Oathlands",
        "theme": "dark fantasy",
        "roles": [
            "cursed knight",
            "forbidden scripture seeker",
            "gravebound ranger",
            "soul-forger apprentice",
        ],
        "description": "A land of broken vows, haunted ruins, and costly magic.",
        "key_elements": [
            "blackened shrines",
            "ash storms over ruined keeps",
            "blood sigils in stone",
            "oathbound relics",
            "whispering catacombs",
        ],
        "tone": "grim, mythic, relentless",
    },
    "solarpunk": {
        "title": "Canopy Commons",
        "theme": "solarpunk frontier",
        "roles": [
            "grid architect",
            "water-rights negotiator",
            "seed librarian",
            "repair diver in floating districts",
        ],
        "description": "An eco-city balancing innovation, scarcity, and diplomacy.",
        "key_elements": [
            "solar canopies",
            "community fabrication labs",
            "living seawalls",
            "autonomous pollinator swarms",
            "water quota exchanges",
        ],
        "tone": "hopeful, practical, politically tense",
    },
    "post_apocalypse": {
        "title": "Rustline Expanse",
        "theme": "post-apocalyptic survival drama",
        "roles": [
            "convoy scout",
            "salvage quartermaster",
            "former city planner",
            "medic protecting a settlement",
        ],
        "description": "Settlements survive between dead highways and dust fronts.",
        "key_elements": [
            "collapsed overpasses",
            "water caravans",
            "radio towers",
            "ration ledgers",
            "salvage disputes",
        ],
        "tone": "tense, resourceful, human",
    },
    "mystery": {
        "title": "Tideglass Inquiry",
        "theme": "mythic mystery thriller",
        "roles": [
            "forensic folklorist",
            "harbor detective",
            "court translator",
            "retired smuggler turned informant",
        ],
        "description": "A coastal city of cover-ups and conflicting truths.",
        "key_elements": [
            "salt archives",
            "sealed witness logs",
            "ritual masks",
            "fogbound causeways",
            "interrupted radio broadcasts",
        ],
        "tone": "investigative, eerie, deliberate",
    },
    "everyday": {
        "title": "Neighborhood Knots",
        "theme": "everyday city life",
        "roles": [
            "part-time barista balancing rent and friendships",
            "night-shift nurse commuting across districts",
            "public school counselor",
            "rideshare driver supporting extended family",
        ],
        "description": "Small decisions around bills, schedules, trust, and community.",
        "key_elements": [
            "crowded bus rides",
            "group chat spillover",
            "apartment chores and bills",
            "coffee shop regulars",
            "community center classes",
        ],
        "tone": "grounded, warm, quietly tense",
    },
}

DEFAULT_DIVERSITY_ACTIONS: List[str] = [
    "I stop and ask the nearest witness what changed in this district overnight.",
    "I leave a coded message to draw an ally here and then hide nearby.",
    "I inspect the environment for one concrete hazard no one has mentioned yet.",
    "I deliberately take the least obvious route to test whether I am being followed.",
    "I offer help to an exhausted stranger and ask for one useful detail in return.",
    "I provoke a minor confrontation to flush hidden actors into the open.",
    "I pause to secure supplies and reduce immediate risk before moving again.",
    "I search for a rumor network and trade information instead of force.",
    "I change priorities and pursue a side objective tied to local tensions.",
    "I attempt to repair a damaged system so future choices open up.",
    "I test a risky shortcut that could save time but raise danger.",
    "I gather hard evidence before committing to any faction claim.",
    "I revisit a previous location to check how the world has changed.",
    "I negotiate for safe passage and offer a concrete concession.",
    "I set a decoy trail so adversaries react to false information.",
    "I escalate publicly to force a decision from the strongest opponent.",
    "I de-escalate, hide my intent, and wait for a better opening.",
    "I attempt a stealth extraction of a key asset without direct conflict.",
    "I sabotage a chokepoint to limit enemy options in future turns.",
    "I choose empathy over efficiency and prioritize protecting bystanders.",
]


@dataclass
class WorldConfig:
    scenario_id: str
    scenario_title: str
    theme: str
    role: str
    description: str
    key_elements: List[str]
    tone: str


@dataclass
class RunConfig:
    base_url: str
    session_id: str
    turns: int
    seed: int
    storylet_count: int
    switch_model: bool
    model_id: str
    hard_reset: bool
    skip_bootstrap: bool
    sleep_seconds: float
    diversity_every: int
    diversity_chance: float
    output_dir: Path
    world: WorldConfig | None


@dataclass
class TurnRecord:
    turn: int
    phase: str
    action_source: str
    action_sent: str
    narrative: str
    ack_line: str
    plausible: bool
    choices: List[Dict[str, Any]]
    state_changes: Dict[str, Any]
    vars: Dict[str, Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_slug(value: str) -> str:
    out = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in value.strip().lower())
    out = "-".join(filter(None, out.split("-")))
    return out or "session"


def _split_csv(value: str) -> List[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _request_json(method: str, url: str, *, payload: Dict[str, Any] | None = None, timeout: float = 45.0) -> Dict[str, Any]:
    response = requests.request(method, url, json=payload, timeout=timeout)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(f"{method} {url} failed: {response.status_code} {response.text.strip()}") from exc
    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError(f"{method} {url} returned unexpected payload type.")
    return body


def _switch_model(base_url: str, model_id: str) -> Dict[str, Any]:
    return _request_json("PUT", f"{base_url}/model", payload={"model_id": model_id})


def _hard_reset(base_url: str) -> Dict[str, Any]:
    return _request_json("POST", f"{base_url}/dev/hard-reset", payload={})


def _bootstrap_session(base_url: str, session_id: str, world: WorldConfig, storylet_count: int) -> Dict[str, Any]:
    payload = {
        "session_id": session_id,
        "world_theme": world.theme,
        "player_role": world.role,
        "description": world.description,
        "key_elements": world.key_elements,
        "tone": world.tone,
        "storylet_count": int(storylet_count),
        "bootstrap_source": "long-run-harness",
    }
    return _request_json("POST", f"{base_url}/session/bootstrap", payload=payload)


def _get_next(base_url: str, session_id: str) -> Dict[str, Any]:
    return _request_json("POST", f"{base_url}/next", payload={"session_id": session_id, "vars": {}})


def _submit_action(base_url: str, session_id: str, action: str, turn: int) -> Dict[str, Any]:
    return _request_json(
        "POST",
        f"{base_url}/action",
        payload={"session_id": session_id, "action": action, "idempotency_key": f"longrun-{session_id}-{turn}"},
    )


def _normalize_choices(raw_choices: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(raw_choices, list):
        return out
    for item in raw_choices:
        if isinstance(item, dict) and str(item.get("label", "")).strip():
            set_payload = item.get("set") if isinstance(item.get("set"), dict) else {}
            out.append({"label": str(item.get("label")).strip(), "set": set_payload})
    return out


def _load_actions_file(path: Path) -> List[str]:
    out: List[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def _dedupe_preserve_order(items: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for item in items:
        s = item.strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _prompt_text(label: str, default: str) -> str:
    raw = input(f"{label} [{default}]: ").strip()
    return raw or default


def _prompt_yes_no(label: str, default: bool) -> bool:
    marker = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{label} ({marker}): ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Please enter y or n.")


def _prompt_int(label: str, default: int, minimum: int) -> int:
    while True:
        raw = input(f"{label} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("Enter a whole number.")
            continue
        if value < minimum:
            print(f"Enter >= {minimum}.")
            continue
        return value


def _prompt_float(label: str, default: float, minimum: float, maximum: float) -> float:
    while True:
        raw = input(f"{label} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = float(raw)
        except ValueError:
            print("Enter a numeric value.")
            continue
        if value < minimum or value > maximum:
            print(f"Enter between {minimum} and {maximum}.")
            continue
        return value


def _prompt_select(label: str, options: Sequence[Tuple[str, str]], default_value: str) -> str:
    option_values = {v for v, _ in options}
    if default_value not in option_values:
        default_value = options[0][0]
    print(label)
    for idx, (value, text) in enumerate(options, start=1):
        marker = " (default)" if value == default_value else ""
        print(f"  {idx}. {text}{marker}")
    while True:
        raw = input(f"Select 1-{len(options)} or value [{default_value}]: ").strip()
        if not raw:
            return default_value
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1][0]
        if raw in option_values:
            return raw
        print("Invalid selection.")


def _interactive_enabled(args: argparse.Namespace) -> bool:
    if args.non_interactive:
        return False
    if args.interactive:
        return True
    return sys.stdin.isatty() and sys.stdout.isatty()


def _resolve_world_config(args: argparse.Namespace, interactive: bool) -> WorldConfig | None:
    if args.skip_bootstrap:
        return None

    scenario_keys = sorted(SCENARIOS.keys())
    scenario_choice = args.scenario
    if scenario_choice is None:
        if interactive:
            options = [(k, f"{k}: {SCENARIOS[k]['title']}") for k in scenario_keys]
            options.append(("custom", "custom: provide your own setup"))
            scenario_choice = _prompt_select("Choose scenario preset:", options, "cyberpunk")
        else:
            scenario_choice = "cyberpunk"

    if scenario_choice == "custom":
        title = "Custom Scenario"
        theme = "custom narrative world"
        roles = ["adventurer"]
        description = "A world with conflicting factions and unresolved tensions."
        key_elements = ["rumors", "resource pressure", "hidden agenda"]
        tone = "dramatic"
    else:
        scenario = SCENARIOS[scenario_choice]
        title = str(scenario["title"])
        theme = str(scenario["theme"])
        roles = [str(item) for item in scenario.get("roles", []) if str(item).strip()]
        description = str(scenario["description"])
        key_elements = [str(item) for item in scenario.get("key_elements", []) if str(item).strip()]
        tone = str(scenario["tone"])

    role_default = roles[0] if roles else "adventurer"
    role = str(args.role).strip() if args.role else role_default
    if interactive and not args.role:
        role_options = [(r, r) for r in roles]
        role_options.append(("custom", "custom role"))
        selected_role = _prompt_select("Choose character role:", role_options, role_default)
        role = _prompt_text("Custom role", role_default) if selected_role == "custom" else selected_role

    if args.theme:
        theme = str(args.theme).strip()
    if args.description:
        description = str(args.description).strip()
    if args.tone:
        tone = str(args.tone).strip()
    if args.key_elements:
        key_elements = _split_csv(args.key_elements)

    if interactive:
        title = _prompt_text("Scenario title", title).strip()
        theme = _prompt_text("World theme", theme).strip()
        role = _prompt_text("Player role", role).strip()
        tone = _prompt_text("World tone", tone).strip()
        description = _prompt_text("World description", description).strip()
        keys_default = ", ".join(key_elements) if key_elements else "risk, pressure, rumor network"
        keys_input = _prompt_text("Key elements (comma-separated)", keys_default)
        parsed = _split_csv(keys_input)
        if parsed:
            key_elements = parsed

    if not key_elements:
        key_elements = ["risk", "tradeoff", "complication"]

    return WorldConfig(
        scenario_id=str(scenario_choice or "custom"),
        scenario_title=title,
        theme=theme or "narrative world",
        role=role or role_default,
        description=description or "A world with unresolved conflict.",
        key_elements=key_elements,
        tone=tone or "dramatic",
    )


def _resolve_run_config(args: argparse.Namespace) -> RunConfig:
    interactive = _interactive_enabled(args)
    if interactive and not (sys.stdin.isatty() and sys.stdout.isatty()):
        interactive = False

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    session_default = f"longrun-{timestamp.lower()}"

    base_url = str(args.base_url or DEFAULT_BASE_URL).rstrip("/")
    session_id = str(args.session_id or "").strip() or session_default
    turns = int(args.turns if args.turns is not None else DEFAULT_TURNS)
    seed = int(args.seed if args.seed is not None else DEFAULT_SEED)
    storylet_count = int(args.storylet_count if args.storylet_count is not None else DEFAULT_STORYLET_COUNT)
    sleep_seconds = float(args.sleep_seconds if args.sleep_seconds is not None else 0.0)
    diversity_every = int(args.diversity_every if args.diversity_every is not None else 8)
    diversity_chance = float(args.diversity_chance if args.diversity_chance is not None else 0.15)
    switch_model = bool(args.switch_model or str(args.model_id or "").strip())
    model_id = str(args.model_id or "").strip()
    hard_reset = bool(args.hard_reset)
    skip_bootstrap = bool(args.skip_bootstrap)

    if interactive:
        print("")
        print("Long-Run Harness Setup")
        print("----------------------")
        base_url = _prompt_text("Base URL", base_url).rstrip("/")
        session_id = _prompt_text("Session ID", session_id)
        turns = _prompt_int("Turns", turns, minimum=1)
        seed = _prompt_int("Seed", seed, minimum=0)
        storylet_count = _prompt_int("Storylet count", storylet_count, minimum=5)
        sleep_seconds = _prompt_float("Sleep between turns (seconds)", sleep_seconds, 0.0, 30.0)
        diversity_every = _prompt_int("Inject diversity every N turns (0 disables cadence)", diversity_every, minimum=0)
        diversity_chance = _prompt_float("Per-turn diversity chance", diversity_chance, 0.0, 1.0)
        if not hard_reset:
            hard_reset = _prompt_yes_no("Run /api/dev/hard-reset first?", False)
        if not skip_bootstrap:
            skip_bootstrap = _prompt_yes_no("Skip bootstrap and continue existing session?", False)
        if not switch_model:
            switch_model = _prompt_yes_no("Switch model before run?", False)
        if switch_model and not model_id:
            model_id = _prompt_text("Model ID", "openai/gpt-4o-mini")

    if turns < 1:
        raise ValueError("--turns must be >= 1")
    if storylet_count < 5:
        raise ValueError("--storylet-count must be >= 5")
    if diversity_every < 0:
        raise ValueError("--diversity-every must be >= 0")
    if not 0.0 <= diversity_chance <= 1.0:
        raise ValueError("--diversity-chance must be in [0, 1]")
    if switch_model and not model_id:
        raise ValueError("model ID is required when switching model")

    world = _resolve_world_config(args, interactive) if not skip_bootstrap else None

    return RunConfig(
        base_url=base_url,
        session_id=session_id,
        turns=turns,
        seed=seed,
        storylet_count=storylet_count,
        switch_model=switch_model,
        model_id=model_id,
        hard_reset=hard_reset,
        skip_bootstrap=skip_bootstrap,
        sleep_seconds=sleep_seconds,
        diversity_every=diversity_every,
        diversity_chance=diversity_chance,
        output_dir=Path(args.output_dir),
        world=world,
    )


def _pick_action(
    rng: random.Random,
    turn: int,
    choices: List[Dict[str, Any]],
    diversity_actions: List[str],
    diversity_every: int,
    diversity_chance: float,
) -> Tuple[str, str]:
    inject = False
    if diversity_actions:
        if diversity_every > 0 and turn % diversity_every == 0:
            inject = True
        elif diversity_chance > 0 and rng.random() < diversity_chance:
            inject = True
    if inject:
        return rng.choice(diversity_actions), "diversity_freeform"
    labels = [str(item.get("label", "")).strip() for item in choices if str(item.get("label", "")).strip()]
    if labels:
        return rng.choice(labels), "choice_button"
    if diversity_actions:
        return rng.choice(diversity_actions), "diversity_fallback"
    return "Continue", "continue_fallback"


def _render_markdown_report(run_payload: Dict[str, Any], diversity_actions: List[str]) -> str:
    turns = run_payload.get("turns", [])
    summary = run_payload.get("summary", {})
    world = run_payload.get("world", {})

    lines: List[str] = [
        "# Long-Run Random Choice Playtest",
        "",
        f"- Session ID: `{run_payload.get('session_id', '')}`",
        f"- Timestamp UTC: `{run_payload.get('timestamp_utc', '')}`",
        f"- Base URL: `{run_payload.get('base_url', '')}`",
        f"- Scenario ID: `{world.get('scenario_id', 'n/a')}`",
        f"- Scenario Title: `{world.get('scenario_title', 'n/a')}`",
        f"- Theme: `{world.get('theme', 'n/a')}`",
        f"- Role: `{world.get('role', 'n/a')}`",
        f"- Tone: `{world.get('tone', 'n/a')}`",
        f"- Turns Requested: `{run_payload.get('turns_requested', 0)}`",
        f"- Turns Completed: `{summary.get('turns_completed', 0)}`",
        f"- Seed: `{run_payload.get('seed', 0)}`",
        f"- Diversity Injections: `{summary.get('diversity_turns', 0)}`",
        f"- Choice Button Presses: `{summary.get('choice_turns', 0)}`",
        f"- Plausible Responses: `{summary.get('plausible_true_count', 0)}`",
        "",
        "## Diversity Freeform Actions",
        "",
    ]
    for action in diversity_actions:
        lines.append(f"- {action}")
    lines.append("")

    for turn in turns:
        turn_no = int(turn.get("turn", 0))
        lines.extend(
            [
                f"## Turn {turn_no}",
                "",
                f"- Phase: `{turn.get('phase', 'unknown')}`",
                f"- Action Source: `{turn.get('action_source', 'n/a')}`",
            ]
        )
        action_sent = str(turn.get("action_sent", "")).strip()
        ack_line = str(turn.get("ack_line", "")).strip()
        if action_sent:
            lines.append(f"- Action: {action_sent}")
        if ack_line:
            lines.append(f"- Ack: {ack_line}")
        lines.extend(
            [
                "",
                "**Narrative**",
                "",
                str(turn.get("narrative", "")).strip(),
                "",
                "**Choices Presented**",
                "",
            ]
        )
        choices = _normalize_choices(turn.get("choices", []))
        if choices:
            for choice in choices:
                lines.append(f"- {choice['label']}")
        else:
            lines.append("- (none)")
        lines.append("")
        lines.append(f"**State Changes:** `{json.dumps(turn.get('state_changes', {}), ensure_ascii=True)}`")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a long autonomous playtest with random choice presses and periodic "
            "diversity freeform actions. Defaults to guided interactive setup."
        )
    )
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--turns", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--scenario", default=None, choices=sorted(SCENARIOS.keys()) + ["custom"])
    parser.add_argument("--role", default=None)
    parser.add_argument("--theme", default=None)
    parser.add_argument("--description", default=None)
    parser.add_argument("--tone", default=None)
    parser.add_argument("--key-elements", default=None, help="Comma-separated list")
    parser.add_argument("--storylet-count", type=int, default=None)
    parser.add_argument("--switch-model", action="store_true")
    parser.add_argument("--model-id", default="")
    parser.add_argument("--hard-reset", action="store_true")
    parser.add_argument("--skip-bootstrap", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=None)
    parser.add_argument("--diversity-every", type=int, default=None)
    parser.add_argument("--diversity-chance", type=float, default=None)
    parser.add_argument("--diversity-actions-file", type=Path, default=None)
    parser.add_argument("--add-diversity-action", action="append", default=[])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--print-diversity-actions", action="store_true")
    parser.add_argument("--interactive", action="store_true", help="Force interactive prompts")
    parser.add_argument("--non-interactive", action="store_true", help="Disable interactive prompts")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.interactive and args.non_interactive:
        print("Error: --interactive and --non-interactive are mutually exclusive.", file=sys.stderr)
        return 2

    diversity_actions = list(DEFAULT_DIVERSITY_ACTIONS)
    if args.diversity_actions_file is not None:
        if not args.diversity_actions_file.exists():
            print(f"Error: diversity actions file not found: {args.diversity_actions_file}", file=sys.stderr)
            return 2
        diversity_actions.extend(_load_actions_file(args.diversity_actions_file))
    diversity_actions.extend([str(item).strip() for item in args.add_diversity_action])
    diversity_actions = _dedupe_preserve_order(diversity_actions)

    if args.print_diversity_actions:
        for action in diversity_actions:
            print(action)
        return 0

    try:
        config = _resolve_run_config(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    rng = random.Random(config.seed)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    print(f"Session: {config.session_id}")
    print(f"Base URL: {config.base_url}")
    print(f"Turns requested: {config.turns}")
    print(f"Seed: {config.seed}")
    print(f"Diversity actions pool: {len(diversity_actions)}")
    if config.world is not None:
        print(f"Scenario: {config.world.scenario_id} ({config.world.scenario_title})")
        print(f"Role: {config.world.role}")
        print(f"Theme: {config.world.theme}")
    if config.skip_bootstrap:
        print("Bootstrap: skipped")

    try:
        if config.switch_model:
            model_result = _switch_model(config.base_url, config.model_id)
            print(f"Model switched to: {model_result.get('current_model', config.model_id)}")
        if config.hard_reset:
            reset_result = _hard_reset(config.base_url)
            print(str(reset_result.get("message", "Hard reset complete.")))
        if not config.skip_bootstrap and config.world is not None:
            bootstrap_result = _bootstrap_session(
                config.base_url,
                config.session_id,
                config.world,
                config.storylet_count,
            )
            print(
                "Bootstrap complete: "
                f"{bootstrap_result.get('storylets_created', 0)} storylets, "
                f"theme={bootstrap_result.get('theme', 'unknown')}"
            )

        turns: List[TurnRecord] = []
        first = _get_next(config.base_url, config.session_id)
        first_choices = _normalize_choices(first.get("choices", []))
        first_vars = first.get("vars", {}) if isinstance(first.get("vars"), dict) else {}
        turns.append(
            TurnRecord(
                turn=1,
                phase="next",
                action_source="initial_scene",
                action_sent="",
                narrative=str(first.get("text", "")),
                ack_line="",
                plausible=True,
                choices=first_choices,
                state_changes={},
                vars=first_vars,
            )
        )
        print(f"Turn 1 loaded. Choices: {len(first_choices)}")

        current_choices = first_choices
        for turn_no in range(2, int(config.turns) + 1):
            action_text, action_source = _pick_action(
                rng,
                turn_no,
                current_choices,
                diversity_actions,
                config.diversity_every,
                config.diversity_chance,
            )
            response = _submit_action(config.base_url, config.session_id, action_text, turn_no)
            next_choices = _normalize_choices(response.get("choices", []))
            next_vars = response.get("vars", {}) if isinstance(response.get("vars"), dict) else {}
            state_changes = response.get("state_changes", {}) if isinstance(response.get("state_changes"), dict) else {}
            turns.append(
                TurnRecord(
                    turn=turn_no,
                    phase="action",
                    action_source=action_source,
                    action_sent=action_text,
                    narrative=str(response.get("narrative", "")),
                    ack_line=str(response.get("ack_line", "")),
                    plausible=bool(response.get("plausible", True)),
                    choices=next_choices,
                    state_changes=state_changes,
                    vars=next_vars,
                )
            )
            current_choices = next_choices
            print(f"Turn {turn_no}/{config.turns}: source={action_source}, choices_returned={len(next_choices)}")
            if config.sleep_seconds > 0:
                time.sleep(max(0.0, float(config.sleep_seconds)))

    except Exception as exc:
        print(f"Run failed: {exc}", file=sys.stderr)
        return 1

    world_payload: Dict[str, Any]
    if config.world is None:
        world_payload = {
            "scenario_id": "existing-session",
            "scenario_title": "Existing Session State",
            "theme": "",
            "role": "",
            "description": "",
            "key_elements": [],
            "tone": "",
        }
    else:
        world_payload = asdict(config.world)

    summary = {
        "turns_completed": len(turns),
        "diversity_turns": sum(1 for t in turns if t.action_source.startswith("diversity")),
        "choice_turns": sum(1 for t in turns if t.action_source == "choice_button"),
        "plausible_true_count": sum(1 for t in turns if t.plausible),
        "final_var_keys": sorted(turns[-1].vars.keys()) if turns else [],
    }

    run_payload: Dict[str, Any] = {
        "timestamp_utc": _utc_now(),
        "base_url": config.base_url,
        "session_id": config.session_id,
        "turns_requested": int(config.turns),
        "seed": int(config.seed),
        "storylet_count": int(config.storylet_count),
        "diversity_every": int(config.diversity_every),
        "diversity_chance": float(config.diversity_chance),
        "diversity_actions_count": len(diversity_actions),
        "switch_model": bool(config.switch_model),
        "model_id": config.model_id,
        "hard_reset": bool(config.hard_reset),
        "skip_bootstrap": bool(config.skip_bootstrap),
        "world": world_payload,
        "summary": summary,
        "turns": [asdict(item) for item in turns],
    }

    out_dir = config.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    run_slug = f"{timestamp}-{_safe_slug(config.session_id)}"
    json_path = out_dir / f"{run_slug}.json"
    md_path = out_dir / f"{run_slug}.md"
    json_path.write_text(json.dumps(run_payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_render_markdown_report(run_payload, diversity_actions), encoding="utf-8")

    print(f"Run complete. Turns: {len(turns)}")
    print(f"JSON report: {json_path}")
    print(f"Markdown transcript: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
