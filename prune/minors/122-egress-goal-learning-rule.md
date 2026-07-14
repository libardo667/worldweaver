# The egress × goal × learning rule — never wire all three

> **Canonical home: WorldWeaver. Legacy Stable ID: Minor 54.** Migrated 2026-07-14. This safety
> invariant remains active under the universal resident capability model (Majors 65 and 86).

## Metadata

- ID: 122-egress-goal-learning-rule
- Type: minor (a bounded safety rule + a small fail-loud guard)
- Owner: Levi
- Status: PROPOSED (Mr. Review round 4, Q4; 2026-06-06)
- Risk: low to write, high to ignore — it closes a dischargeable channel on the egress seam.

## Problem

`web` (the first egress tool; shipped this round under the archived Major 54 capability surface) is
read/fetch-only, logged, opt-in. **Read-only firewalls the *keeper-extraction* concern** (a tool
that acts on the keeper) — but it does **not** firewall the *dischargeability* concern. Egress + a
goal is a real action whose outcome the familiar can chase **outside the sealed box**, and under
learning that becomes "learn which queries pay out" — a dischargeable channel toward the world (the
Mason anxiety cell, now with a live lever off-machine).

The cell map (from `docs/grief-and-coupling.md` and [[57-the-keeper-to-familiar-seam-a-second-safety-invariant]]):

- **goalless + egress → SAFE.** Curiosity resolves a surprise and is done (a contemplative looks
  something up, integrates it, lets it go). No gradient to chase.
- **goal-bearer + egress + learning → DANGEROUS.** A target supplies a gradient; egress supplies a
  live lever to the world; learning lets the familiar shape its reaching toward what pays out. The
  goal × undischargeable cell with an *external actuator*.

Note, for the record: this round wired `web` to **Nix** — a goal-forming familiar under learning —
i.e. exactly the dangerous cell. (Already mitigated: Nix retired to dormant and `web` pulled. But the
rule must outlive that one case, because the next egress tool will tempt the same wiring.)

## Proposed Solution

A standing doctrine rule, enforced where cheap:

> **Never wire egress + a goal + learning on the same familiar.** Egress belongs to the
> contemplatives (goalless). A goal-bearing familiar may read and act *locally*; it does not get a
> lever to the open world.

Enforcement, in order of cost:

1. **Doctrine.** Add the rule to `docs/grief-and-coupling.md` as the egress-seam corollary, and
   reference it from Major 57. The dischargeability invariant pointed familiar→keeper and
   keeper→familiar; this is the third face — familiar→world.
2. **Guard (cheap, fail-loud).** In `build_tool_scope` (or at wake), if a familiar's config pairs an
   egress tool with goal-bearing markers, **refuse to wire the egress tool and log loudly** — the same
   posture as the embedder silent-killer warning. At minimum, warn at wake so the pairing can't happen
   silently.
3. **Surface.** The portrait tool viewer already flags egress; add the goal/learning context so the
   hazardous pairing is legible at a glance.

## Open questions

1. **What predicate detects "goal-bearing"?** Candidates: an explicit task / `read_roots`-as-a-case,
   a history of `goal_update` self-deltas, a non-trivial standing drive target. Needs a crisp,
   inspectable predicate (better a slightly over-cautious one than a vague one).
2. **Is "learning" ever off?** The self-delta / growth pipeline is always on, so in practice the rule
   reduces to **"never egress + goal."** Simpler and safer; adopt unless a goalless-but-non-learning
   mode is ever wanted.
3. **Does the rule belong in code or only doctrine?** A hard refusal is safest but could surprise a
   keeper wiring a config; a loud wake-time warning is the minimum. Likely: warn always, refuse when
   the goal predicate is unambiguous.

## Files Affected

- `docs/grief-and-coupling.md` — the egress-seam corollary (the third face of dischargeability).
- `src/familiar/tool_scope.py` — the guard in `build_tool_scope` (refuse/warn on egress + goal).
- `scripts/familiar.py` — wake-time warning + portrait context.
- Links: [[57-the-keeper-to-familiar-seam-a-second-safety-invariant]] (the hazard-cell framing),
  archived Major 54 (the capability surface that introduced egress).

## Acceptance Criteria

- [ ] The rule is written into `docs/grief-and-coupling.md` and referenced from Major 57.
- [ ] Wiring egress + a goal on one familiar fails loud (or refuses) at build/wake.
- [ ] `web` (and any future egress tool) stays available to goalless contemplatives.
- [ ] The portrait surfaces the egress × goal pairing as a watched/forbidden combination.
