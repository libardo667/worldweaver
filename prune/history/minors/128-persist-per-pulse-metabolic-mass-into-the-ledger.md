# Persist per-pulse metabolic mass (tokens + model + latency) into the ledger

> **Legacy Stable ID: Minor 63. Disposition: implemented in the legacy Stable runtime; archived
> 2026-07-14.** Its four acceptance criteria are complete. WorldWeaver runtime reconvergence is owned by
> Majors 76 and 86; active Major 120 must verify the fields exist locally before beginning an energy run.

## Metadata

- ID: 128-persist-per-pulse-metabolic-mass-into-the-ledger
- Type: minor
- Owner: Levi
- Status: **DONE (2026-06-18)** — `InferenceClient` now records `last_model` per call and exposes
  `is_local` (pen_local); the pulse engine measures latency around the inference call and attaches a
  `metabolic` reading to the `Pulse`; `route_pulse` writes it into the `pulse_emitted` payload when
  present. Strictly additive and absence-tolerant (a usage-less stub mind omits it, behavior
  unchanged). 4 new tests in `tests/test_metabolic_mass.py`; full suite 252 passed.
- Risk: low

## Problem

The substrate already *holds* the numbers needed to measure a familiar's metabolism, and
then throws them away. `InferenceClient` records `last_usage` and running prompt/completion
totals on every call (`src/inference/client.py:62-131` — the comment says it outright:
"lets callers measure real token cost"), but **nothing persists it**: no caller reads those
fields, and the `pulse_emitted` ledger event carries no token counts (verified against
cinder's real ledger — no usage fields in any payload). The metabolic record dies with the
process.

The result: the duty cycle is derivable from the ledger *today* (cinder = 45 ignitions /
135 ticks = 33% over 38 h), but the **mass** of each pulse — how many tokens it actually
cost, on which model, at what latency — is not. Frequency without mass. Every downstream
energy/cost question (Minor 120's dollar story going forward, Major 120's RQ1, Major 119's
Phase-2 cost claim) needs this term, and none of them can have it until a pulse writes its
own cost into the log. This is the single highest-leverage instrument the project is missing,
and it is hours of work because the data is already in hand at the moment the pulse returns.

See `research/writeups/the-metabolism-of-tending.md` (Part 2, Tier 0) for the full framing.

## Proposed Solution

Thread the usage already captured by `InferenceClient` into the `pulse_emitted` (and
`pulse_act_emitted`) ledger event payload, so each consequential pulse records its own
metabolic cost going forward. No new measurement, no new dependency — just stop discarding
what is already computed.

Add to the pulse event payload, when available:
- `model` — the pen that fired this pulse (string; already known to the pulse engine).
- `prompt_tokens`, `completion_tokens` — from `client.last_usage` for *this* call (not the
  running total).
- `latency_ms` — wall-clock around the inference call (cheap to measure at the call site).
- `pen_local` — boolean derived from the inference base URL (localhost/Ollama vs cloud), so
  later analysis can split local-pen pulses from cloud-pen pulses without re-deriving it.

Keep it strictly additive and absence-tolerant: if `last_usage` is empty (a stub mind, or a
provider that returns no usage), the fields are simply omitted — no behavior change, and the
offline stub tests stay green.

## Files Affected

- `src/inference/client.py` — expose this-call usage + latency cleanly if not already
  returned alongside the response (the totals exist; surface the per-call delta + timing).
- `src/runtime/pulse_engine.py` — capture model + usage + latency at the inference call site
  and pass them through to the event the cognitive core emits.
- `src/runtime/cognitive_core.py` — include the metabolic fields in the `pulse_emitted` /
  `pulse_act_emitted` event payload.
- (tests) `tests/` — a test asserting a live-usage pulse records the fields, and that a
  no-usage (stub) pulse omits them with byte-identical behavior otherwise.

## Acceptance Criteria

- [x] After a live pulse, its `pulse_emitted` ledger event payload carries `model`,
      `prompt_tokens`, `completion_tokens`, `latency_ms`, and `pen_local`. — `test_live_pulse_records_metabolic_mass`.
- [x] With a stub/usage-less mind, behavior is unchanged and the fields are simply absent
      (offline stub tests remain green) — proven by a test. — `test_stub_pulse_omits_metabolic_and_is_unchanged`;
      the full 252-test suite stays green.
- [x] A ~10-line analysis over one familiar's ledger can now report total tokens, mean
      per-pulse mass, and the local-vs-cloud split — not just the duty cycle. — `test_summed_ledger_mass_reconciles_with_a_simple_analysis`.
- [x] The running totals already in `InferenceClient` are reconciled against the summed
      per-pulse ledger figures (the log and the counter agree). — same test sums per-pulse `prompt_tokens`/
      `completion_tokens` and matches the per-call usage exactly (one pulse → one `pulse_emitted` mass).

## Implementation note (2026-06-18)

- **Mass rides on `pulse_emitted` only, NOT `pulse_act_emitted`.** The spec named both, but a pulse fires
  exactly one `pulse_emitted` and 0-or-1 `pulse_act_emitted`; putting the same token mass on both invites a
  double-count when summing cost. Keeping it on the one always-emitted event makes `sum(pulse_emitted.mass)`
  the honest total, and an act's cost is joinable to its pulse by `pulse_id`. Rollback is unchanged (reducers
  ignore unknown keys).
- **Latency is wall-clock at the call site** (`time.monotonic()` around `_llm.complete`), so it includes
  retry time — the real cost of getting the pulse, not just the last successful HTTP round-trip.
- **`model` is read from `client.last_model`** (the actual pen the request used) rather than the engine's
  configured `self._model`, which may be `None` (→ the client's default); falls back to `self._model` if the
  client doesn't expose it.

## Validation Commands

- `.venv/bin/python -m pytest tests/ -q`
- `.venv/bin/python scripts/familiar.py --home familiar/cinder --ticks 4 --pause 0.2 --no-weather`
  then inspect the tail of `familiar/cinder/memory/runtime_ledger.jsonl` for the new fields
  (stub run → fields absent; a live run → fields present).

## Pruning Prevention Controls

- Authoritative path: the existing `InferenceClient.last_usage` is the source; the pulse
  engine is the single point that already wraps the call. No new accounting path.
- Parallel path introduced: none — this extends the existing `pulse_emitted` event, it does
  not add a second cost ledger.
- Artifact output target: the existing per-familiar `runtime_ledger.jsonl`. No new file.
- Default-path impact: additive-only; absent usage → identical behavior.

## Risks and Rollback

- Risk: ledger bloat (a few integer fields per pulse). Negligible — pulses are ignition-gated
  and already the rarest event class.
- Risk: provider usage fields vary in shape across models. Mitigate by reading defensively
  (the client already coerces with `int(... or 0)`), and omitting rather than guessing.
- Rollback: drop the added fields from the event payload — the ledger reducers ignore
  unknown keys, so no projection depends on them; nothing downstream breaks.
