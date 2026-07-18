# Current-model pulse compatibility — 2026-07-17

## Question

Can several current model families produce WorldWeaver's typed pulse reliably, and do any of them
immediately choose outward action when placed in the same neutral synthetic situation?

This is a contract probe, not a resident-behavior experiment. It uses a synthetic person and place,
does not open a city or resident home, and records no generated prose.

## Method

Tool: `research/probes/model_battery.py` at commit `6ff815e`.

Each model received the same ordinary reactive pulse prompt: a newly awake synthetic resident in Test
Square, with two reachable locations and two elective information sources. Temperature was omitted so
each route used its model default. Three independent calls were made per model through the configured
OpenAI-compatible endpoint.

Commands:

```bash
python dev.py run research/probes/model_battery.py --trials 1 --run
python dev.py run research/probes/model_battery.py --trials 2 --run
```

## Results

| Model | Valid pulses | Chose a private reach | Chose an outward act | Reach + act conflicts | Mean latency | Total prompt tokens | Total completion tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| `google/gemini-3-flash-preview` | 3/3 | 3/3 | 0/3 | 0 | 2.785 s | 4,287 | 847 |
| `google/gemini-3.5-flash` | 3/3 | 3/3 | 0/3 | 0 | 2.819 s | 4,287 | 1,046 |
| `anthropic/claude-sonnet-5` | 3/3 | 3/3 | 0/3 | 0 | 4.367 s | 5,736 | 872 |
| `openai/gpt-5.6-terra` | 3/3 | 3/3 | 0/3 | 0 | 2.997 s | 4,101 | 583 |
| `deepseek/deepseek-v4-flash` | 3/3 | 3/3 | 0/3 | 0 | 5.754 s | 4,178 | 1,448 |

All 15 calls completed without a transport error. All 15 passed `Pulse.from_dict`; none reproduced
Riley's earlier invalid simultaneous `reach` and `act` response.

## What this supports

- All five routes are compatible enough for a live pilot. Omitting temperature successfully covered
  the routes that do not advertise that parameter.
- Initial information-gathering was not unique to Gemini 3 Flash. Every sampled model chose to inspect
  something before acting.
- This is consistent with the idea that a neutral language model tends to orient through information
  before taking an embodied action when no need or task makes movement relevant.

## What this does not support

- It does not establish a universal LLM preference for stillness. The prompt offered useful information,
  and there were only three samples per model.
- It does not show what happens after the requested information returns. The live resident loop permits
  several continuation reads and then an act; this probe measured only the first response.
- It does not compare identity continuity, long-term initiative, topic diversity, or city behavior.

## Next test

Run one real resident for 15 minutes at the natural 20-second cadence with a run-only model override and
action tendency unchanged. Judge contract health, selective reading, coherent response to results, and
outward behavior separately. Do not score movement itself as success.
