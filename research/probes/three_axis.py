#!/usr/bin/env python3
"""Three-axis convergence instrument (Mr. Review round-5, "step zero").

Every metric we used called SOME failure healthy: commons-volume was blind to Portland's
private convergence; register-retention is blind to shared mood. They miss different things
because convergence-vs-health lives on THREE orthogonal axes, and reading only one blesses
the failures the others would catch:

  VOICE      — does each mind keep its own register in public? (catches SF assimilation)
               [reuses register_retention's LLM judge + shuffle-control]
  ATTENTION  — venue-agnostic per-soul DISPLACEMENT: is the shared thing attended IN ADDITION to
               each soul's own concerns (health), or has it crowded them out (disease)? Read across
               ALL output — commons + rooms + carries + felt-sense + journal — so it catches
               convergence wherever it lives, Portland's private hush included. NOT a minimize-
               target: a shared world SHOULD make minds attend shared things; the disease is only
               the crowding-out.
  CONTACT    — do the minds actually ENGAGE each other? (separates SF's false-we [high] from
               Portland's no-we [zero] — the axis no prior metric had). Mechanical: a directed,
               named, responsive utterance is contact; felt-sense and journal are solipsism.

Health is shared attention that costs NEITHER the self NOR the we: distinct voices (high VOICE),
genuinely connected (high CONTACT), over a thing they really share (some attention) WITHOUT it
displacing who each of them is (low DISPLACEMENT).

Usage (from the repository root, needs WW_INFERENCE_* only):
    set -a && . <(sed 's/\\r$//' ww_agent/.env) && set +a
    python dev.py run research/probes/three_axis.py --residents shards/ww_sfo/residents
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))  # to import register_retention (same dir)
import register_retention as rr  # noqa: E402  (sets up the src path + the voice judge on import)

from src.inference.client import InferenceClient  # noqa: E402

_FELT = "felt_sense_logged"


def _read_felt_and_journal(d: Path, since) -> list[str]:
    """The private/inward attention corpus: felt-sense traces + this-run journal entries."""
    out: list[str] = []
    ledger = d / "memory" / "runtime_ledger.jsonl"
    if ledger.exists():
        for line in ledger.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                e = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if e.get("event_type") == _FELT:
                t = str((e.get("payload") or {}).get("felt_sense") or "").strip()
                if t:
                    out.append(t)
    out += rr._read_journal(d, since)
    return out


def _roster(dirs: list[Path]) -> dict[str, str]:
    """slug -> a name-token regex alternation, for detecting who an utterance addresses."""
    names: dict[str, str] = {}
    for d in dirs:
        toks = [t for t in re.split(r"[_\s]+", d.name) if len(t) >= 3]
        if toks:
            names[d.name] = "|".join(re.escape(t) for t in toks)
    return names


def _contact_score(utterances: list[str], self_slug: str, roster: dict[str, str], inward_n: int) -> tuple[int, int]:
    """(directed, total-output). A directed utterance names some OTHER resident; inward traces
    (felt-sense + journal) are solipsism — counted in the denominator, never as contact."""
    others = "|".join(rx for slug, rx in roster.items() if slug != self_slug)
    directed = 0
    if others:
        pat = re.compile(rf"\b({others})\b", re.I)
        directed = sum(1 for u in utterances if pat.search(u))
    return directed, len(utterances) + inward_n


_THEME_SYS = "You read a city's people and name, in one short phrase, the single thing the population keeps returning to. Reply with only the phrase."
_DISP_SYS = (
    "You judge ATTENTION DISPLACEMENT — whether a shared concern has crowded out a person's OWN concerns, "
    "or merely sits alongside them. A shared world SHOULD make minds attend shared things, so attending the "
    "shared concern is NOT itself the problem; the problem is only when it leaves no room for the person's own. "
    "Reply with one JSON object."
)


def _disp_user(name: str, own: str, attending: str, theme: str) -> str:
    return (
        f"{name}'s OWN concerns (who they are, from their private writing):\n\"\"\"\n{own[:900]}\n\"\"\"\n\n"
        f"What {name} has actually been attending to lately (everything they've put out — said, felt, written):\n"
        f"\"\"\"\n{attending[:1400]}\n\"\"\"\n\n"
        f"The shared concern the whole population keeps returning to is: \"{theme}\".\n\n"
        "Is that shared concern present IN ADDITION to this person's own concerns (additive — they still attend "
        "their own life too), or has it CROWDED OUT their own concerns (displacement — almost all they attend now "
        "is the shared thing)?\n"
        'Return JSON: {"displacement": <0.0-1.0>, "note": "<=10 words"}  '
        "(0.0 = own concerns fully intact alongside the shared; 1.0 = own concerns gone, only the shared remains)."
    )


async def _dominant_theme(llm: InferenceClient, sample: list[str], model: str | None) -> str:
    blob = "\n".join(f"- {s[:160]}" for s in sample[:40])
    try:
        return (await llm.complete(_THEME_SYS, f"The city's people have been saying and feeling:\n{blob}", model=model, temperature=0.0, max_tokens=40)).strip().strip('".')
    except Exception:
        return "(theme extraction failed)"


async def _displacement(llm: InferenceClient, name: str, own: str, attending: str, theme: str, model: str | None) -> float | None:
    try:
        r = await llm.complete_json(_DISP_SYS, _disp_user(name, own, attending, theme), model=model, temperature=0.0, response_format={"type": "json_object"}, max_tokens=80)
        return max(0.0, min(1.0, float(r.get("displacement"))))
    except Exception:
        return None


async def _run(residents_dir: Path, per_resident: int, model: str | None) -> None:
    key = os.environ.get("WW_INFERENCE_KEY", "").strip()
    if not key:
        print("WW_INFERENCE_KEY unset — source .env first.")
        return
    llm = InferenceClient(base_url=os.environ.get("WW_INFERENCE_URL", "https://openrouter.ai/api/v1"), api_key=key, default_model=os.environ.get("WW_INFERENCE_MODEL", "google/gemini-3-flash-preview"), timeout=float(os.environ.get("WW_INFERENCE_TIMEOUT", "120")))
    judge = model or os.environ.get("WW_INFERENCE_MODEL", "google/gemini-3-flash-preview")
    print(f"\nThree-axis read — VOICE · ATTENTION(displacement) · CONTACT   ·  judge: {judge}")
    print("=" * 100)

    dirs = sorted(d for d in residents_dir.iterdir() if d.is_dir() and (d / "memory").is_dir() and not d.name.startswith("_"))
    roster = _roster(dirs)
    cast: list[dict[str, Any]] = []
    for d in dirs:
        run_start, utterances = rr._read_ledger(d)
        inward = _read_felt_and_journal(d, run_start)
        own = rr._private_sample(rr._read_journal(d, run_start), rr._read_kept(d))
        if not (utterances or inward) or not own:
            continue
        cast.append({"name": d.name, "own": own, "utterances": [u["msg"] for u in utterances], "inward": inward})

    if not cast:
        print("  no residents with output yet.\n")
        await llm.close()
        return

    # ATTENTION needs the population's dominant theme first (one call over a cross-resident sample).
    all_out = [s for c in cast for s in (c["utterances"] + c["inward"])]
    theme = await _dominant_theme(llm, all_out, model)
    print(f"  population's dominant shared concern: \"{theme}\"\n")

    v_all: list[float] = []
    disp_all: list[float] = []
    contact_dir = contact_tot = 0
    try:
        for c in cast:
            attending = " | ".join((c["utterances"] + c["inward"])[:30])
            # VOICE (public register retention) — reuse the register_retention judge on utterances.
            pub = [{"msg": m, "chan": "x"} for m in c["utterances"]]
            vscores = await rr._score_resident(llm, c["name"], c["own"], pub, per_resident, model) if pub else []
            v = sum(s["ret"] for s in vscores) / len(vscores) if vscores else None
            # ATTENTION (displacement).
            disp = await _displacement(llm, c["name"], c["own"], attending, theme, model)
            # CONTACT (mechanical).
            directed, total = _contact_score(c["utterances"], c["name"], roster, len(c["inward"]))
            contact_dir += directed
            contact_tot += total
            if v is not None:
                v_all.append(v)
            if disp is not None:
                disp_all.append(disp)
            vtxt = f"{v:.2f}" if v is not None else " — "
            dtxt = f"{disp:.2f}" if disp is not None else " — "
            cr = (directed / total) if total else 0.0
            print(f"  {c['name']:<22} voice {vtxt}  displacement {dtxt}  contact {cr:.0%} ({directed}/{total})  · utt {len(c['utterances'])} inward {len(c['inward'])}")
    finally:
        await llm.close()

    print("-" * 100)
    voice = sum(v_all) / len(v_all) if v_all else 0.0
    disp = sum(disp_all) / len(disp_all) if disp_all else 0.0
    contact = (contact_dir / contact_tot) if contact_tot else 0.0
    print(f"  POPULATION  ·  VOICE-retention {voice:.2f}   ·   ATTENTION-displacement {disp:.2f}   ·   CONTACT {contact:.0%}")
    print("  health = distinct voices (VOICE high) + genuinely connected (CONTACT high) + over a real shared thing")
    print("           WITHOUT it crowding out who each one is (DISPLACEMENT low).")
    print(f"  reading: {'voices kept' if voice >= 0.6 else 'VOICES COLLAPSING (assimilation)'} · "
          f"{'selves intact alongside the shared' if disp < 0.5 else 'SELVES DISPLACED by the shared thing'} · "
          f"{'a real we (minds engage)' if contact >= 0.25 else 'NO-WE (minds do not engage — converged alone)'}\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="Three-axis convergence read: voice / attention-displacement / contact.")
    ap.add_argument("--residents", default="shards/ww_sfo/residents")
    ap.add_argument("--per-resident", type=int, default=4, help="utterances judged per resident for VOICE")
    ap.add_argument("--model", default=None)
    args = ap.parse_args()
    asyncio.run(_run(Path(args.residents), args.per_resident, args.model))


if __name__ == "__main__":
    main()
