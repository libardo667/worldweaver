from __future__ import annotations

from scripts.benchmark_three_layer import _build_comparison, summarize_latencies
from tests.integration_harness_helpers import assert_metric_values, assert_nested_values


def test_summarize_latencies_computes_basic_stats() -> None:
    summary = summarize_latencies([100.0, 200.0, 300.0, 400.0])
    assert_metric_values(
        summary,
        {
            "count": 4.0,
            "min_ms": 100.0,
            "max_ms": 400.0,
            "avg_ms": 250.0,
            "p50_ms": 250.0,
            "p95_ms": 385.0,
        },
    )


def test_build_comparison_returns_deltas() -> None:
    baseline = {
        "mode": "strict_off",
        "bootstrap_ms": 1000.0,
        "turn_latency_summary": {"avg_ms": 200.0, "p50_ms": 180.0, "p95_ms": 260.0},
    }
    candidate = {
        "mode": "strict_on",
        "bootstrap_ms": 1250.0,
        "turn_latency_summary": {"avg_ms": 230.0, "p50_ms": 210.0, "p95_ms": 300.0},
    }
    comparison = _build_comparison(baseline, candidate)

    assert_nested_values(
        comparison,
        {
            ("bootstrap", "delta_ms"): 250.0,
            ("bootstrap", "delta_pct"): 25.0,
            ("turn_latency_deltas", "avg_ms", "delta_ms"): 30.0,
            ("turn_latency_deltas", "p50_ms", "delta_ms"): 30.0,
            ("turn_latency_deltas", "p95_ms", "delta_ms"): 40.0,
        },
    )
