#!/usr/bin/env python3
"""Pen throughput + feasibility sweep for the swap-arm choice (NOT a gemini-speed match).

Why this exists and what it is NOT: the swap replay is offline + deterministic, so a pen's tok/s changes
how LONG an arm takes, never WHAT it chooses. Speed is therefore a feasibility FLOOR, not a selection
axis — and matching gemini's speed would bias toward same-family pens (shared serving infra), the one
thing a foreign pen must not be. So: measure tok/s across genuinely-DIFFERENT families, convert to
wall-clock for the real run, exclude only the impractically slow, and pick foreign pens for diversity.

Measures per model: effective tok/s (completion_tokens / wall_time, latency-inclusive — the number that
governs a many-sequential-call replay) over median-of-N pulse-sized generations, and the estimated
wall-clock for a PULSES-pulse replay arm.

Usage: set WW_INFERENCE_KEY (source the shard .env); python3 pen_throughput_bench.py [--pulses 1300]
"""
import argparse, json, os, statistics, sys, time
import httpx

URL = os.environ.get("WW_INFERENCE_URL", "https://openrouter.ai/api/v1") + "/chat/completions"
KEY = os.environ.get("WW_INFERENCE_KEY", "")
HOME = "google/gemini-3-flash-preview"

# Curated for FAMILY DIVERSITY (+ a same-family ref to make the matching trap visible). Invalid/unavailable
# IDs are skipped gracefully.
CANDIDATES = [
    ("google/gemini-3-flash-preview", "Google (HOME pen — baseline)"),
    ("google/gemini-3.5-flash", "Google (same family — the 'speed match' trap)"),
    ("anthropic/claude-haiku-4.5", "Anthropic (current pre-reg foreign arm)"),
    ("openai/gpt-5-mini", "OpenAI"),
    ("openai/gpt-5-nano", "OpenAI (small)"),
    ("deepseek/deepseek-v4-flash", "DeepSeek"),
    ("meta-llama/llama-4-maverick", "Meta Llama-4"),
    ("meta-llama/llama-4-scout", "Meta Llama-4 (small)"),
    ("mistralai/mistral-small-2603", "Mistral"),
    ("mistralai/ministral-8b-2512", "Mistral (small)"),
    ("amazon/nova-2-lite-v1", "Amazon Nova"),
    ("qwen/qwen3-235b-a22b", "Qwen"),
    ("x-ai/grok-4-fast", "xAI Grok"),
    ("cohere/command-r-08-2024", "Cohere"),
]

# A pulse-sized, structured generation (felt-sense + a short action) — approximates real pen load.
SYS = "You are a person reacting to a moment. Reply ONLY with compact JSON: {\"felt_sense\": <~40 words>, \"act\": {\"kind\": \"speak\", \"body\": <~30 words>, \"target\": <a name>}}."
USR = "The fog rolls in off the bay at the South Waterfront after dark. Jihoon is pouring barley tea. React."


def one_call(client, model):
    t0 = time.time()
    r = client.post(URL, headers={"Authorization": f"Bearer {KEY}"}, json={
        "model": model, "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": USR}],
        "max_tokens": 500, "temperature": 0.7, "usage": {"include": True},
    })
    dt = time.time() - t0
    r.raise_for_status()
    d = r.json()
    out = d["choices"][0]["message"]["content"] or ""
    ct = (d.get("usage") or {}).get("completion_tokens") or max(1, len(out.split()) * 4 // 3)
    ok_json = False
    try:
        json.loads(out[out.find("{"): out.rfind("}") + 1]); ok_json = True
    except Exception:
        pass
    return dt, ct, ok_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pulses", type=int, default=1300, help="replay pulses per arm (order-of-magnitude; KEEP run sets the real length)")
    ap.add_argument("--runs", type=int, default=2)
    a = ap.parse_args()
    if not KEY:
        print("WW_INFERENCE_KEY required (source the shard .env)", file=sys.stderr); return 2
    rows = []
    with httpx.Client(timeout=120) as client:
        for model, fam in CANDIDATES:
            times, toks, jsons = [], [], []
            for _ in range(a.runs):
                try:
                    dt, ct, okj = one_call(client, model)
                    times.append(dt); toks.append(ct); jsons.append(okj)
                except Exception as e:
                    code = getattr(getattr(e, "response", None), "status_code", "")
                    rows.append((model, fam, None, None, None, f"skip ({code or e.__class__.__name__})")); break
            else:
                med_t = statistics.median(times); med_ct = statistics.median(toks)
                tps = med_ct / med_t if med_t else 0
                wall_h = (a.pulses * med_t) / 3600.0  # sequential worst case
                rows.append((model, fam, round(tps, 1), round(med_t, 2), round(wall_h, 1), "json-ok" if all(jsons) else "JSON?"))
    home_tps = next((r[2] for r in rows if r[0] == HOME and r[2]), None)
    print(f"\n{'model':38} {'tok/s':>7} {'s/call':>7} {'arm-wall(h)':>11}  {'vs home':>8}  family / note")
    print("-" * 120)
    for model, fam, tps, sc, wh, note in rows:
        rel = f"{tps/home_tps:.2f}x" if (tps and home_tps) else "--"
        print(f"{model:38} {str(tps or note):>7} {str(sc or ''):>7} {str(wh or ''):>11}  {rel:>8}  {fam} [{note}]")
    print(f"\narm-wall(h) = {a.pulses} sequential pulses x s/call / 3600 (parallelism across residents divides this).")
    print("Read it as a FLOOR filter, not a ranking: pick >=2 DIFFERENT-family pens above your wall-clock tolerance.")


if __name__ == "__main__":
    raise SystemExit(main())
