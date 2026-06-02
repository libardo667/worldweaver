#!/usr/bin/env python3
"""Generate souls with the doula's seed prompt and check they come out distinct.

Tests the fix to _SEED_SYSTEM: feed several characters — including ones whose
evidence is vague/atmospheric (the kind that used to produce "sensitive observer
of the city's pulse" clones) — and see whether the new prompt yields concrete,
unmistakable people with no baked-in weather. Pair with voice_test.py to confirm
distinct souls then produce distinct voices.

Usage (from ww_agent/):
    set -a && . <(sed 's/\r$//' .env) && set +a
    ../worldweaver_engine/.venv/bin/python scripts/seed_test.py
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.inference.client import InferenceClient  # noqa: E402
from src.loops.doula import _SEED_SYSTEM  # noqa: E402

# Name + the world's recorded evidence — two atmospheric (the failure mode), one concrete.
CASES = {
    "Vivian": [
        "Vivian was seen near the humming pavement of Alamo Square as a crowd gathered.",
        "She noticed the shift in the collective attention as someone arrived.",
        "Observed standing quietly, attuned to the mood of the block.",
    ],
    "Hector": [
        "Hector runs the hardware store on Mission Street.",
        "He complained loudly that the new condos are pushing the rents up.",
        "Fixed a neighbor's bike chain for free and grumbled the whole time.",
    ],
    "Lena": [
        "Lena plays cello for coins in the BART station at Civic Center.",
        "She argues with her brother about money over the phone.",
        "Commuters sometimes stop and miss their trains to listen.",
    ],
}

_ATMOSPHERE_RX = re.compile(r"\b(pulse|hum|currents?|rhythm|mood|attuned|texture|the city's|atmosphere|weather|degrees|partly cloudy|afternoon|morning sun)\b", re.IGNORECASE)


async def _main() -> None:
    key = os.environ.get("WW_INFERENCE_KEY", "").strip()
    if not key:
        print("WW_INFERENCE_KEY unset — source .env first.")
        return
    model = os.environ.get("WW_DOULA_MODEL") or os.environ.get("WW_INFERENCE_MODEL", "google/gemini-3-flash-preview")
    llm = InferenceClient(base_url=os.environ.get("WW_INFERENCE_URL", "https://openrouter.ai/api/v1"), api_key=key, default_model=model, timeout=float(os.environ.get("WW_INFERENCE_TIMEOUT", "120")))
    print(f"\nseeding souls with the new _SEED_SYSTEM  ·  model: {model}\n")
    try:
        for name, evidence in CASES.items():
            user = f"Character: {name}\n\nWhat the world has recorded about them:\n" + "\n".join(f"- {e}" for e in evidence)
            soul = (await llm.complete(system_prompt=_SEED_SYSTEM, user_prompt=user, temperature=0.7, max_tokens=600)).strip()
            hits = sorted(set(m.lower() for m in _ATMOSPHERE_RX.findall(soul)))
            print(f"── {name}")
            print(f"   {soul}")
            print(f"   [atmosphere/weather clichés: {hits if hits else 'none'}]\n")
    finally:
        await llm.close()


if __name__ == "__main__":
    asyncio.run(_main())
