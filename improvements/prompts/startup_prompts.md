Yes, start with [00-ADOPTION_GUIDE.md](C:/Users/levib/PythonProjects/worldweaver/worldweaver/improvements/harness/00-ADOPTION_GUIDE.md), but don’t stop there.

Schema precedence rule:
- If repo-local MAJOR_SCHEMA.md / MINOR_SCHEMA.md exist, treat them as authoritative.
- Use harness templates only to fill optional metadata fields or when schema sections are missing.
- Do not invent required sections that conflict with local schema.

Use this sequence with an agent:

1. **Bootstrap pass (docs-only)**
2. **Pilot pass (one minor item)**
3. **Normal execution loop**

Use this first prompt (edited with what already exists here):

```text
Read:
- improvements/harness/README.md
- improvements/harness/00-ADOPTION_GUIDE.md
- improvements/harness/01-OPERATING_MODEL.md
- improvements/harness/03-AGENT_EXECUTION_PROTOCOL.md
- improvements/VISION.md
- improvements/ROADMAP.md
- improvements/majors/MAJOR_SCHEMA.md
- improvements/minors/MINOR_SCHEMA.md

Task:
- Do not change application code.
- Create improvements/HARNESS_BOOTSTRAP_CHECKLIST.md for THIS repo.
- Fill concrete command surface (backend run, client run, tests, build).
- Map quality gates to actual commands in this repo.
- Identify the first “pilot minor” to run through the harness.
```

If there are gaps in anything, send a prompt like this:
```text
Read:
- improvements/HARNESS_BOOTSTRAP_CHECKLIST.md
- improvements/harness/04-QUALITY_GATES.md
- improvements/ROADMAP.md
- improvements/majors/MAJOR_SCHEMA.md
- improvements/minors/MINOR_SCHEMA.md

Task (docs-only):
1) Classify each listed gap as:
   - blocker_now
   - non_blocker_defer
2) Create improvements/HARNESS_GAP_DECISIONS.md with:
   - gap
   - classification
   - rationale
   - owner
   - due window
   - unblock condition
3) For each blocker_now gap:
   - create a new minor improvement doc (schema-compliant)
   - add it to ROADMAP in execution order before the pilot item
4) For each non_blocker_defer gap:
   - record explicit temporary waiver + expiration trigger
5) Do not change application code.
```

Then this prompt (pilot execution):

```text
Using improvements/HARNESS_BOOTSTRAP_CHECKLIST.md, execute the selected pilot minor end-to-end via the harness protocol.
Use PR evidence format from improvements/harness/templates/PR_EVIDENCE_TEMPLATE.md.
Keep scope tight. No drive-by refactors.
```

Then ongoing prompt pattern per item:

```text
Execute <item-id> using improvements/harness/03-AGENT_EXECUTION_PROTOCOL.md and 04-QUALITY_GATES.md.
```

Practical tip: for day-to-day work, point agents to only 3-4 harness docs max (`03`, `04`, plus template), not the entire folder, to keep context focused.

For multi-agent pruning requests, see:
- `improvements/prompts/pruning_prompts.md`
