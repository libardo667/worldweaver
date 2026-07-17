# Agent runtime guidance

The repository-level `CLAUDE.md`, `prune/VISION.md`, active work item, and live code are authoritative.
This file narrows that guidance for `ww_agent/`.

## Read first

1. `src/resident.py` — one resident's composition root.
2. `src/runtime/cognitive_core.py` — the current perceive → integrate → ignite → pulse → act path.
3. `src/runtime/ledger.py` and `src/runtime/mirror.py` — durable evidence and derived runtime state.
4. `src/runtime/{perception,integrator,pulse_engine,effectors}.py` — the principal seams.
5. Tests matching the surface being changed.

The former fast/slow/mail loop bank and tiered `src/memory/` package are gone. Do not recreate them or
describe them as current architecture. Timing and model fields with loop-era names remain compatibility
inputs in the identity loader; they do not restore the old ownership model.

## Runtime invariants

- A resident has one `CognitiveCore`; independent behavior schedulers must not compete with it.
- Durable observations and actions enter the append-only ledger. Runtime views are projections, not a
  second source of truth.
- The ledger file keeps the complete history for recovery and research. Normal writes advance a versioned
  checkpoint; updates that need a rebuild read at most the latest 10,000 entries. Only checkpoint recovery
  may reread the complete file. Do not make the normal write path grow with lifetime history again.
- Polling a source emits a stable stimulus packet; it does not by itself mean the resident attended to
  that source. Prompt-included encounters transition from `pending` to `observed` through ledger events.
- `runtime/prompt_context.py` is the typed selection boundary between perception and prose. Mode policy
  must be explicit there; source selection, recall/affect input, traces, and packet consumption must agree.
- Exact prompts/completions may be captured in `memory/prompt_traces.jsonl` as private diagnostics. This
  file is evidence about the inference boundary, never cognitive input; no reducer may read it.
- `WorldWeaverClient` is the engine boundary. Keep engine-specific transport out of cognitive modules.
- Canonical identity is immutable at runtime. Proposed growth is written separately and matures through
  the growth pipeline.
- Capabilities are concrete effectors and world affordances, not permissions implied only by prompts.
- Elective information uses typed `Pulse.reach` → `InformationAccess`; it never masquerades as `act.do`
  and never crosses the engine action/narration endpoint. A reach continuation may end with no outward act.
- Information providers return structured records retaining provenance, freshness, locality, visibility,
  and selection mode. Render records only at the inference boundary; traces keep the structured form.
- Physical `mark` acts use the narrator-free world-trace endpoint. Local trace encounters are bounded,
  source-attributed, and consume-on-prompt; they never enter chat or the rolling world-event bundle.
- WorldWeaver is the canonical owner of the resident substrate. `the-stable` is source history only:
  consult it when lineage is useful, but never land new work there or mechanically sync it into this tree.

## Validation

From `ww_agent/`:

```bash
.venv/bin/python -m pytest tests -q
```

For a cross-project change, also run from `worldweaver_engine/`:

```bash
python scripts/dev.py check
```

When architecture changes, update this file, `README.md`, and `src/README.md` in the same slice.
