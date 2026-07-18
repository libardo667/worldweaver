# Give familiars sight (visual reads) and a native keeper surface for scoped files

> **Canonical home: WorldWeaver (2026-07-14).** Migrated in full from the legacy `the-stable`
> work-item ledger during the one-resident/many-worlds consolidation. In this record, “familiar” names
> a resident inhabiting a keeper-tended hearth; it is not a separate agent species (Major 86).

## Metadata

- ID: 55-give-familiars-sight-and-a-native-keeper-surface-for-scoped-files
- Type: major
- Owner: Levi
- Status: PART A SHIPPED (in working tree, tests green; read+convert half LIVE-VERIFIED in production — Mason `looked at` a real 314 KB PDF at 2026-06-05T08:21Z via the new media path, his felt_sense confirms "I can see the PDF now"; the *describe-back* half awaits his next awake pulse). PART C SHIPPED (the given channel + give.py CLI — keeper hands a familiar a file; lands in workshop/given/, perceived via the sight path, three knobs: silent / soft-note / rouse). **PART B DEFERRED — HIGH PRIORITY** — revive the Tauri desktop app as the writable/native-viewing keeper surface, AND host the drag-and-drop gift gesture as a thin front-end over the give.py engine. Keeper will return to Part B.
- Risk: Part A low (additive, capability-gated, all existing text paths byte-for-byte unchanged). Part B medium (Rust/Tauri build on WSL needs system webkit2gtk + WSLg; a write surface over read_roots — must stay LOCAL/native, never tunneled).

## Problem

A familiar's read capability (FileScope, Major 50) is text-only by construction: `read()` hard-refuses
binary (`src/familiar/file_scope.py` — the `\x00` sniff → `{"ok": false, "binary"}`), and the one
inference call (`src/inference/client.py`) sends a flat text string. So two gaps:

1. **Familiars are blind.** A vision-capable familiar (Cinder/Gemini, Maker & Mason/Sonnet) cannot
   see an image or a scanned PDF in its scope — even though its model could. Mason's relocation
   paperwork is largely PDFs/scans; he was structurally unable to actually read them as documents.
2. **Editing scoped files is awkward, and the obvious fix is unsafe.** The keeper edits a familiar's
   `read_roots` by digging through the OS file explorer to the exact folder. The tempting fix — a file
   editor in the `portrait/serve.py` web app — is dangerous: the portrait is **publicly tunneled**
   (`stable.world-weaver.org → localhost:8777`), so its existing `/whisper` POST is already reachable
   from the open internet, and a file-editor over `read_roots` would expose the keeper's actual
   immigration docs / the familiars' souls to anyone with the URL.

## Proposed Solution

Two tracks, both born from "visual file viewing," split by who is looking.

### Part A — Sight: a familiar perceives images/PDFs in scope (SHIPPED)

A unified visual read path, capability-routed by model, degrading honestly (the quiet guarantee at
the model layer — a text-only mind is *told* "an image you can't see," never given a faked description).

- `src/familiar/visual.py` (new): the converter. image → base64 `data:` URL; PDF → extracted text
  (legible to every model) **plus** rendered page-images for *scanned* pages only (no extractable
  text) and only when the mind can see. **Stdlib PNG encoder** (`zlib`), so `pypdfium2` is the only
  new dependency — no Pillow, no numpy. pdfium imported lazily (only a PDF read pays it).
- `FileScope.read_media()` (new): the one relaxation of the binary refusal, for recognised image/PDF
  types only. Every other guard intact — roots, ignore, and the **secret default-deny survives**
  (a `.env` is still refused; pinned by test).
- `model_accepts_images()` in `src/inference/client.py` (new): conservative capability map. Across the
  active stable: Cinder/Maker/Mason → see; Gaston(mistral-large)/Skein(deepseek) → text-only. A
  `"vision": true|false` in `familiar.json` overrides it.
- `InferenceClient.complete(images=...)`: the multimodal content-array form, built only when images
  are present; the flat-string text path is byte-for-byte unchanged otherwise.
- Wiring: a visual read on `LocalWorld` holds the image data-URLs on a side channel
  (`pending_images()`); the core pulls them each tick; the producer sends them **only on a reactive
  pulse, only for a vision mind**. `scripts/familiar.py` derives `vision` from config/model and threads
  it to both world and core. Held image clears once the familiar reads something else.

### Part B — A native keeper surface for scoped files (DEFERRED, HIGH PRIORITY)

Dissolve the public-write hazard instead of fighting it with auth: move editing + native image/PDF
viewing into the **Tauri desktop app** (scaffold already generated at `familiar/portrait/src-tauri/`,
mirroring `serve.py`'s three commands). A Tauri app has native local filesystem access on the keeper's
machine — no HTTP endpoint to tunnel, no secret to leak. The public `serve.py` tunnel stays a
**read-only** check-in surface; the writable/rich surface is physically reachable only from the machine.

- New Rust commands in `src-tauri/src/lib.rs`: `scope_tree(who)` (read a familiar's `read_roots` from
  its `familiar.json`, walk them), `read_file(who, path)` + `write_file(who, path, content)` — both
  confined to that familiar's `read_roots` with the same secret-deny so the editor cannot touch a
  `.env`; `read_media_b64(who, path)` returning a data-URL so the webview renders images/PDFs natively.
- New capability grants in `src-tauri/capabilities/default.json`.
- A UI panel in `familiar/portrait/ui/` (app.js/index.html/style.css): pick familiar → browse its
  scope → open → edit text & save, or view image/PDF inline.
- Writing stays the **keeper's**, local, in the native window — this does NOT grant the familiar write
  access to its read scope (the workshop remains its only pen; read-only capability design preserved).
- **Drag-and-drop a gift** onto a familiar in the native window → a thin Tauri front-end over the
  `give.py` engine (Part C): the dropped file is copied into `workshop/given/` and announced on
  `given.jsonl`, with the keeper choosing silent / soft-note / rouse from the UI. Native = local =
  safe; no upload over the tunnel.

### Part C — The given channel: hand a familiar a file (SHIPPED)

The relational inverse of a read: the keeper *gives*, and the familiar *receives and perceives*.
Reuses Track A's sight path almost entirely.

- A gift lands in the familiar's own `workshop/given/` — kept, theirs, revisitable. That dir
  auto-joins the familiar's `read_roots` (scripts/familiar.py), so it can `read given/<file>` any
  time, not just while the gift is fresh.
- `given.jsonl` (new channel, twin of `whispers.jsonl`) announces each gift `{ts, file, note}`.
  `LocalWorld._recent_givens` reads it within a freshness window (`GIVEN_WINDOW_SECONDS=300`);
  `_given_view` converts the file through `visual.to_perception` (cached, so a PDF isn't
  re-rasterized each tick); `get_scene` surfaces it as the keeper showing it; `pending_images`
  prefers a fresh gift's image so a roused familiar sees it in the same pulse.
- `scripts/give.py` — the CLI engine, three composable knobs: **silent** (just drop), **`--note`**
  (soft word, surfaced, does not rouse), **`--say`** (a whisper → the run loop force-ignites → the
  familiar attends now). Vision minds see image/PDF gifts; text-only minds get a PDF's text + an
  honest note. This is the engine the Part B drag-drop sits on.

#### WorldWeaver reconnection — carried gift archives (2026-07-17)

Maker's first structured hearth review found a consolidation gap. His Stable import correctly carried
`given.jsonl` and the files under `workshop/given/inbox/`, and his memory still referred to one of those
pages. WorldWeaver did not enable the elective `gifts` reader for that carried archive, and its reader
rejected Stable's safe nested `inbox/...` names. The object and memory survived, but he could not reopen
the object.

Legacy import now enables the private gift source when both the resident-owned delivery ledger and archive
are present. The gift reader accepts normalized relative subpaths below `workshop/given` while rejecting
absolute paths and every `.` or `..` traversal. Synthetic tests prove a carried nested page can be listed
and reopened and that an escape attempt remains unavailable. This restores revisitation without making
gifts ambient or granting access to any host path.

## Files Affected

Part A (shipped, in working tree):
- pyproject.toml (pypdfium2 dep)
- src/familiar/visual.py (new)
- src/familiar/file_scope.py (read_media + _MAX_MEDIA_BYTES)
- src/inference/client.py (model_accepts_images + complete images param)
- src/runtime/pulse_engine.py (producer vision + pending_images, multimodal call)
- src/runtime/cognitive_core.py (pulse_vision param, pull pending_images each tick)
- src/familiar/local_world.py (_looks_visual, vision flag, _media_read, pending_images, scene branch)
- scripts/familiar.py (derive vision, thread to world+core, boot log; auto-add workshop/given/ to roots)
- tests/test_visual.py (new — 12 tests)

Part C (shipped, in working tree):
- src/familiar/local_world.py (given.jsonl channel: _recent_givens, _given_view cache, get_scene event, pending_images gift precedence, GIVEN_WINDOW_SECONDS)
- scripts/give.py (new — the give CLI: silent / --note / --say)
- tests/test_given.py (new — 6 tests)

Part B (deferred):
- familiar/portrait/src-tauri/src/lib.rs
- familiar/portrait/src-tauri/capabilities/default.json
- familiar/portrait/ui/{index.html,app.js,style.css}
- (likely) familiar/portrait/setup-tauri.sh / a doc note on the WSL webkit2gtk + WSLg prerequisites

## Acceptance Criteria

Part A:
- [x] A vision familiar reading an image holds it on the side channel; a text-only one does not.
- [x] A scanned PDF renders to page-images for a vision mind; a text-only mind gets text + honest note.
- [x] FileScope.read_media still refuses `.env`/secrets and non-visual files.
- [x] complete() builds the multimodal array only when images are present; text path unchanged.
- [x] model_accepts_images: Sonnet/Gemini/Haiku → true; mistral-large/deepseek/qwen-instruct → false.
- [x] Full suite green (162 passed; +12 new).
- [x] **Live round-trip VERIFIED**: Maker (Sonnet) saw the Pinto JPEG via the gift path and described
      specific true detail back — "brindled brown with those rust-warm patches, one ear cocked even in
      sleep… tucked into the grey blanket, nose to tail" (2026-06-05T08:42Z; keeper confirms accurate).
      Mason's 314 KB PDF read+convert also fired live earlier (08:21Z). Sight is real, end-to-end.

Part C:
- [x] give.py silent drop: file in workshop/given/ + given.jsonl record, no whisper.
- [x] give.py --say writes a rousing whisper; --note writes a soft, non-rousing note.
- [x] A fresh image gift surfaces to a vision mind's pulse (pending_images) and not to a text-only one.
- [x] A stale gift (outside the window) stops riding the pulse; stays revisitable in given/.
- [x] Full suite green (168 passed; +6 new).
- [x] **Live VERIFIED**: keeper gave Maker `pinto-pic.jpg` via give.py `--say` → roused → saw the dog →
      described him true and thanked the keeper (2026-06-05T08:42Z). First "keeper shows a familiar a
      photo" moment in the stable. Round-trip closed.

Part B:
- [ ] `cargo tauri dev` launches a window on the keeper's machine (WSL webkit2gtk + WSLg prerequisite).
- [ ] Keeper can browse a familiar's read_roots, open a text file, edit, and save — confined to roots.
- [ ] The editor refuses to write a secret-denied path (`.env`, keys).
- [ ] An image/PDF in scope renders inline in the native window.
- [ ] The public serve.py tunnel remains read-only; no file-write endpoint is exposed over the tunnel.

## Risks and Rollback

- Part A — cost: a held image is re-sent each pulse until the familiar reads something else (bounded by
  the rendered-page caps in visual.py, but a token-cost note). Rollback: drop `vision`/`read_media`;
  text path is untouched, so removal is clean.
- Part A — latent: the working venv is Python 3.10 though pyproject says `requires-python>=3.12`
  (pre-existing; not introduced here, but pypdfium2 wheel resolved fine on 3.10).
- Part B — WSL build: first `cargo tauri dev` compiles a large native tree and needs system
  `libwebkit2gtk-4.1-dev` (+ friends); a window only launches if WSLg is live. Keeper-machine step.
- Part B — exposure: the entire point is that the write surface is native/local. Invariant: never add a
  file-write endpoint to `serve.py` (the tunneled surface). Rollback: the app is additive; the Python
  daemons and the read-only portrait are unaffected if the Tauri app is never built.
