# Work-item relevance and completion audit — 2026-07-14

This is the durable disposition record for the 2026-07-14 sweep of every active WorldWeaver major and
minor, plus every active work item inherited from the legacy `the-stable` prune workspace. It compares
each item's acceptance criteria and stated status against the code, tests, current CognitiveCore, and the
accepted one-resident/many-worlds architecture.

The standard used here is substantive rather than clerical:

- an item moves to history when its acceptance work is present, when only an ordinary operational
  observation remains, or when a newer architecture makes the proposed implementation wrong;
- an item stays active when a meaningful acceptance slice remains, even if an earlier phase shipped;
- live-agent experiments and calibrations remain recorded but are classified as research-deferred, not
  allowed to masquerade as the architectural queue;
- a superseded item is archived with its failed or obsolete criteria intact. History records what was
  learned; it does not rewrite an abandoned design as success.

## Headline disposition

- **Archived in this sweep:** 15 majors and 7 minors.
- **Merged rather than duplicated:** legacy Stable Major 73 is preserved in full inside active Major 84.
- **Active after the sweep:** 46 majors and 16 minors.
- **Canonical work-item home:** WorldWeaver. The legacy Stable ledger is source history, not a second
  active planning authority.
- **Immediate architecture:** Major 69's event-spine/turn demolition is complete. Proceed with Major 85
  ledger durability, Major 66 relational events, then Majors 35/63/64/84/86 as ordered in the
  architectural plan.

## Active majors

| Major | Completion/relevance judgment |
|---|---|
| 18 | Open, later product/ops. Public deployment still depends on the observatory and front-door surfaces. |
| 20 | Open, foundational. Federation-wide `actor_id` is required before exclusive cross-world/cross-shard presence can settle. |
| 25 | Explicitly parked, still coherent. Keep only as a wake-triggered structural refactor; the current engine/agent HTTP boundary is useful. |
| 32 | Parked casting work; stale paths require re-baselining before use. It remains a doula concern, not current architecture execution. |
| 35 | Open but over-broad. Re-baseline to immutable resident events, reducer checkpoints, projections, and evidence-backed subjective claims. |
| 36 | Open, later. Viewport map/occupancy work should follow actor identity and travel contracts. |
| 37 | Open, later. Must implement one actor changing exclusive world attachment under Majors 20 and 86. |
| 39 | Open. Human thread/inbox work remains useful, but resident private delivery must coordinate with Major 72 rather than the deleted mail loop. |
| 43 | Open. The curiosity-first front door and frontend decomposition remain substantive product work. |
| 51 | Open research, deferred. The general local-pen/training ladder survives; the legacy Maker-pilot execution plan did not. |
| 55 | Partial. Sight and gifts shipped in the legacy host; the native keeper surface and universal-host reconciliation remain. |
| 56 | Open, high relevance. Belief provenance is the principled successor to immutable hand-listed canon. |
| 57 | Partial doctrine/guard. The keeper→resident seam remains relevant under optional hearth relationships. |
| 58 | Partial. Phase 1 shipped; behavioral-concordance correction and later growth/reverie phases remain. |
| 59 | Partial. Tool chaining shipped; felt chain consolidation and long-chain agentification guard remain. |
| 60 | Mechanism built, empirical criterion open. Keep as research-validation debt, not architectural work. |
| 62 | Proposed casting experiment, deferred until topology and plural salience are trustworthy. |
| 63 | Open, architectural priority. Physical/local speech transport remains the primary monoculture lever. |
| 64 | Open, architectural priority. Plural world salience is required before population learning is trustworthy. |
| 65 | In progress. Trace commons and one shared resident faculty (`measure`) shipped; most seed verbs and derived demand remain. |
| 66 | Partial. Initial edge schema landed; stable actor/location/perception/reply lineage remains. |
| 67 | Partial. Pure source gate exists in the legacy substrate; in-ignition capture and WorldWeaver commit integration remain. |
| 70 | Open, orthogonal. Spend accounting remains useful after event/ledger contracts settle. |
| 71 | Open product/observability surface. It depends on stable identity, ledger, and frontend contracts. |
| 72 | Open. Private peer correspondence must be a deliberate pulse act/percept with explicit visibility edges. |
| 73 | Deferred experiment. Pen-strength × substrate-richness is not part of the architecture queue. |
| 74 | Deferred/fundable research. Counterfactual societies remain valid but expensive and tooling-dependent. |
| 75 | Correctly parked. Scarcity is triple-gated by ethics, dischargeability mapping, and fork tooling. |
| 76 | Tooling built but still active as a maintenance boundary. It remains needed until Major 86 eliminates the runtime split rather than merely syncing it. |
| 77 | Original observation withdrawn; redesigned control remains valid research and stays deferred. |
| 78 | Publication backlog, no runtime impact. Retain as a deliberate later synthesis task. |
| 80 | Thesis graduated but compute-economics acceptance work remains open; retain outside the architecture queue. |
| 82 | Deferred research. It may test whether hearths preserve divergence but no longer decides whether hearths exist. |
| 83 | Partial. Several dead-surface slices shipped; loop removal, tooling relocation, full-stack smoke, and migration-baseline work remain. |
| 84 | Open and consolidated. It now owns both legible derived rest and the legacy Stable diagnosis of rest as withdrawal rather than a self-igniting drive. |
| 85 | In progress, immediate substrate priority. Cold append is unbounded/O(1) and short reducers use a guarded hot horizon; incremental projection checkpointing remains before total tick cost is flat. |
| 86 | Accepted architecture, in progress. Shared sources/recall/measure landed; universal hearth host, exclusivity, privacy, and travel remain. |
| 113 | Open, optional later resident role. The Witness is a consent-gated hearth configuration, not another runtime species. |
| 114 | Deferred, ethics-gated research. The dischargeability boundary map still has scientific value. |
| 115 | Deferred research. Counterfactual biography/mechanism lesions remain gated and costly. |
| 116 | Deferred research only. Product hearth↔city continuity belongs to Major 86; this item asks the later controlled world-share question. |
| 117 | Deferred research. Identity-carrier factorization remains a measurement program, not a hearth prerequisite. |
| 118 | Deferred, ethics-gated research. The confederate-world apparatus must not enter current runtime work. |
| 119 | Deferred bounded architecture/eval. Tiered pens have a clean non-casting seam but need identity/noise-floor evidence. |
| 120 | Deferred offline measurement. The local-vs-cloud metabolism study must first verify legacy metabolic fields are reconciled into WorldWeaver. |
| 121 | Partial. Legacy Phase 0 disorientation detection shipped; behavioral reckoning remains gated and unreconciled. |

## Active minors

| Minor | Completion/relevance judgment |
|---|---|
| 31 | Open developer-experience polish left after Major 22: flag naming, strict readiness, topology diagnostics. |
| 32 | Open but should fold into Major 63 if ephemeral sublocations become real child-location semantics. |
| 33 | Open, low-priority texture; reconsider under Major 64 rather than simulate another full population. |
| 37 | Open UI decomposition, deliberately after Major 43 settles the product surface. |
| 38 | Partial frontend decomposition; re-baseline against hooks/components already extracted. |
| 62 | Open research classifier; defer until the ledger records enough novelty/provenance to distinguish dark-room silence. |
| 63 | Open live calibration; explicitly deferred and not architectural implementation. |
| 120 | Open, read-only cost analysis. Useful grant evidence but not in the architecture queue. |
| 121 | Open, read-only legacy matched-window measurement; defer until/if the old data question matters. |
| 122 | Open safety invariant. Egress + goal + learning needs a fail-loud capability guard in the unified resident model. |
| 123 | Deferred experiment. A contingent whisperer is not current machinery work. |
| 124 | Parked product onboarding behind Majors 43, 55, and 86. |
| 125 | Open, bounded future curation/publication surface. |
| 126 | Open governance prerequisite. The harm-regime protocol must exist before any living harm arm is authorized. |
| 127 | Deferred writing/positioning, no runtime mutation. |
| 129 | Partial research. Zero-burn Arm A/B0 apparatus exists; any paid/live B1 remains separately gated. |

## Archived majors in this sweep

| Major | Why it moved |
|---|---|
| 15 | Audit resolved to Outcome C: keep `WorldProjection` as a reducer-produced materialized view; action/event/overlay tests prove it is load-bearing. |
| 22 | Shard-first boot, readiness diagnostics, API-base gating, observer/BYOK UX, and docs are present; remaining polish is Minor 31 and redesign is Major 43. |
| 40 | Superseded. Its engine-state-manager→behavior bridge is the wrong authority for the ledger-derived CognitiveCore. |
| 42 | Canonical/growth separation, composition, staging, constitution gate, neutral seeding, reset, and inspection are present; refinements live in 56/58/61. |
| 49 | Complete CognitiveCore foundation: typed pulse, ledger substrate, afterimage, surprise/ignition, drive, and loop-closure tests. |
| 50 | Viable core delivered; guild/public-apprenticeship remainder retired. Workshop/capability work now belongs to 43/55/65/86. |
| 52 | Superseded as a category. A familiar is a resident in its hearth; Major 86 owns the unified host. |
| 54 | ToolScope/local-MCP proof complete; generalized capabilities and egress safety moved to 65/86 and Minor 122. |
| 61 | All provenance-promotion criteria and tests complete. |
| 69 | Complete. Canonical event submission owns world writes; `/api/action` uses the lean action service; turn/storylet/world-bible compatibility and schema residue are removed. |
| 81 | All one-time documentation reconciliation criteria complete. |
| 112 | Legacy Stable Major 60 retired because its training corpus depended on the voided dishonest-prompt pilot; parent Major 51 survives. |
| 122 | Legacy Stable Major 74 complete precursor: continuous hearth↔city travel was built; Major 86 owns product integration. |
| 123 | Imported completed/voided honest-situational-grounding lineage needed to interpret Major 112 and current briefing code. |
| 124 | Imported completed pulse-honesty/recall-affordance lineage needed by Major 121. |

## Archived minors in this sweep

| Minor | Why it moved |
|---|---|
| 57 | Measurement implementation and tests complete; a new storm run is separate empirical work. |
| 58 | Negative result: soul-level quote-or-abstain made confabulation more authoritative; Major 67 supersedes it. |
| 59 | Unicode name-filter implementation/tests complete; a future cast-distribution run is empirical. |
| 61 | Root CI and public-hygiene gate implemented and locally validated; next remote scheduling is ordinary observation. |
| 64 | Cross-repo ownership problem eliminated by choosing WorldWeaver as the single canonical workspace. |
| 128 | Legacy Stable metabolic-mass instrumentation completed all criteria; reconciliation is owned by 76/86. |
| 130 | Honest WorldWeaver briefing port and drift-catcher tests complete. |

## Stable → WorldWeaver ID map

Shared lineage Majors 49–59 retain their numbers. Post-fork collisions were renumbered:

| Legacy Stable | WorldWeaver |
|---|---|
| Major 60 | archived Major 112 |
| Major 61 | Major 113 |
| Major 63 | Major 114 |
| Major 64 | Major 115 |
| Major 65 | Major 116 |
| Major 66 | Major 117 |
| Major 67 | Major 118 |
| Major 68 | Major 119 |
| Major 69 | Major 120 |
| Major 72 | Major 121 |
| Major 73 | merged into Major 84 |
| Major 74 | archived Major 122 |
| archived Stable Majors 70/71 | archived Majors 123/124 |
| Minor 47 | Minor 120 |
| Minor 50 | Minor 121 |
| Minor 54 | Minor 122 |
| Minor 55 | Minor 123 |
| Minor 57 | Minor 124 |
| Minor 58 | Minor 125 |
| Minor 59 | Minor 126 |
| Minor 60 | Minor 127 |
| Minor 63 | archived Minor 128 |
| Minor 64 | Minor 129 |
| Minor 65 | archived Minor 130 |

## Maintenance rule

New work items are created only in WorldWeaver. Legacy Stable code may remain a temporary implementation
source under Majors 76/86, but its `prune/` directory is not edited as an independent queue. When a migrated
item's implementation is reconciled, update the WorldWeaver item and archive it here; do not create a new
Stable-side successor.
