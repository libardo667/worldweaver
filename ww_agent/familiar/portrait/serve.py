#!/usr/bin/env python3
"""Preview Cinder's portrait in a browser, no Tauri toolchain required.

Serves the ui/ folder and bridges two endpoints to the familiar's home dir:
  GET  /state    -> the live state.json
  POST /whisper  -> appends {ts, text} to whispers.jsonl

Run the familiar in one terminal (scripts/familiar.py), this in another:

    ../../worldweaver_engine/.venv/bin/python serve.py --home ../cinder
    # then open http://localhost:8777

The Tauri build (src-tauri/) uses native commands instead; this is the quick,
dependency-free way to see her.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
UI = HERE / "ui"


def make_handler(home: Path):
    state_path = home / "state.json"
    whispers_path = home / "whispers.jsonl"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _send(self, code, body: bytes, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.split("?")[0] == "/state":
                if state_path.exists():
                    self._send(200, state_path.read_bytes())
                else:
                    self._send(200, json.dumps({"name": "Cinder", "mood": "asleep", "felt_sense": "(not yet woken — run scripts/familiar.py)", "awake": False}).encode("utf-8"))
                return
            # static UI
            rel = self.path.split("?")[0].lstrip("/") or "index.html"
            target = (UI / rel).resolve()
            if UI in target.parents and target.is_file():
                ctype = "text/html" if target.suffix == ".html" else "text/css" if target.suffix == ".css" else "application/javascript" if target.suffix == ".js" else "application/octet-stream"
                self._send(200, target.read_bytes(), ctype)
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self):
            if self.path.split("?")[0] != "/whisper":
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
                with whispers_path.open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            self._send(200, b'{"ok":true}')

    return Handler


def main() -> None:
    p = argparse.ArgumentParser(description="Browser preview for Cinder's portrait.")
    p.add_argument("--home", default="../cinder", help="the familiar's home dir (holds state.json, whispers.jsonl)")
    p.add_argument("--port", type=int, default=8777)
    args = p.parse_args()
    home = (HERE / args.home).resolve() if not Path(args.home).is_absolute() else Path(args.home)
    home.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(home))
    print(f"· Cinder's portrait at http://localhost:{args.port}  (home: {home})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
