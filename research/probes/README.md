# probes/ — research & diagnostic instrumentation

Moved here from `ww_agent/scripts/` (Major 83 slice 3): these are **measurement tools**, not
runtime — nothing in the agent imports them. They live in `research/` because that is this
repo's box for "verify instead of trust": the probes are the recompute/measurement half of the
run records under `../runs/`.

## Contents

- `pen_swap/` — the pen-swap record/replay harness (record a resident's perception stream with
  one model, replay it under another; divergence + parity analysis). See its `DESIGN.md`.
- `register_calibration.py`, `register_construct_check.py`, `register_retention.py`,
  `peer_register_check.py` (+ `fixtures/`) — voice/register probes. The peer-register check
  runs against `../artifacts/historical-residents/` and its known-positive JSONL fixture.
- `reciprocity.py`, `three_axis.py`, `soul_domain_retention.py`, `voice_test.py`,
  `field_guide.py` — identity/relationship measurement.
- `cost_curve.py`, `score_predictions.py`, `pulse_demo.py`, `seed_test.py`,
  `build_parallel_probe.py`, `build_stel_probe.py` — cost, prediction-scoring, and pulse/seed
  diagnostics.

## Running

Probes that import the agent runtime bootstrap `sys.path` to `<repo>/ww_agent` themselves —
run them from anywhere:

```bash
python research/probes/voice_test.py --help
python research/probes/pen_swap/record_run.py --help
```

Docstring examples inside some probes still show the old `scripts/...` invocation paths and
`../shards/...` CWD-relative defaults (they assumed being run from `ww_agent/`); pass explicit
`--residents shards/<city>/residents` style paths from the repo root instead.

Operational scripts (shard ops, substrate sync, familiar entry) stayed in `ww_agent/scripts/`.

`tests/` — pytest coverage for the probes themselves (run `python -m pytest ../research/probes/tests/`
from `ww_agent/`, whose dev extra provides pytest).
