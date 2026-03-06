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
        for item in history[-6:]
    ]
    choice_labels = [str(item.get("label", "")).strip() for item in choices]

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
    parsed = extract_json_object(raw)

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
) -> str:
    lines = [
        "# LLM Agent Playtest Transcript",
        "",
        f"- Session ID: `{session_id}`",
        f"- Scenario: `{world.scenario_id}` ({world.scenario_title})",
        f"- Theme: `{world.theme}`",
        f"- Role: `{world.role}`",
        f"- Generated UTC: `{_utc_now()}`",
        "",
    ]

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
    parser.add_argument("--agent-model", default="")
    parser.add_argument("--agent-temperature", type=float, default=0.35)
    parser.add_argument("--agent-max-tokens", type=int, default=300)

    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if int(args.turns) < 2:
        print("Error: --turns must be >= 2", file=sys.stderr)
        return 2
    if int(args.storylet_count) < 5:
        print("Error: --storylet-count must be >= 5", file=sys.stderr)
        return 2

    world = _build_world_config(args)
    run_slug = _timestamp_slug()
    session_id = str(args.session_id).strip() or f"llm-agent-{_safe_slug(world.scenario_id)}-{run_slug}"
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

    agent_model = str(args.agent_model).strip() or str(get_narrator_model())

    def emit(msg: str) -> None:
        if not args.quiet:
            print(msg)

    emit(f"[llm-playtest] run dir: {run_dir}")
    emit(f"[llm-playtest] scenario: {world.scenario_id} ({world.scenario_title})")
    emit(f"[llm-playtest] turns: {args.turns}")
    emit(f"[llm-playtest] agent model: {agent_model}")
    emit(f"[llm-playtest] backend mode: {'reuse' if args.reuse_backend else 'spawn-managed'}")

    def _execute(base_url: str, backend_mode: str, backend_startup_ms: float) -> int:
        decisions: List[Decision] = []
        turns: List[Dict[str, Any]] = []

        _hard_reset(base_url, timeout=float(args.request_timeout_seconds))
        bootstrap_result = _bootstrap(
            base_url,
            session_id=session_id,
            world=world,
            storylet_count=int(args.storylet_count),
            timeout=float(args.request_timeout_seconds),
        )
        emit(f"[llm-playtest] bootstrap: storylets_created={bootstrap_result.get('storylets_created', 0)}")

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

            decision = _llm_decide(
                model=agent_model,
                temperature=float(args.agent_temperature),
                max_tokens=int(args.agent_max_tokens),
                turn=turn_no,
                narrative=narrative,
                choices=choices,
                vars_payload=vars_payload,
                history=decisions,
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

        transcript = _render_transcript(
            session_id=session_id,
            world=world,
            turns=turns,
            decisions=decisions,
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
