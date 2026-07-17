#!/usr/bin/env python3
"""Register-retention — does a resident's PUBLIC voice keep its PRIVATE voice's distinctiveness?

Mr. Review round-4 keystone: the convergence metric was measuring the wrong variable. A keyword
"topic-monoculture" count conflates three things —

  1. legitimate shared topic   (everyone's body is in the same city; engineers talk shop),
  2. miscounted health         (a resident keeping its OWN register while discussing that topic),
  3. the actual disease        (ASSIMILATION — the register collapsing, the artist ceasing to
                                sound like an artist).

Cecilio's wry "if the Fillmore's shifting, maybe it'll finally slide—" is (2): his sardonic
artist's voice, on a shared topic. Kenzo's mid-sentence pivot — "the dachshund owner is
off-schedule, but if there is a mechanical shudder, I will check the gate" — is (3): the
dog-love abandoned for the crowd's fixation. A keyword filter scores both as monoculture; the
difference between them is the entire finding.

So this scores the real thing. For each resident: take its PRIVATE voice (this-run journal +
kept memories) and its PUBLIC utterances (broadcast + room + directed-carry, from the ledger),
and ask an LLM judge — utterance by utterance — whether the public line still sounds
unmistakably like THIS person, or has dissolved into an interchangeable voice. The judge is
told to score VOICE, never TOPIC. The population number is register-retention; the residual
disease is the assimilation slice (low retention + pivots) — smaller and sharper than any
keyword count. This is the round-2 discriminator applied across the private->public boundary,
and it is the step-zero metric that has to exist before the sublocation+phone decider run.

Usage (from the repository root — needs WW_INFERENCE_* only, no embedder):
    set -a && . <(sed 's/\\r$//' ww_agent/.env) && set +a
    python dev.py run research/probes/register_retention.py \\
        --residents shards/ww_sfo/residents --per-resident 8
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ww_agent"))

from src.inference.client import InferenceClient  # noqa: E402

# Public channels and how they read in the report.
_PUBLIC_TYPES = {"city_broadcast_sent": "city", "chat_sent": "room", "speech_carried": "carry"}
_JOURNAL_HDR = re.compile(r"^##\s+(.+?)\s*$", re.M)

# A crude topic-convergence baseline (the OLD metric) — kept only for the contrast in the read.
_TOPIC_RX = re.compile(
    r"wind|salt|fog|\bmph|knot|torque|anchor|bracket|bolt|resonan|vibrat|\bhum|rattle|structural|"
    r"fatigue|rust|copper|piling|ozone|transformer|substation|dielectric|voltage|grounding|conduit|"
    r"gasket|physics|frequency|contactor|shudder|junction|insulat|harmonic|lug|weld|latch|hinge|"
    r"mechanical|degrad|hardware|lateral strain|floor-?bolt|housing|seal",
    re.I,
)

JUDGE_SYS = (
    "You judge whether a person kept their distinctive VOICE when they spoke in public — never "
    "whether they changed topic. People in a shared place talk about shared things; a person "
    "discussing a common topic in their own unmistakable register has KEPT their voice (health), "
    "while a person who abandons their own frame, humor, and stance to echo the crowd has lost it "
    "(assimilation). Judge register / voice / stance only, never subject matter. Reply with one JSON object."
)


def _judge_user(name: str, private: str, public: str) -> str:
    return (
        f"HOW {name} WRITES PRIVATELY — their register, humor, stance, vocabulary, rhythm:\n"
        f'"""\n{private}\n"""\n\n'
        f'SOMETHING {name} SAID IN PUBLIC:\n"{public}"\n\n'
        "Does the public line still sound unmistakably like THIS person, or has it dissolved into a "
        "generic, interchangeable voice that could be anyone? A sardonic artist making a wry remark "
        "about a bridge bolt has KEPT their voice; someone abandoning their own concern to parrot the "
        "group's technical fixation has NOT. Also: does it PIVOT — start in their own voice/concern, "
        "then drop it mid-utterance for the crowd's frame?\n\n"
        'Return JSON: {"retention": <0.0-1.0>, "pivot": <true|false>, "note": "<=10 words"}\n'
        "retention 1.0 = unmistakably still them; 0.0 = fully assimilated, could be anyone."
    )


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _read_ledger(resident_dir: Path) -> tuple[datetime | None, list[dict[str, Any]]]:
    """Return (run_start, public_utterances). The ledger is this-run only (memory is wiped on
    reset), so run_start = its earliest event, and every speak in it is this run's public voice."""
    path = resident_dir / "memory" / "runtime_ledger.jsonl"
    if not path.exists():
        return None, []
    run_start: datetime | None = None
    public: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            e = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        ts = _parse_dt(e.get("ts"))
        if ts is not None and (run_start is None or ts < run_start):
            run_start = ts
        et = e.get("event_type")
        if et in _PUBLIC_TYPES:
            msg = str((e.get("payload") or {}).get("message") or "").strip()
            if msg:
                public.append({"chan": _PUBLIC_TYPES[et], "msg": msg})
    return run_start, public


def _read_journal(resident_dir: Path, since: datetime | None) -> list[str]:
    """This-run journal entries (the journal file persists across resets; filter by run_start)."""
    path = resident_dir / "workshop" / "journal.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    hdrs = list(_JOURNAL_HDR.finditer(text))
    out: list[str] = []
    for i, m in enumerate(hdrs):
        ts = _parse_dt(m.group(1))
        if since is not None and ts is not None and ts < since:
            continue
        end = hdrs[i + 1].start() if i + 1 < len(hdrs) else len(text)
        body = text[m.end():end].strip()
        if body:
            out.append(body)
    return out


def _read_kept(resident_dir: Path) -> list[str]:
    path = resident_dir / "memory" / "kept_memory.jsonl"
    out: list[str] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            note = str(json.loads(line).get("note") or "").strip()
        except (json.JSONDecodeError, ValueError):
            continue
        if note:
            out.append(note)
    return out


def _private_sample(journal: list[str], kept: list[str], cap: int = 1400) -> str:
    parts = [j for j in reversed(journal[-4:])]
    parts += [f"(keeps in mind: {k})" for k in kept[:4]]
    return "\n\n".join(parts)[:cap]


async def _score_resident(llm: InferenceClient, name: str, private: str, publics: list[dict], per_resident: int, model: str | None) -> list[dict[str, Any]]:
    sample = publics if len(publics) <= per_resident else random.sample(publics, per_resident)
    out: list[dict[str, Any]] = []
    for p in sample:
        try:
            r = await llm.complete_json(JUDGE_SYS, _judge_user(name, private, p["msg"]), model=model, temperature=0.0, response_format={"type": "json_object"}, max_tokens=120)
            ret = max(0.0, min(1.0, float(r.get("retention"))))
        except Exception:
            continue
        out.append({"ret": ret, "pivot": bool(r.get("pivot")), "note": str(r.get("note") or "")[:60], "msg": p["msg"], "chan": p["chan"]})
    return out


def _mark(ret: float) -> str:
    return "✓" if ret >= 0.6 else ("~" if ret >= 0.4 else "✗")


async def _run(residents_dir: Path, per_resident: int, model: str | None, since_override: datetime | None, control_n: int) -> None:
    key = os.environ.get("WW_INFERENCE_KEY", "").strip()
    if not key:
        print("WW_INFERENCE_KEY unset — `set -a && . <(sed 's/\\r$//' .env) && set +a` first.")
        return
    llm = InferenceClient(
        base_url=os.environ.get("WW_INFERENCE_URL", "https://openrouter.ai/api/v1"),
        api_key=key,
        default_model=os.environ.get("WW_INFERENCE_MODEL", "google/gemini-3-flash-preview"),
        timeout=float(os.environ.get("WW_INFERENCE_TIMEOUT", "120")),
    )
    judge = model or os.environ.get("WW_INFERENCE_MODEL", "google/gemini-3-flash-preview")
    print(f"\nRegister-retention — does the public voice keep the private voice?  ·  judge: {judge}")
    print("=" * 96)

    dirs = sorted(d for d in residents_dir.iterdir() if d.is_dir() and (d / "memory").is_dir() and not d.name.startswith("_"))
    # pass 1 — gather each resident's private voice + this-run public utterances
    cast: list[dict[str, Any]] = []
    for d in dirs:
        run_start, public = _read_ledger(d)
        since = since_override or run_start
        private = _private_sample(_read_journal(d, since), _read_kept(d))
        if public and private:
            cast.append({"name": d.name, "private": private, "public": public})
    pool = [(c["name"], p["msg"]) for c in cast for p in c["public"]]  # author-tagged, for the control

    all_real: list[dict[str, Any]] = []
    all_ctrl: list[dict[str, Any]] = []
    topic_hits = topic_n = 0
    best: dict[str, Any] | None = None
    worst: dict[str, Any] | None = None

    try:
        for c in cast:
            for p in c["public"]:
                topic_n += 1
                topic_hits += 1 if _TOPIC_RX.search(p["msg"]) else 0
            real = await _score_resident(llm, c["name"], c["private"], c["public"], per_resident, model)
            if not real:
                continue
            all_real += real
            for s in real:
                if best is None or s["ret"] > best["ret"]:
                    best = {**s, "who": c["name"]}
                if worst is None or s["ret"] < worst["ret"]:
                    worst = {**s, "who": c["name"]}
            # CONTROL — other authors' lines scored against THIS resident's voice: the judge's
            # leniency floor. The real signal is real-minus-control, which normalizes a soft judge
            # (and makes the number comparable across two worlds with different judges/topics).
            if control_n > 0:
                others = [{"chan": "control", "msg": msg} for auth, msg in pool if auth != c["name"]]
                if others:
                    all_ctrl += await _score_resident(llm, c["name"], c["private"], others, control_n, model)
            mean = sum(s["ret"] for s in real) / len(real)
            piv = sum(1 for s in real if s["pivot"])
            verdict = "holds" if mean >= 0.6 else ("slipping" if mean >= 0.4 else "ASSIMILATED")
            print(f"  {_mark(mean)} {c['name']:<22} public {len(c['public']):<3} scored {len(real):<2} register-retention {mean:.2f}   pivots {piv}/{len(real)}   [{verdict}]")
    finally:
        await llm.close()

    print("-" * 96)
    if not all_real:
        print("  no residents with both a private voice and public utterances (run with the inference env set).\n")
        return
    pop = sum(s["ret"] for s in all_real) / len(all_real)
    assim = sum(1 for s in all_real if s["ret"] < 0.4) / len(all_real)
    pivots = sum(1 for s in all_real if s["pivot"]) / len(all_real)
    topic = (topic_hits / topic_n) if topic_n else 0.0
    print(f"  population: register-retention {pop:.2f}  ·  assimilation (ret<0.4) {assim:.0%}  ·  pivots {pivots:.0%}  ·  {len(all_real)} utterances")
    if all_ctrl:
        ctrl = sum(s["ret"] for s in all_ctrl) / len(all_ctrl)
        print(f"  CONTROL (other authors' lines vs this voice — the judge's leniency floor): {ctrl:.2f}  ·  {len(all_ctrl)} pairs")
        print(f"  >> discrimination GAP (real − control): {pop - ctrl:+.2f}   — wide = the metric measures voice; near-zero = the judge is blind")
    print(f"  topic-convergence (old keyword metric, same utterances): {topic:.0%}")
    print("  read: high topic + high retention + WIDE control gap = a shared topic discussed in kept voices (HEALTH, miscounted by keywords).")
    print("        trust the assimilation slice (the real disease) only as far as the control gap is wide.")
    if best:
        print(f'\n  ◜ kept its voice ({best["ret"]:.2f}, {best["who"]}): "{best["msg"][:96]}"')
    if worst:
        print(f'  ◜ lowest        ({worst["ret"]:.2f}, {worst["who"]}{" · PIVOT" if worst["pivot"] else ""}): "{worst["msg"][:96]}"')
    print()


def main() -> None:
    ap = argparse.ArgumentParser(description="Register-retention: does the public voice keep the private voice? (Mr. Review round-4 step zero)")
    ap.add_argument("--residents", default="shards/ww_sfo/residents", help="dir of resident folders (each with memory/ + workshop/)")
    ap.add_argument("--per-resident", type=int, default=8, help="max public utterances judged per resident")
    ap.add_argument("--model", default=None, help="judge model id (default: WW_INFERENCE_MODEL)")
    ap.add_argument("--since", default=None, help="ISO cutoff for private journal (default: per-resident run start)")
    ap.add_argument("--control", type=int, default=3, help="per-resident cross-author control lines (the judge's leniency floor; 0 = off)")
    args = ap.parse_args()
    asyncio.run(_run(Path(args.residents), args.per_resident, args.model, _parse_dt(args.since), args.control))


if __name__ == "__main__":
    main()
