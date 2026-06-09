"""Record/replay world clients for the pen-swap experiment.

Two subclasses of the real ``WorldWeaverClient`` that intercept the three HTTP
choke points every world call funnels through — ``_get``, ``_get_with_retry``,
``_post``:

- :class:`RecordingClient` — used during the LIVE KEEP run. Passes calls through
  to the real backend, and logs each (kind, path, params/payload, status, body)
  to a JSONL recording, tagged with the current tick.

- :class:`ReplayClient` — used during KEEP'/SWAP replay runs. Serves recorded
  responses for read calls (so the real ``perceive()`` runs unchanged on top and
  reproduces its substrate perturbations); captures-and-suppresses write calls
  (a swapped-pen resident's acts are recorded but must not mutate the fixed,
  recorded world). Reads with no recorded match are served an empty body and
  counted as ``misses`` — the telemetry of how far a swapped pen strays off the
  recorded world.

Why the HTTP layer: every read method parses its dataclass (``SceneData``,
``ChatMessage``, …) from ``resp.json()``. Replaying raw bodies lets the real,
unmodified client do that parsing — maximally faithful, and we never enumerate
the ~40 client methods.

Run from the ww_agent root (``from src...`` style), matching the other scripts.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.world.client import WorldWeaverClient  # noqa: E402


# --------------------------------------------------------------------------- #
# Recording format
# --------------------------------------------------------------------------- #
@dataclass
class CallRecord:
    """One recorded world-client HTTP call."""

    seq: int
    tick: int
    kind: str  # "read" | "write"
    method: str  # "GET" | "POST"
    path: str
    key: Any  # params (GET) or payload (POST)
    status: int
    body: Any  # parsed JSON body

    def to_json(self) -> str:
        return json.dumps(
            {
                "seq": self.seq,
                "tick": self.tick,
                "kind": self.kind,
                "method": self.method,
                "path": self.path,
                "key": self.key,
                "status": self.status,
                "body": self.body,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CallRecord":
        return cls(
            seq=int(d.get("seq", 0)),
            tick=int(d.get("tick", 0)),
            kind=str(d.get("kind", "read")),
            method=str(d.get("method", "GET")),
            path=str(d.get("path", "")),
            key=d.get("key"),
            status=int(d.get("status", 200)),
            body=d.get("body"),
        )


def _fake_response(method: str, path: str, status: int, body: Any) -> httpx.Response:
    """A response carrying a recorded body, parseable by the real client code."""
    return httpx.Response(
        status_code=status,
        json=body if body is not None else {},
        request=httpx.Request(method, f"http://replay.invalid{path}"),
    )


# --------------------------------------------------------------------------- #
# Recording client (live KEEP run)
# --------------------------------------------------------------------------- #
class RecordingClient(WorldWeaverClient):
    """Live client that tees every choke-point call into a JSONL recording."""

    def __init__(self, base_url: str, *, recording_path: str | Path, **kwargs: Any) -> None:
        super().__init__(base_url, **kwargs)
        self._recording_path = Path(recording_path)
        self._recording_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self._recording_path.open("w", encoding="utf-8")
        self._seq = 0
        self._tick = 0

    def set_tick(self, tick: int) -> None:
        self._tick = int(tick)

    def _record(self, kind: str, method: str, path: str, key: Any, resp: httpx.Response) -> None:
        try:
            body = resp.json()
        except Exception:
            body = None
        rec = CallRecord(self._seq, self._tick, kind, method, path, key, resp.status_code, body)
        self._seq += 1
        self._fh.write(rec.to_json() + "\n")
        self._fh.flush()

    async def _get(self, path: str, *, params: dict | None = None, timeout: float = 30.0) -> httpx.Response:
        resp = await super()._get(path, params=params, timeout=timeout)
        self._record("read", "GET", path, params, resp)
        return resp

    async def _get_with_retry(self, path: str, *, params: dict | None = None, timeout: float = 30.0, max_retries: int = 2) -> httpx.Response:
        resp = await super()._get_with_retry(path, params=params, timeout=timeout, max_retries=max_retries)
        self._record("read", "GET", path, params, resp)
        return resp

    async def _post(self, path: str, payload: dict, *, timeout: float = 60.0) -> httpx.Response:
        resp = await super()._post(path, payload, timeout=timeout)
        self._record("write", "POST", path, payload, resp)
        return resp

    async def close(self) -> None:
        try:
            self._fh.close()
        finally:
            await super().close()


# --------------------------------------------------------------------------- #
# Replay client (KEEP' / SWAP runs)
# --------------------------------------------------------------------------- #
@dataclass
class CapturedWrite:
    tick: int
    path: str
    payload: Any


class ReplayClient(WorldWeaverClient):
    """Serves recorded reads; captures + suppresses writes.

    Reads are served per ``(method, path)`` FIFO in recorded order — the path
    already encodes session/location for the calls that matter (``/scene/{id}``,
    ``/location/{loc}/chat``), so order within a key is the faithful axis. A read
    with no remaining recorded match is served ``{}`` and counted in ``misses``.
    """

    def __init__(self, records: list[CallRecord], *, base_url: str = "http://replay.invalid", **kwargs: Any) -> None:
        super().__init__(base_url, **kwargs)
        self._read_queues: dict[tuple[str, str], deque[CallRecord]] = defaultdict(deque)
        self._write_responses: dict[tuple[str, str], deque[CallRecord]] = defaultdict(deque)
        for rec in records:
            key = (rec.method, rec.path)
            if rec.kind == "write":
                self._write_responses[key].append(rec)
            else:
                self._read_queues[key].append(rec)
        self.misses: list[tuple[str, str]] = []
        self.captured_writes: list[CapturedWrite] = []
        self._tick = 0

    def set_tick(self, tick: int) -> None:
        self._tick = int(tick)

    @classmethod
    def from_recording(cls, recording_path: str | Path, **kwargs: Any) -> "ReplayClient":
        records = [CallRecord.from_dict(json.loads(line)) for line in Path(recording_path).read_text(encoding="utf-8").splitlines() if line.strip()]
        return cls(records, **kwargs)

    def _serve_read(self, method: str, path: str) -> httpx.Response:
        q = self._read_queues.get((method, path))
        if q:
            rec = q.popleft()
            return _fake_response(method, path, rec.status, rec.body)
        self.misses.append((method, path))
        return _fake_response(method, path, 200, {})

    async def _get(self, path: str, *, params: dict | None = None, timeout: float = 30.0) -> httpx.Response:
        return self._serve_read("GET", path)

    async def _get_with_retry(self, path: str, *, params: dict | None = None, timeout: float = 30.0, max_retries: int = 2) -> httpx.Response:
        return self._serve_read("GET", path)

    async def _post(self, path: str, payload: dict, *, timeout: float = 60.0) -> httpx.Response:
        # Capture the swapped-pen resident's act; do NOT touch the (fixed) world.
        self.captured_writes.append(CapturedWrite(self._tick, path, payload))
        q = self._write_responses.get(("POST", path))
        if q:
            rec = q[0]  # peek: reuse a representative recorded shape, don't consume
            return _fake_response("POST", path, rec.status, rec.body)
        return _fake_response("POST", path, 200, {})

    async def close(self) -> None:
        await super().close()
