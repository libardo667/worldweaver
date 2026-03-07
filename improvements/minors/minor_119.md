# Add `intent` Field to Choice Objects

## Metadata

- ID: 119-choice-intent-field
- Type: minor
- Owner: agent
- Status: backlog
- Risk: low
- Depends On: none (prerequisite for Major 112)

## Problem

Choice buttons carry only a display `label` and a raw `set` block — for example:

```json
{"label": "Descend into the cryptic archive", "set": {"location": "library_archive"}}
```

When Major 112 routes choice selections through the intent pipeline, the pipeline needs natural
language to extract semantic intent from — not a raw key/value dict. Without an `intent` field,
the pipeline has no prose to work with; it can only see that `location` is being set, not *why*
or *how* the player is acting.

Additionally, having an `intent` string gives the scene narrator richer context for generating
the consequence narration: "you slip past the velvet rope and descend the stairs" is far better
than reconstructing that prose from `{location: library_archive}`.

## Proposed Solution

Extend the JIT beat narrator prompt (and any other choice generation path) to emit an `intent`
field alongside `label` and `set` on each choice object. The `intent` is 1–2 sentences in
present-tense, second-person voice describing exactly what the player is committing to do.

Example output after this change:
```json
{
  "label": "Descend into the cryptic archive",
  "set": {"location": "library_archive", "sublocation": "lower_stacks"},
  "intent": "You slip past the velvet rope and descend the narrow stairs into the archive's
             restricted lower stacks, lamp held high."
}
```

The `intent` field is optional for backwards compatibility: consumers that don't need it can
ignore it. The schema accepts but does not require it until Major 112 is implemented.

## Files Affected

- `src/services/rules/schema.py` — add optional `intent: str | None = None` to `ChoiceOut`
- `src/services/turn_service.py` — JIT beat generation prompt; add `intent` to choice output
  instructions and parse it from the LLM response
- Any JIT beat template prompt files that define the choice JSON schema

## Acceptance Criteria

- [ ] Every choice object returned by the `/next` endpoint includes a non-empty `intent` field.
- [ ] Existing `label` and `set` fields are unchanged.
- [ ] `ChoiceOut` schema accepts `intent` as an optional field (no breaking change).
- [ ] `python scripts/dev.py quality-strict` passes.

## Validation Commands

- `python scripts/dev.py quality-strict`
- Manual: start a session, call `/next`, inspect response choices for `intent` field presence

## Pruning Prevention Controls

- Authoritative path: `src/services/turn_service.py` JIT beat generation; `src/services/rules/schema.py`
- Parallel path introduced: none
- Artifact output target: no generated artifacts
- Default-path impact: core_path (changes JIT beat LLM output schema and prompt)

## Risks and Rollback

- Risk: JIT beat LLM may omit `intent` field occasionally. Mitigation: default to `None`; Major
  112 falls back to `label` text if `intent` is absent.
- Rollback: Remove `intent` from `ChoiceOut` and JIT prompt; no state or DB schema changes.
