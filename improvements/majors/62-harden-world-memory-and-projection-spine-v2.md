# Harden world memory, fact graph, and projection spine (v2)

## Problem
A v2 iteration of the spine implemented by archived majors 52, 53, and 54 is needed to enforce stronger freeform action grounding and deterministic projection. This requires strict evaluation and playtesting to ensure narrative consistency and quality.

## Proposed Solution
Create a v2 of the world memory, fact graph identities/relationships, deterministic world projection, and freeform action grounding spine.
- Consolidate the foundational work from majors 52, 53, and 54 into a rigorous v2 implementation.
- Require strict narrative eval harness passes and playtest harnesses for acceptance.

## Files Affected
- src/models/*
- src/services/*
- tests/*

## Validation Commands
- `python -m pytest -q`
- `python scripts/dev.py` (or equivalent playtest/eval harness commands)

## Acceptance Criteria
- [ ] v2 of the world memory and projection spine logic is implemented.
- [ ] Strict narrative eval harness passes successfully.
- [ ] Playtest harnesses validate narrative quality and grounding.
- [ ] `python -m pytest -q` succeeds.
