# Major Fix Schema

Each `.md` file in this folder describes a single **major** improvement — a change
that touches multiple files, introduces new subsystems, or significantly alters
existing behaviour. Major fixes are the kind of work that moves the project from
"backend prototype" to "playable vertical slice."

---

## File naming

```
MM-<slug>.md        (MM = two-digit sequence number, slug = kebab-case summary)
```

Example: `01-persist-full-session-state.md`

---

## Required sections

Every major fix file **must** contain the following sections in order.

### Title (H1)

A single sentence naming the fix.

### Problem

What is broken, missing, or incomplete today? Reference specific files and
line numbers where relevant.

### Proposed Solution

Concrete description of the changes. List every file that will be created or
modified and summarise what changes in each.

### Files Affected

Bulleted list of file paths that will be created or modified.

### Acceptance Criteria

Bulleted checklist (`- [ ]`) of observable outcomes that prove the fix is
complete. Each criterion should be independently verifiable.

### Risks & Rollback

What could go wrong, and how would you undo the change safely?

---

## Example skeleton

```markdown
# Persist full session state to database

## Problem
Only `state_manager.variables` is saved to the `session_vars` table.
Inventory, relationships, and environment are lost on server restart.

## Proposed Solution
...

## Files Affected
- src/database.py
- src/models/__init__.py
- src/api/game.py

## Acceptance Criteria
- [ ] Inventory survives server restart
- [ ] Relationships survive server restart
- [ ] Environment state survives server restart
- [ ] Existing sessions migrate without data loss

## Risks & Rollback
...
```
