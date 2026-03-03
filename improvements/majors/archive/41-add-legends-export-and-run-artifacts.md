# Add exportable run artifacts and a shareable legends bundle

## Problem
WorldWeaver’s DF-like cultural loop depends on shareability: players should be able to export and share what happened. Today, the system has world history and state, but no cohesive artifact format:
- no “run chronicle” export,
- no pinned thread bundle,
- no stable, versioned export schema.

## Proposed Solution
Implement exportable artifacts in the client (v1), with an optional server-side bundling endpoint (v2).

Client v1:
1. Add an “Export” action in Reflect mode that produces:
   - `run.json` containing:
     - session id,
     - current vars snapshot,
     - recent world history,
     - pinned items,
     - client version + export schema version.
   - `chronicle.md` containing a readable story summary (timeline + key turning points).
2. Provide “Copy share text” that generates a short teaser paragraph (no raw JSON).

Optional server v2 (additive endpoint):
- `GET /api/world/export/{session_id}` returns a structured export bundle for clients that prefer server-side composition.

## Files Affected
- client/src/utils/exportRun.ts (new or extend)
- client/src/views/ReflectView.tsx (modify: export controls)
- client/src/components/ExportPanel.tsx (new)
- (Optional) src/api/world_export.py (new)
- (Optional) main.py (include router)
- (Optional) tests/api/test_world_export_endpoint.py (new)

## Acceptance Criteria
- [x] Player can export `run.json` and `chronicle.md` from the client for the active session.
- [x] Export includes explicit schema versioning fields.
- [x] Export includes pinned items and recent history at minimum.
- [x] Export does not leak raw embeddings or private prompts.
- [x] Existing backend tests remain green (`pytest -q`).

## Risks & Rollback
Primary risks:
- Export format churn (solve with explicit versioning and minimal stable fields).
- Privacy leakage (avoid raw prompts and embeddings).
- Large histories causing big downloads (cap history and allow pagination later).

Rollback:
- Remove export UI and utility functions; optionally keep internal JSON bundling for debugging only. Backend unchanged unless v2 endpoint was added.
