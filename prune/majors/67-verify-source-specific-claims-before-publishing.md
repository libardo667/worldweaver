# Verify source-specific claims before publishing them

## Status

`the-stable` contains a small, tested `source_gate.py` that compares quoted spans, file paths, dates, and
line references against the bytes read during one tool-use cycle. It was never wired into WorldWeaver.
WorldWeaver now has the better integration point: its information-source registry already returns structured
records with provenance.

## Problem

A resident or specialized research assistant may read files and then state an exact quotation, filename,
date, or line reference that was not present in what it actually read. General expressive residents should
not be forced through a citation checker, but an explicitly source-reporting action needs a mechanical
grounding rule.

## Build next

1. Port the pure gate and its tests from `the-stable` into the WorldWeaver runtime.
2. Capture the exact bounded bytes and source pointers returned during one information request.
3. Define an explicit `source_report` or equivalent action for work that claims to report from sources.
4. Before that action becomes durable or public, verify exact claims against the captured records.
5. Downgrade or remove unsupported specifics while retaining a clear “not verified” result.
6. Record the source record IDs, gate version, verified spans, and rejected spans in the private ledger.
7. Add offset-aware line verification rather than treating any line number as trustworthy.

## Boundaries

- This gate applies to deliberate source-reporting actions, not ordinary conversation or feeling.
- It is a mechanical check, not a second LLM call and not hidden chain-of-thought capture.
- A source-matching quotation proves that the bytes contained it, not that the source was true.
- Truncated reads cannot verify claims outside the captured range.
- Public reports may cite public sources; private file paths and contents remain private unless separately
  authorized for publication.

## Acceptance criteria

- [ ] The tested pure gate from `the-stable` is ported and attributed in WorldWeaver.
- [ ] Information reads retain exact bounded bytes, source pointers, truncation state, and stable record IDs.
- [ ] Unsupported quotations, paths, dates, and line references cannot survive as verified source claims.
- [ ] Verified claims retain a durable link to the records that supported them.
- [ ] Ordinary resident speech and action selection are unchanged.
- [ ] No additional LLM call or private reasoning trace is required.
