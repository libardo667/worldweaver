# Minor Fix Schema

Each `.md` file in this folder describes a single **minor** improvement — a
focused change that is typically confined to one or two files. Minor fixes
harden the codebase, remove rough edges, and improve reliability without
introducing new subsystems.

---

## File naming

```
MM-<slug>.md        (MM = two-digit sequence number, slug = kebab-case summary)
```

Example: `01-replace-bare-excepts.md`

---

## Required sections

Every minor fix file **must** contain the following sections in order.

### Title (H1)

A single sentence naming the fix.

### Problem

What is broken or suboptimal today? Reference specific files and line numbers.

### Proposed Fix

Concrete description of the change. Keep it short — a minor fix should be
explainable in a few sentences.

### Files Affected

Bulleted list of file paths that will be modified.

### Acceptance Criteria

Bulleted checklist (`- [ ]`) of observable outcomes. One to three items is
typical for a minor fix.

---

## Example skeleton

```markdown
# Replace bare except clauses in game.py

## Problem
`src/api/game.py` line 317 uses `except: pass`, silently swallowing all
errors including JSON parsing failures in spatial navigation.

## Proposed Fix
...

## Files Affected
- src/api/game.py

## Acceptance Criteria
- [ ] No bare `except:` clauses remain in game.py
- [ ] Errors are logged with context
```
