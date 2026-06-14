# Stage agent intents before execution and require focused confirmation

## Problem

Agent decision-making is currently inconsistent across loops. Some behaviors follow
the intended multi-step shape of "detect intent, route it to the owning loop, ask
for specifics, then execute," while others still execute directly from brittle
regexes or one-shot classifier output.

Concrete problems visible in the current runtime:

- `ww_agent/src/runtime/rest.py` still turns reflective prose into rest state through
  keyword matching over reflection and subconscious text. Atmospheric language like
  "quiet" or "stillness" can be misread as a decision to sleep or withdraw.
- `ww_agent/src/loops/fast.py` mostly executes directly from a single classifier slug:
  `move:`, `chat:`, `city:`, and `react:` route immediately into execution logic
  rather than staging a structured intent and confirming specifics.
- `ww_agent/src/loops/slow.py` has bespoke deterministic extraction for mail contact
  and identity shift, but those extractors are not part of a general intent-routing
  system.
- `ww_agent/src/loops/mail.py` is the closest thing to the intended architecture:
  the slow loop stages a letter intent, the mail loop re-asks a focused question,
  and only then is a letter sent or discarded. That pattern has not been generalized.
- As a result, the runtime does not have one durable "decision shape." Some actions
  are reflective and confirmed, some are reflexive and direct, and some are just
  regex-triggered.

This is now an architecture problem. As the agent runtime becomes more capable,
direct execution from raw prose or a one-line slug becomes less trustworthy and
harder to reason about. Intent extraction, routing, and confirmation should be the
default shape for nontrivial behavior.

## Proposed Solution

Introduce a first-class staged-intent architecture for resident runtime decisions.

The standard shape should be:

1. Extract a candidate intent from reflection, subconscious reading, scene context,
   or classifier output.
2. Persist that intent as structured staged state.
3. Route it to the loop that owns that capability.
4. Ask a focused follow-up question to resolve confirmation and specifics.
5. Execute only after the follow-up produces a usable decision.

This should become the canonical runtime pattern for nontrivial actions, with mail
used as the reference example and rest migrated first.

### Phase 1 - Introduce a generic staged-intent primitive

- Add a small, structured staged-intent format that can live under resident-local
  runtime state or files.
- Each staged intent should include fields like:
  - `intent_type`
  - `source_loop`
  - `created_at`
  - `status`
  - `summary`
  - `context`
  - `confirmation_needed`
  - `expires_at`
- Support at least these lifecycle states:
  - `pending`
  - `confirmed`
  - `cancelled`
  - `expired`
  - `executed`
- Keep the format generic enough that multiple loops can stage and consume intents
  without inventing loop-specific mini protocols each time.

### Phase 2 - Migrate rest to staged intent + confirmation

- Remove regex-driven direct rest triggering from `ww_agent/src/runtime/rest.py`.
- Have the slow loop extract only explicit rest intention from subconscious output,
  such as:
  - wanting to sleep
  - needing to rest
  - deciding to step away
  - choosing to take a break
- Stage a `rest` intent instead of directly mutating rest state.
- Route the `rest` intent to the fast loop, which should ask a focused follow-up
  equivalent to:
  - are you taking a short break or actually going to sleep?
  - for how long?
  - here, or elsewhere?
- Only after that resolution should the runtime call into `RestState` to begin
  `resting`.
- Keep the existing confirmation-count and wake-grace protections, but make them
  apply to explicit rest intent rather than keyword echoes.

### Phase 3 - Normalize fast-loop decision handling

- Refactor `ww_agent/src/loops/fast.py` so the classifier no longer acts as a direct
  executor for every meaningful action.
- Keep genuinely reflexive no-cost outputs like `observe` as immediate.
- For nontrivial actions, stage and confirm:
  - `react`
  - `move`
  - `mail`
  - `rest`
  - optionally `city` broadcasts
- Use focused second-pass prompts to resolve specifics instead of relying on the
  classifier slug to carry all necessary intent detail.
- Make the fast loop an intent router/realizer rather than a thin dispatch table
  over one-line classifier strings.

### Phase 4 - Generalize deterministic extraction from the slow loop

- Replace bespoke ad hoc pattern matching in `ww_agent/src/loops/slow.py` with a
  clearer extractive pass that can emit multiple candidate intents, such as:
  - `mail_contact`
  - `rest`
  - `identity_note`
  - `research`
- Preserve deterministic safeguards where they are helpful, but make them operate
  over a common intent abstraction instead of separate handwritten side paths.
- Ensure the decision log captures:
  - extracted intents
  - routed loop
  - confirmation result
  - execution outcome

### Phase 5 - Visibility, expiry, and operator sanity

- Surface staged intents in operator diagnostics so it is obvious what an agent is
  currently considering versus what it has actually decided.
- Add expiry/garbage-collection rules so stale intents do not accumulate forever.
- Make it possible to inspect cases like:
  - "agent considered resting but did not confirm"
  - "agent wanted to write but declined at confirmation"
  - "agent staged movement but the route was invalid"

## Files Affected

- `ww_agent/src/loops/fast.py`
- `ww_agent/src/loops/slow.py`
- `ww_agent/src/loops/mail.py`
- `ww_agent/src/runtime/rest.py`
- `ww_agent/src/resident.py`
- `ww_agent/src/main.py`
- `ww_agent/src/identity/loader.py`
- `ww_agent/src/memory/`
- `ww_agent/tests/test_rest.py`
- `ww_agent/tests/`
- `worldweaver_engine/src/api/game/world.py`
- `worldweaver_engine/client/src/App.tsx`
- `worldweaver_engine/client/src/components/PresencePanel.tsx`
- `improvements/majors/23-rest-cycles-and-agent-dormancy.md`

## Acceptance Criteria

- [ ] The runtime has a reusable staged-intent format rather than loop-specific ad hoc files or regex side effects
- [ ] Rest no longer begins directly from generic words like `quiet` or `stillness` without an explicit rest intent
- [ ] A staged `rest` intent is extracted by the slow loop and resolved through a focused confirmation pass before rest begins
- [ ] The fast loop executes nontrivial actions through staged intent resolution rather than relying solely on one-line classifier slugs
- [ ] Mail remains supported under the new abstraction without regressing current send/decline behavior
- [ ] Decision logs clearly show extracted intents, confirmation outcomes, and final execution
- [ ] Staged intents can expire or be cancelled cleanly without leaving resident state stuck
- [ ] Operator diagnostics can distinguish "considered" actions from actually executed actions

## Risks & Rollback

- If the staging layer is overbuilt, the runtime may become slower and harder to
  debug than the direct-dispatch model. Keep the first abstraction small and use
  mail as the reference behavior.
- If too many actions are forced through confirmation, agents may feel hesitant or
  over-mediated. Preserve a fast path for trivial reflexes like `observe`.
- If rest migration is done without preserving wake-grace and confirmation rules,
  agents may become oscillatory again. Keep those guardrails and change only the
  source of intent.
- Rollback path: keep the initial staged-intent primitive additive, migrate rest
  behind a narrow code path first, and fall back to the current direct fast-loop
  routing if the abstraction proves too disruptive.
