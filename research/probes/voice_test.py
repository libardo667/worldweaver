#!/usr/bin/env python3
"""Feed the SAME moment to several souls and print each one's pulse.

A controlled test of whether distinct souls produce distinct voices through the
drive vector + pulse — isolating the echo chamber's cause. If genuinely
different characters diverge sharply on the same input, the runtime is sound and
the homogeneity lives in the souls (doula quality), not the machinery.

Each soul: drive vector built from its canonical text (real embeddings via
WW_EMBEDDING_*), then one real pulse (WW_INFERENCE_*) on a shared "the hum is
tightening" moment that 12 doula residents all echoed.

Usage (from ww_agent/):
    set -a && . <(sed 's/\r$//' .env) && set +a
    WW_EMBEDDING_URL=http://172.20.240.1:11434/v1 WW_EMBEDDING_MODEL=nomic-embed-text \
        ../worldweaver_engine/.venv/bin/python scripts/voice_test.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ww_agent"))

from src.identity.loader import LoopTuning, ResidentIdentity  # noqa: E402
from src.inference.client import InferenceClient  # noqa: E402
from src.runtime.drive import DriveVector, RemoteEmbedder  # noqa: E402
from src.runtime.pulse_engine import LLMPulseProducer  # noqa: E402

# Three deliberately distinct people — different concerns, different registers.
SOULS = {
    "Mardel (mechanic)": (
        "Mardel fixes what is broken and says what is true. He has no patience for talk that circles and "
        "goes nowhere — a thing works or it does not, and if it does not you find the loose bolt and you "
        "fix it. He measures people by whether they pull their weight. Talk of the city's 'mood' strikes "
        "him as noise; there is always a real cause, usually mechanical, usually mundane."
    ),
    "Perel (baker)": (
        "Perel keeps a small corner bakery and believes most troubles soften with warmth and bread. She "
        "greets strangers by feeding them. She worries over people the way she worries over dough — "
        "patiently, with her hands, giving them time to rise. The world's sharp edges are easier to bear "
        "when there is something in the oven and someone to share it with."
    ),
    "Soren (night clerk)": (
        "Soren works the night desk and trusts almost nothing he cannot check twice. He reads rooms for "
        "their exits and people for their tells. Crowds make him count heads. He assumes the worst "
        "quietly and is quietly relieved to be wrong. He keeps his voice low, his back to a wall, and his "
        "questions sharper than they sound."
    ),
}

# The shared moment — the exact echo the doula residents all riffed on.
HEARD = [
    {"speaker": "Anika", "message": "the hum is tightening, the air feels brittle this morning", "channel": "local", "is_direct": False},
    {"speaker": "Arlo", "message": "the whole city is pulling tight, like it's holding its breath", "channel": "local", "is_direct": False},
    {"speaker": "Catherine", "message": "there's a friction in the air, a thinning of the texture", "channel": "local", "is_direct": False},
]


def _identity(name: str, soul: str) -> ResidentIdentity:
    return ResidentIdentity(name=name, actor_id="voice", soul=soul, canonical_soul=soul, growth_soul="", vibe="", core="", voice_seed=[], tuning=LoopTuning())


async def _main() -> None:
    key = os.environ.get("WW_INFERENCE_KEY", "").strip()
    if not key:
        print("WW_INFERENCE_KEY unset — source .env first.")
        return
    llm = InferenceClient(
        base_url=os.environ.get("WW_INFERENCE_URL", "https://openrouter.ai/api/v1"),
        api_key=key,
        default_model=os.environ.get("WW_INFERENCE_MODEL", "google/gemini-3-flash-preview"),
        timeout=float(os.environ.get("WW_INFERENCE_TIMEOUT", "120")),
    )
    emb_url = os.environ.get("WW_EMBEDDING_URL", "").strip()
    embedder = RemoteEmbedder(base_url=emb_url, api_key=os.environ.get("WW_EMBEDDING_KEY", "ollama"), model=os.environ.get("WW_EMBEDDING_MODEL", "nomic-embed-text")) if emb_url else None

    print("\nSame moment to every soul:")
    for h in HEARD:
        print(f'  {h["speaker"]}: "{h["message"]}"')
    print(f"\ndrive vector: {'on (' + (embedder._model if embedder else '') + ')' if embedder else 'OFF (no WW_EMBEDDING_URL)'}\n")

    with tempfile.TemporaryDirectory() as tmp:
        for label, soul in SOULS.items():
            identity = _identity(label.split(" ")[0], soul)
            drive = await DriveVector.build(embedder=embedder, constitution=soul) if embedder else None
            mem = Path(tmp) / label.split(" ")[0] / "memory"
            mem.mkdir(parents=True, exist_ok=True)
            producer = LLMPulseProducer(llm=llm, identity=identity, memory_dir=mem, temperature=0.8, drive_vector=drive)
            producer.latest_perception = {"heard": list(HEARD), "location": "Duboce Triangle", "present": ["Anika", "Arlo", "Catherine"]}
            if drive is not None:
                res = await drive.resonance(" ".join(h["message"] for h in HEARD))
                frag = res["resonant"][0]["text"][:80] if res["resonant"] else "(none)"
                print(f"── {label}\n   resonates with: \"{frag}\"")
            else:
                print(f"── {label}")
            pulse = await producer(traces=[], stimulus={"self": {"social_pull": 0.8, "vigilance": 0.5}}, arousal=1.3)
            if pulse is None:
                print("   (no pulse)\n")
                continue
            act = pulse.act
            said = f'{act.kind} → {act.target}: "{act.body}"' if act else "(no act)"
            print(f"   felt: {pulse.felt_sense}")
            print(f"   says: {said}\n")

    await llm.close()
    if embedder is not None:
        await embedder.close()


if __name__ == "__main__":
    asyncio.run(_main())
