#!/usr/bin/env python3
"""Familiar-wide pulse: drop the same whisper into every familiar's whispers.jsonl
at once, so the whole stable gets identical input at the same moment.

Why: ad-hoc chatter with one familiar but not another is a confound — differences
between them become partly *your attention*, not their nature. A uniform pulse keeps
the whisper log balanced across residents (clean comparative data) and gives you a
shared event to watch each one refract in its own register.

  # one pulse, now, to all:
  python scripts/pulse_familiars.py "the afternoon light is thinning."

  # every hour, rotating through gentle prompts (Ctrl-C to stop):
  python scripts/pulse_familiars.py --loop 3600 --prompts familiar/pulses.txt

  # a subset, or a different root:
  python scripts/pulse_familiars.py --who cinder,wren "just you two…"
  python scripts/pulse_familiars.py --root familiar "…"

--loop INTERVAL repeats every INTERVAL seconds; with --prompts it rotates through the
file's non-empty lines (one per pulse), wrapping around. A pulse force-ignites each
familiar — it WILL turn and attend — so keep them sparse and gentle; the point is
ambient shared weather, not a interrogation. Rotating prompts avoid habituation
(drop the identical line every hour and the substrate tunes it out fast).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parent / "familiar"


def familiars(root: Path, only: set[str] | None) -> list[Path]:
    out = []
    for child in sorted(root.iterdir()) if root.is_dir() else []:
        if child.name == "portrait" or not (child / "identity").is_dir():
            continue
        if only and child.name not in only:
            continue
        out.append(child)
    return out


def drop(home: Path, text: str) -> None:
    line = json.dumps(
        {"ts": datetime.now().astimezone().isoformat(), "text": text},
        ensure_ascii=False,
    )
    with (home / "whispers.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def pulse(homes: list[Path], text: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    for home in homes:
        drop(home, text)
    print(f"· [{stamp}] pulsed {len(homes)} familiars: {text!r}")


def load_prompts(path: Path) -> list[str]:
    return [
        ln.strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description="Drop a familiar-wide whisper pulse.")
    ap.add_argument(
        "message",
        nargs="?",
        default="",
        help="the whisper text (omit if using --prompts)",
    )
    ap.add_argument(
        "--root", default=str(DEFAULT_ROOT), help="dir holding the familiar homes"
    )
    ap.add_argument("--who", default="", help="comma-separated subset (default: all)")
    ap.add_argument(
        "--loop", type=float, default=0.0, help="repeat every N seconds (0 = one-shot)"
    )
    ap.add_argument(
        "--prompts", default="", help="file of prompts to rotate through (one per line)"
    )
    args = ap.parse_args()

    root = Path(args.root).resolve()
    only = {w.strip() for w in args.who.split(",") if w.strip()} or None
    homes = familiars(root, only)
    if not homes:
        print(f"no familiars under {root}", file=sys.stderr)
        sys.exit(1)

    prompts = (
        load_prompts(Path(args.prompts))
        if args.prompts
        else ([args.message] if args.message else [])
    )
    if not prompts:
        print("nothing to send — give a message or --prompts file", file=sys.stderr)
        sys.exit(1)

    if not args.loop:
        pulse(homes, prompts[0])
        return

    print(
        f"· pulsing {len(homes)} familiars every {args.loop:g}s, rotating {len(prompts)} prompt(s). Ctrl-C to stop."
    )
    i = 0
    try:
        while True:
            pulse(homes, prompts[i % len(prompts)])
            i += 1
            time.sleep(args.loop)
    except KeyboardInterrupt:
        print("\n· stopped.")


if __name__ == "__main__":
    main()
