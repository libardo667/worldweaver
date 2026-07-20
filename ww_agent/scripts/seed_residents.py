#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Plan or create a small, dormant cohort without starting resident processes."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.inference.client import InferenceClient  # noqa: E402
from src.runtime.doula import DoulaLoop, _VOCATION_DOMAINS  # noqa: E402
from src.runtime.ledger import load_runtime_events  # noqa: E402
from src.world.client import WorldWeaverClient  # noqa: E402

_BASELINE_VOCATIONS = tuple(
    domain
    for domain in _VOCATION_DOMAINS
    if domain.startswith(
        (
            "food and drink",
            "care work",
            "the arts",
            "hair and body",
            "teaching and tutoring",
            "animals and green things",
            "night work",
        )
    )
)


def choose_vocations(*, count: int, seed: int) -> list[str]:
    """Choose distinct, ordinary work domains for a small baseline cohort."""
    if count > len(_BASELINE_VOCATIONS):
        raise ValueError("count exceeds the baseline vocation deck")
    return random.Random(seed).sample(list(_BASELINE_VOCATIONS), count)


def choose_locations(
    vitality: dict[str, dict],
    *,
    count: int,
    explicit: list[str],
) -> list[str]:
    if explicit:
        cleaned = list(
            dict.fromkeys(value.strip() for value in explicit if value.strip())
        )
        if len(cleaned) != count:
            raise ValueError("provide exactly one distinct --location per resident")
        return cleaned

    ranked: list[tuple[int, float, str]] = []
    for payload in vitality.values():
        if not isinstance(payload, dict):
            continue
        name = str(payload.get("name") or "").strip()
        if not name:
            continue
        try:
            agents = int(
                payload.get("total_agents") or payload.get("current_agents") or 0
            )
        except (TypeError, ValueError):
            agents = 0
        try:
            score = float(payload.get("vitality_score") or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        ranked.append((agents, score, name))
    locations = [
        item[2] for item in sorted(ranked, key=lambda item: (item[0], item[1], item[2]))
    ]
    locations = list(dict.fromkeys(locations))
    if len(locations) < count:
        raise ValueError(f"the city exposed only {len(locations)} usable neighborhoods")
    return locations[:count]


def _resident_summary(home: Path) -> tuple[str, str]:
    identity = (home / "identity" / "IDENTITY.md").read_text(encoding="utf-8")
    name = next(
        (
            line.removeprefix("# ").strip()
            for line in identity.splitlines()
            if line.startswith("# ")
        ),
        home.name,
    )
    events = load_runtime_events(home / "memory")
    seeded = next(event for event in events if event["event_type"] == "resident_seeded")
    vocation = str(seeded["payload"]["dealt_hand"]["livelihood_domain"])
    return name, vocation


async def run(args: argparse.Namespace) -> int:
    residents_dir = args.residents_dir.resolve()
    if not residents_dir.is_dir():
        print(f"Residents directory not found: {residents_dir}", file=sys.stderr)
        return 2

    world = WorldWeaverClient(args.server_url)
    llm: InferenceClient | None = None
    try:
        try:
            vitality = await world.get_neighborhood_vitality()
            locations = choose_locations(
                vitality,
                count=args.count,
                explicit=args.location,
            )
        except Exception as exc:
            print(f"Could not make a creation plan: {exc}", file=sys.stderr)
            return 1

        vocations = choose_vocations(count=args.count, seed=args.seed)
        print("Fresh resident plan")
        print(f"  count: {args.count}")
        print(f"  destination: {residents_dir}")
        print("  context: dealt hand plus bare home location; no city-history lookup")
        print(
            "  startup: dormant hearth manifests; no city sessions or resident processes"
        )
        for index, (location, vocation) in enumerate(
            zip(locations, vocations), start=1
        ):
            print(f"  {index}. {location} — {vocation}")

        if not args.apply:
            print("Dry run only. Add --apply to create this cohort.")
            return 0

        inference_url = str(os.environ.get("WW_INFERENCE_URL") or "").strip()
        inference_key = str(os.environ.get("WW_INFERENCE_KEY") or "").strip()
        inference_model = str(
            os.environ.get("WW_DOULA_MODEL")
            or os.environ.get("WW_INFERENCE_MODEL")
            or ""
        ).strip()
        if not inference_url or not inference_key or not inference_model:
            print(
                "WW_INFERENCE_URL, WW_INFERENCE_KEY, and a configured inference model are required.",
                file=sys.stderr,
            )
            return 2

        random.seed(args.seed)
        llm = InferenceClient(
            base_url=inference_url,
            api_key=inference_key,
            default_model=inference_model,
            timeout=float(os.environ.get("WW_INFERENCE_TIMEOUT", "200")),
        )
        doula = DoulaLoop(
            ww_client=world,
            llm=llm,
            residents_dir=residents_dir,
            spawn_queue=asyncio.Queue(),
            tethered_names=set(),
            known_session_ids=[],
            max_spawns_per_day=args.count,
            soul_model=inference_model,
            creation_mode="fixed_dormant_batch",
        )

        created: list[Path] = []
        for location, vocation in zip(locations, vocations):
            before = {
                path
                for path in residents_dir.iterdir()
                if path.is_dir() and not path.name.startswith((".", "_"))
            }
            success = await doula._seed_founding_resident(
                location,
                [f"This person lives around {location}."],
                vocation_domain=vocation,
                dormant=True,
                hand_only_context=True,
            )
            after = {
                path
                for path in residents_dir.iterdir()
                if path.is_dir() and not path.name.startswith((".", "_"))
            }
            added = sorted(after - before)
            if not success or len(added) != 1:
                print(
                    f"Creation stopped after {len(created)} residents; {location} did not produce exactly one home.",
                    file=sys.stderr,
                )
                return 1
            created.append(added[0])

        print("Created dormant residents:")
        for home in created:
            name, vocation = _resident_summary(home)
            print(f"  {home.name}: {name} — {vocation}")
        print("Nobody was activated or woken.")
        return 0
    finally:
        if llm is not None:
            await llm.close()
        await world.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--residents-dir", type=Path, required=True)
    parser.add_argument("--server-url", required=True)
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument(
        "--seed", type=int, default=0, help="repeatable deal and vocation selection"
    )
    parser.add_argument("--location", action="append", default=[])
    parser.add_argument(
        "--apply", action="store_true", help="create homes; omitted means dry-run"
    )
    args = parser.parse_args()
    if not 1 <= args.count <= 5:
        parser.error("--count must be between 1 and 5")
    return args


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
