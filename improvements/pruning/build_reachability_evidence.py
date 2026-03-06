"""Build reachability evidence from static graph + test route literals + coverage.

Usage (from repo root):
    coverage erase
    coverage run --source=src -m pytest tests -q
    coverage json -o improvements/pruning/COVERAGE_SUMMARY.json
    python improvements/pruning/build_reachability_evidence.py
"""

from __future__ import annotations

import ast
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
TESTS_DIR = REPO_ROOT / "tests"
MAIN_FILE = REPO_ROOT / "main.py"
PRUNING_DIR = REPO_ROOT / "improvements" / "pruning"
COVERAGE_JSON = PRUNING_DIR / "COVERAGE_SUMMARY.json"
OUTPUT_CSV = PRUNING_DIR / "REACHABILITY_EVIDENCE.csv"

HTTP_DECORATORS = {"get", "post", "put", "patch", "delete"}


def _norm(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def _canonical_http_path(path: str) -> str:
    value = str(path or "").strip()
    if not value.startswith("/"):
        return ""
    value = value.split("?", 1)[0]
    if len(value) > 1 and value.endswith("/"):
        value = value.rstrip("/")
    return value


def _module_for_src_path(src_path: Path) -> str:
    rel = src_path.relative_to(REPO_ROOT).with_suffix("")
    return ".".join(rel.parts)


def _module_for_file(file_path: Path, src_module_by_path: Dict[Path, str]) -> str:
    if file_path == MAIN_FILE:
        return "main"
    if file_path in src_module_by_path:
        return src_module_by_path[file_path]
    rel = file_path.relative_to(REPO_ROOT).with_suffix("")
    return ".".join(rel.parts)


def _resolve_from_module(module_name: str, level: int, imported_module: str | None) -> str:
    package_parts = module_name.split(".")[:-1]
    up = max(0, level - 1)
    if up > len(package_parts):
        base_parts: List[str] = []
    else:
        base_parts = package_parts[: len(package_parts) - up]
    if imported_module:
        base_parts.extend(imported_module.split("."))
    return ".".join(base_parts)


def _load_ast(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_coverage() -> Dict[str, Dict[str, float]]:
    if not COVERAGE_JSON.exists():
        raise FileNotFoundError(
            f"Coverage summary missing at {COVERAGE_JSON}. "
            "Run coverage first."
        )
    payload = json.loads(COVERAGE_JSON.read_text(encoding="utf-8"))
    files = payload.get("files", {})
    out: Dict[str, Dict[str, float]] = {}
    for raw_path, info in files.items():
        norm_path = _norm(raw_path)
        if not norm_path.startswith("src/"):
            continue
        summary = info.get("summary", {})
        out[norm_path] = {
            "covered_lines": float(summary.get("covered_lines", 0)),
            "num_statements": float(summary.get("num_statements", 0)),
            "missing_lines": float(summary.get("missing_lines", 0)),
            "percent_covered": float(summary.get("percent_covered", 0.0)),
        }
    return out


def _collect_test_path_literals(test_files: Iterable[Path]) -> Counter:
    path_counter: Counter = Counter()
    for path in test_files:
        tree = _load_ast(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                candidate = _canonical_http_path(node.value)
                if candidate:
                    path_counter[candidate] += 1
            elif isinstance(node, ast.JoinedStr):
                parts: List[str] = []
                for value in node.values:
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        parts.append(value.value)
                    else:
                        parts.append("{}")
                candidate = _canonical_http_path("".join(parts))
                if candidate:
                    path_counter[candidate] += 1
    return path_counter


def _route_pattern_to_regex(route_path: str) -> re.Pattern:
    escaped = re.escape(route_path)
    # Replace escaped "{param}" sections with one path-segment wildcard.
    escaped = re.sub(r"\\\{[^{}]+\\\}", r"[^/]+", escaped)
    return re.compile(rf"^{escaped}/?$")


def _collect_route_hits(
    src_files: Iterable[Path],
    src_module_by_path: Dict[Path, str],
    test_path_literals: Counter,
) -> Tuple[Dict[str, int], Dict[str, List[Tuple[str, int]]]]:
    module_route_hits: Dict[str, int] = defaultdict(int)
    module_route_details: Dict[str, List[Tuple[str, int]]] = defaultdict(list)

    for src_path in src_files:
        if src_path.name == "__init__.py":
            continue
        module_name = src_module_by_path[src_path]
        if not module_name.startswith("src.api."):
            continue

        if module_name.startswith("src.api.game."):
            prefix = "/api"
        elif module_name.startswith("src.api.author."):
            prefix = "/author"
        elif module_name == "src.api.semantic":
            prefix = "/api/semantic"
        else:
            prefix = ""

        tree = _load_ast(src_path)
        if tree is None:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                if not isinstance(decorator.func, ast.Attribute):
                    continue
                if decorator.func.attr not in HTTP_DECORATORS:
                    continue
                if not decorator.args:
                    continue
                first = decorator.args[0]
                if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                    continue

                raw_path = _canonical_http_path(f"{prefix}{first.value}")
                if not raw_path:
                    continue
                route_regex = _route_pattern_to_regex(raw_path)
                hits = sum(
                    count
                    for literal, count in test_path_literals.items()
                    if route_regex.match(literal)
                )
                module_route_hits[module_name] += hits
                module_route_details[module_name].append((raw_path, hits))

    return module_route_hits, module_route_details


def _collect_import_graph(
    files: Iterable[Path],
    src_module_by_path: Dict[Path, str],
    src_modules: Set[str],
) -> Dict[str, Set[str]]:
    reverse: Dict[str, Set[str]] = defaultdict(set)
    for path in files:
        tree = _load_ast(path)
        if tree is None:
            continue
        importer_module = _module_for_file(path, src_module_by_path)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported = alias.name
                    if imported in src_modules:
                        reverse[imported].add(importer_module)
            elif isinstance(node, ast.ImportFrom):
                base = _resolve_from_module(importer_module, node.level, node.module)
                if base in src_modules:
                    reverse[base].add(importer_module)
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    candidate = f"{base}.{alias.name}" if base else alias.name
                    if candidate in src_modules:
                        reverse[candidate].add(importer_module)
    return reverse


def _coverage_band(percent_covered: float, statements: float) -> str:
    if statements <= 0:
        return "na"
    if percent_covered >= 80.0:
        return "high"
    if percent_covered >= 50.0:
        return "medium"
    if percent_covered >= 25.0:
        return "low"
    return "very_low"


def _build_rows() -> List[Dict[str, str]]:
    src_files = sorted(SRC_DIR.rglob("*.py"))
    test_files = sorted(TESTS_DIR.rglob("*.py"))

    src_module_by_path = {
        path: _module_for_src_path(path)
        for path in src_files
    }
    # Keep the same scope as prior artifact: non-__init__ source modules only.
    scored_src_files = [p for p in src_files if p.name != "__init__.py"]
    src_modules = {
        src_module_by_path[path]
        for path in scored_src_files
    }

    coverage = _load_coverage()
    reverse_graph = _collect_import_graph(
        files=[MAIN_FILE, *src_files, *test_files],
        src_module_by_path=src_module_by_path,
        src_modules=src_modules,
    )

    test_path_literals = _collect_test_path_literals(test_files)
    route_hits, route_details = _collect_route_hits(
        src_files=scored_src_files,
        src_module_by_path=src_module_by_path,
        test_path_literals=test_path_literals,
    )

    test_blob = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in test_files
    )

    rows: List[Dict[str, str]] = []
    for path in sorted(scored_src_files):
        module = src_module_by_path[path]
        rel_path = _norm(path.relative_to(REPO_ROOT))

        cov = coverage.get(rel_path, {})
        covered_lines = int(cov.get("covered_lines", 0))
        statements = int(cov.get("num_statements", 0))
        missing_lines = int(cov.get("missing_lines", 0))
        percent_covered = float(cov.get("percent_covered", 0.0))

        importers = reverse_graph.get(module, set())
        runtime_importers = sorted(
            importer
            for importer in importers
            if importer == "main" or importer.startswith("src.")
        )
        test_importers = sorted(
            importer for importer in importers if importer.startswith("tests.")
        )

        test_module_mentions = test_blob.count(module)
        test_route_hits = int(route_hits.get(module, 0))

        if test_route_hits > 0 or test_importers or test_module_mentions > 0:
            static_tier = "strong"
        elif runtime_importers:
            static_tier = "transitive_only"
        else:
            static_tier = "none"

        executed = covered_lines > 0
        coverage_band = _coverage_band(percent_covered, statements)

        weak_candidate = (
            (not executed)
            or (
                static_tier == "transitive_only"
                and coverage_band in {"very_low", "low"}
            )
        )

        if not executed and static_tier == "none":
            final_tier = "none"
        elif executed and weak_candidate:
            final_tier = "executed_but_weak"
        elif executed:
            final_tier = "strong"
        else:
            final_tier = "static_only"

        route_examples = "; ".join(
            f"{route}:{hits}"
            for route, hits in route_details.get(module, [])[:8]
        )

        rows.append(
            {
                "module": module,
                "path": rel_path,
                "statements": str(statements),
                "covered_lines": str(covered_lines),
                "missing_lines": str(missing_lines),
                "coverage_percent": f"{percent_covered:.2f}",
                "coverage_band": coverage_band,
                "executed_in_tests": "yes" if executed else "no",
                "runtime_importer_count": str(len(runtime_importers)),
                "test_importer_count": str(len(test_importers)),
                "test_module_string_mentions": str(test_module_mentions),
                "test_route_pattern_hits": str(test_route_hits),
                "static_evidence_tier": static_tier,
                "final_evidence_tier": final_tier,
                "weak_reachability_candidate": "yes" if weak_candidate else "no",
                "runtime_importer_examples": "; ".join(runtime_importers[:6]),
                "test_importer_examples": "; ".join(test_importers[:6]),
                "route_examples": route_examples,
            }
        )

    return rows


def main() -> None:
    rows = _build_rows()
    if not rows:
        raise RuntimeError("No reachability rows generated.")

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    strong = sum(1 for row in rows if row["final_evidence_tier"] == "strong")
    weak = sum(1 for row in rows if row["weak_reachability_candidate"] == "yes")
    not_executed = sum(1 for row in rows if row["executed_in_tests"] == "no")
    print(f"Wrote {OUTPUT_CSV}")
    print(
        "Summary: "
        f"total={len(rows)} strong={strong} weak={weak} not_executed={not_executed}"
    )


if __name__ == "__main__":
    main()
