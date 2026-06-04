#!/usr/bin/env python3
"""Preview the whole stable of familiars in a browser, no Tauri toolchain needed.

Serves the ui/ folder and three endpoints over the familiar root (the dir holding
each familiar's home folder):
  GET  /roster            -> [{name, mood, awake, ...}] for every familiar found
  GET  /state?who=<name>  -> that familiar's live state.json
  POST /whisper?who=<name>-> appends {ts, text} to that familiar's whispers.jsonl

Run the familiars (scripts/familiar.py, or familiar/wake-all.sh) and this, then
open http://localhost:8777 and switch between them in the roster.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
UI = HERE / "ui"


def _familiars(root: Path) -> list[str]:
    if not root.exists():
        return []
    out = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and child.name != "portrait" and (child / "identity").is_dir():
            out.append(child.name)
    return out


def _roster(root: Path) -> list[dict]:
    now = datetime.now(timezone.utc)
    roster = []
    for name in _familiars(root):
        state_path = root / name / "state.json"
        entry = {"who": name, "name": name.replace("_", " ").title(), "mood": "asleep", "awake": False, "live": False}
        if state_path.exists():
            try:
                st = json.loads(state_path.read_text(encoding="utf-8"))
                age = (now - datetime.fromisoformat(st["ts"])).total_seconds() if st.get("ts") else 1e9
                entry.update(
                    {
                        "name": st.get("name") or entry["name"],
                        "mood": st.get("mood") or "—",
                        "awake": bool(st.get("awake")),
                        "arousal": float(st.get("arousal") or 0.0),
                        "wakefulness": float(st.get("wakefulness") or 1.0),
                        "local_time": st.get("local_time") or "",
                        "live": age < 150,
                    }
                )
            except (json.JSONDecodeError, OSError, ValueError):
                pass
        roster.append(entry)
    return roster


def make_handler(root: Path):
    def safe_home(who: str) -> Path | None:
        who = (who or "").strip()
        if not who or who in _familiars(root):
            return (root / who) if who else None
        return None

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body: bytes, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _who(self):
            q = parse_qs(urlparse(self.path).query)
            who = (q.get("who") or [""])[0]
            return safe_home(who) or (root / (_familiars(root)[0] if _familiars(root) else ""))

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/roster":
                self._send(200, json.dumps(_roster(root)).encode("utf-8"))
                return
            if path == "/state":
                sp = self._who() / "state.json"
                if sp.exists():
                    self._send(200, sp.read_bytes())
                else:
                    self._send(200, json.dumps({"name": "—", "mood": "asleep", "felt_sense": "(not yet woken)", "awake": False}).encode("utf-8"))
                return
            if path == "/artifact":
                # full text of one workshop artifact (e.g. the journal), so the rail's
                # last-excerpt isn't the only view. Name sanitized; confined to workshop/.
                q = parse_qs(urlparse(self.path).query)
                name = "".join(c for c in (q.get("name") or [""])[0] if c.isalnum() or c in "-_")
                wsdir = (self._who() / "workshop").resolve()
                f = (wsdir / f"{name}.md").resolve()
                if name and wsdir in f.parents and f.is_file():
                    self._send(200, f.read_bytes(), "text/plain; charset=utf-8")
                else:
                    self._send(404, b"not found", "text/plain")
                return
            rel = path.lstrip("/") or "index.html"
            target = (UI / rel).resolve()
            if UI in target.parents and target.is_file():
                ctype = "text/html" if target.suffix == ".html" else "text/css" if target.suffix == ".css" else "application/javascript" if target.suffix == ".js" else "application/octet-stream"
                self._send(200, target.read_bytes(), ctype)
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self):
            if urlparse(self.path).path != "/whisper":
                self._send(404, b"not found", "text/plain")
                return
            length = int(self.headers.get("Content-Length") or 0)
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
                text = str(payload.get("text") or "").strip()
            except (json.JSONDecodeError, ValueError):
                text = ""
            if text:
                line = json.dumps({"ts": datetime.now().astimezone().isoformat(), "text": text}, ensure_ascii=False)
                with (self._who() / "whispers.jsonl").open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            self._send(200, b'{"ok":true}')

    return Handler


def main() -> None:
    p = argparse.ArgumentParser(description="Browser preview for the stable of familiars.")
    p.add_argument("--root", default="..", help="dir holding the familiar home folders (default: familiar/)")
    p.add_argument("--port", type=int, default=8777)
    args = p.parse_args()
    root = (HERE / args.root).resolve() if not Path(args.root).is_absolute() else Path(args.root)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(root))
    fams = _familiars(root)
    print(f"· the stable at http://localhost:{args.port}  ·  familiars: {', '.join(fams) or '(none found)'}  (root: {root})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
