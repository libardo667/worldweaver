#!/usr/bin/env python
"""Probe registry models and remove ones that exceed response timeout.

Usage:
  python scripts/prune_slow_models.py
  python scripts/prune_slow_models.py --timeout-seconds 30 --dry-run
"""

from __future__ import annotations

import argparse
import ast
import sys
import time
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.llm_client import get_llm_client  # noqa: E402
from src.services.model_registry import list_available_models  # noqa: E402


MODEL_REGISTRY_PATH = ROOT / "src" / "services" / "model_registry.py"
DEFAULT_PROMPT = "Reply with exactly: ok"


def _is_timeout_error(exc: Exception) -> bool:
    name = exc.__class__.__name__.lower()
    message = str(exc).lower()
    return (
        "timeout" in name
        or "timed out" in message
        or "read timeout" in message
        or "deadline" in message
    )


def _prune_registry_file(model_ids_to_remove: set[str]) -> int:
    if not model_ids_to_remove:
        return 0

    source = MODEL_REGISTRY_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)

    registry_node: ast.Dict | None = None
    for node in tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "MODEL_REGISTRY"
            and isinstance(node.value, ast.Dict)
        ):
            registry_node = node.value
            break

    if registry_node is None:
        raise RuntimeError("Could not find MODEL_REGISTRY assignment in model_registry.py")

    remove_ranges: list[tuple[int, int]] = []
    for key_node, value_node in zip(registry_node.keys, registry_node.values):
        if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
            continue
        model_id = key_node.value
        if model_id not in model_ids_to_remove:
            continue
        if value_node.end_lineno is None:
            raise RuntimeError(f"Could not determine end line for registry entry: {model_id}")
        start_idx = key_node.lineno - 1
        end_idx = value_node.end_lineno - 1
        remove_ranges.append((start_idx, end_idx))

    if not remove_ranges:
        return 0

    for start_idx, end_idx in sorted(remove_ranges, reverse=True):
        del lines[start_idx : end_idx + 1]

    MODEL_REGISTRY_PATH.write_text("".join(lines), encoding="utf-8")
    return len(remove_ranges)


def _probe_models(
    model_ids: Iterable[str],
    *,
    timeout_seconds: float,
    max_tokens: int,
    prompt: str,
) -> tuple[list[str], list[str], list[str]]:
    client = get_llm_client()
    if client is None:
        raise RuntimeError(
            "No LLM client available. Configure OPENROUTER_API_KEY, LLM_API_KEY, or OPENAI_API_KEY."
        )

    ok_models: list[str] = []
    timeout_models: list[str] = []
    failed_models: list[str] = []

    for model_id in model_ids:
        started = time.perf_counter()
        try:
            client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=max_tokens,
                timeout=timeout_seconds,
            )
            elapsed = time.perf_counter() - started
            if elapsed > timeout_seconds:
                print(f"[TIMEOUT] {model_id} ({elapsed:.2f}s, over threshold)")
                timeout_models.append(model_id)
            else:
                print(f"[OK]      {model_id} ({elapsed:.2f}s)")
                ok_models.append(model_id)
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - started
            if _is_timeout_error(exc):
                print(f"[TIMEOUT] {model_id} ({elapsed:.2f}s) :: {exc}")
                timeout_models.append(model_id)
            else:
                print(f"[ERROR]   {model_id} ({elapsed:.2f}s) :: {exc}")
                failed_models.append(model_id)

    return ok_models, timeout_models, failed_models


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe all dropdown models and remove slow ones from model registry."
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="Per-model response timeout in seconds (default: 30).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=8,
        help="Max completion tokens for probe prompt (default: 8).",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=DEFAULT_PROMPT,
        help="Probe prompt text (default: 'Reply with exactly: ok').",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not modify model_registry.py; only print what would be removed.",
    )
    args = parser.parse_args()

    models = [entry["model_id"] for entry in list_available_models()]
    print(f"Probing {len(models)} registry models (timeout={args.timeout_seconds:.1f}s)...")
    ok_models, timeout_models, failed_models = _probe_models(
        models,
        timeout_seconds=args.timeout_seconds,
        max_tokens=args.max_tokens,
        prompt=args.prompt,
    )

    print("\nSummary")
    print(f"- OK: {len(ok_models)}")
    print(f"- TIMEOUT (> {args.timeout_seconds:.1f}s): {len(timeout_models)}")
    print(f"- ERROR (kept): {len(failed_models)}")

    if timeout_models:
        print("- Timed out models:")
        for model_id in timeout_models:
            print(f"  - {model_id}")

    if args.dry_run:
        print("\nDry run enabled; model_registry.py not modified.")
        return 0

    removed = _prune_registry_file(set(timeout_models))
    print(f"\nRemoved {removed} timed-out model entries from {MODEL_REGISTRY_PATH}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
