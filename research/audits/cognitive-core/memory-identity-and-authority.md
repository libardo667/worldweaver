# Memory, identity, and authority

Status: code audit and deterministic reproductions, 2026-07-19.

This pass asks four plain questions:

1. What information actually tells the model who this resident is?
2. Which changes are chosen, and which are silently imposed by the host?
3. What does the runtime call memory, and how does a memory reach a later prompt?
4. Does the same resident remain behaviorally the same when its hearth moves?

The current implementation has one strong boundary worth preserving: canonical soul text cannot be rewritten
by an ordinary pulse, and proposed growth requires a later private inspection and explicit adoption. Around
that boundary, however, several files and comments promise an identity system that the running code does not
actually use. Folder names alter behavior, a birth-time trait is ignored, selected memory has two authorities,
and host-authored deployment claims are presented as unchanging truth that the resident must not remember
against.

## What actually enters the model prompt

| Source | Who or what authors it | Live effect |
| --- | --- | --- |
| `SOUL.canonical.md` | steward, seed process, or imported hearth history | included directly in every system prompt and embedded into the optional drive vector |
| `soul_growth.md` | exact model-proposed text, but only after private inspection and an explicit hearth adoption action | appended to the system prompt and embedded into the optional drive vector |
| situational briefing | host/world adapter plus the renderer in `identity/loader.py` | appended as a `GROUND TRUTH (unchanging)` system block when the core is constructed |
| resident directory name | host filesystem layout or import target chosen by an operator | becomes runtime name and display name; affects session identity, one stock prompt example, and default circadian phase |
| `IDENTITY.md` vibe | seed process or steward | used in city session bootstrap metadata, but not as cognitive prompt identity |
| `IDENTITY.md` prose body (`core`) | seed process or steward | loaded into `ResidentIdentity.core`, then unused by production code |
| `IDENTITY.md` voice examples | seed process or steward | included only when the process-wide `WW_VOICE_REGISTER` flag is on; off by default |
| `IDENTITY.md` chronotype | seed process | written at birth, never parsed by `IdentityLoader`, and never used by the circadian runtime |
| `tuning.json` | seed process or steward | live consumers use model fallback, pulse temperature, anchor gating, and incubation; most loop-era fields have no consumer |
| kept memory | model output under a project-written memory policy | written automatically after a valid pulse and shown by recency or embedding relevance in later prompts |
| felt self-report | model output | not selected as a keepsake, but remains in the ledger, enters the elective recall source, and is mined for anchors |

This is a much smaller and stranger identity contract than the source comments describe. In particular,
`ResidentIdentity.core` says its prose is made of immutable facts injected into every prompt. It is not
injected anywhere. `IDENTITY.md` may look like the resident's main identity file to an operator while its body
has no cognitive effect.

## The same actor changes when its folder changes

`resident_id.txt` correctly supplies a durable `actor_id`. The portable hearth manifest also preserves that
ID and its runtime generation. But `IdentityLoader.load()` separately sets `name = resident_dir.name`.

That path-derived name is not cosmetic. It controls:

- the resident's display name and city bootstrap role;
- the slug used in new city session IDs;
- the default circadian chronotype through a SHA-256 hash;
- the stock worked example selected for every pulse through a SHA-1 hash;
- the human-readable name used in logs and operator reports.

The hearth package contains no stable display-name field. Its import function accepts any new target directory
name. Therefore the same actor can be imported under a different folder and wake with a different name,
day/night phase, and few-shot behavioral example.

A deterministic reproduction loaded identical identity files and the same `actor_id` from two differently
named temporary directories. The first loaded as `Same Resident`, received chronotype `-0.46`, and got the
worked example about leaving a close room. The second loaded as `Renamed Resident`, received chronotype
`1.03`, and got the example about recording an observation. Nothing resident-owned changed; only the host path
did.

This directly contradicts the identity package's stated rule not to derive identity from a filesystem path.
The actor ID remains stable, but live policy does not.

## The birth-time chronotype is decorative

The doula contains an explicit chronotype inference function. It classifies a new resident as `early`, `day`,
`night`, or `irregular` from their creation context and writes the result to `IDENTITY.md`.

The live circadian code does not read it. It calls `chronotype(identity)`, whose identity key is
`identity.name`; that name came from the folder. `LoopTuning.rest_chronotype` is parsed from another possible
location but also has no production reader. The live value is a numeric hash in a fixed three-hour spread,
not the doula's categorical decision.

This creates three conflicting representations:

- a categorical chronotype written in `IDENTITY.md` and ignored;
- another categorical `rest.chronotype` compatibility field parsed from `tuning.json` and ignored;
- a numeric folder-name hash that actually changes wakefulness and rest pressure.

The code comment that a chronotype is a stable trait derived from identity is only true if a filesystem label
is accepted as identity. That is incompatible with portable hearths and with the actual durable actor ID.

## Most tuning controls are inert compatibility data

`LoopTuning` still exposes fast-loop, slow-loop, rest, wander, ground, mail, home, and landmark controls. A
production search finds only these live uses:

- `slow_model` or `fast_model` as the pulse model fallback;
- `fast_temperature` as pulse temperature;
- `anchor_gating`;
- `incubation_enabled`.

The rest, wander, ground, mail, context-window, cooldown, token, chronotype, home-location, and landmark tuning
fields do not schedule or configure current `CognitiveCore` behavior. The doula has already stopped writing
most removed-loop settings, but it still writes `home_location` and `first_landmark_target` to `tuning.json`
under a comment claiming they have an operational consumer. They do not.

Keeping old inputs readable can be a sensible migration policy. Presenting them as live controls is not. A
steward can edit these values, observe no effect, and reasonably draw the wrong conclusion about the runtime.

## `GROUND TRUTH` gives the host too much epistemic authority

When a core is constructed, its world adapter reports a set of situational flags. The renderer turns those
flags into prose and places them after the soul under this heading:

```text
GROUND TRUTH (unchanging)
```

The model is told that apparent contradictions belong to somebody else or are misunderstandings and that it
must not record a memory that overturns these claims.

Some lines are ordinary interface facts, such as the existence of movement, mail, or model-backed inference.
Others are broader claims that the implementation does not support:

- `inner_private` says internal feelings and predictions are not read by anyone, while the city runtime still
  mirrors private projections into shard session variables and exposes the raw variable route without the
  promised authorization boundary;
- `no_reward` expands the absence of an explicit scalar reward into “nothing here pushes you toward, or away
  from, any way of being,” despite extensive prompt instructions, thresholds, mode policies, permissions, and
  scheduler pressure;
- travel says nothing of the resident is left behind, although public traces and city history remain, some
  private diagnostics are excluded from a hearth package, and the complete transfer protocol is not yet a
  federated guarantee;
- `local_only` and egress language describes files and messages as staying on one machine even though the
  language-model call itself requires a provider boundary unless the configured model is genuinely local.

There is also a time problem. `situational_facts()` is called once in `CognitiveCore.__init__`. The rendered
briefing is then reused. A permission, route, recording policy, file scope, host mode, or other standing fact
can change while the core continues telling the model that the old value is unchanging ground truth.

The issue is not that a world may state real affordances. It is that mutable host configuration is granted
higher authority than later observation and memory. If the host statement is wrong or stale, the prompt tells
the resident to distrust contrary evidence and prevents the ordinary correction path.

## Identity growth has the clearest authority boundary

The growth path is comparatively careful:

1. A pulse may propose exact `soul_edit` text.
2. Routing stores it as a candidate; it does not rewrite canonical soul text.
3. The resident must later inspect that specific candidate through a private source.
4. A separate typed hearth action adopts that exact wording.
5. The ledger records proposal, inspection, and adoption provenance.
6. Canonical soul remains separate from mutable growth.

This is a useful resident-control pattern. It makes proposal, review, and commitment different events. It
also repairs an interrupted file write from ledger evidence.

Two qualifications matter:

- the live pulse route never supplies the existing semantic contradiction checker, so every structurally
  valid self change is accepted as a candidate;
- the checker is asynchronous while the current gate callback type is synchronous, so merely passing the
  method would not correctly wire it. More importantly, embedding similarity can measure topical alignment;
  it cannot establish logical contradiction or whether a change is “earned.”

The explicit later adoption boundary should survive. The unused similarity gate should not be described as a
constitutional safeguard until its purpose and limits are redesigned in plain terms.

## Kept memory is project-filtered model output

The pulse contract asks the language model which notes to keep. The runtime then persists valid returned notes
without a later adoption step. This is a functional form of resident selection, but it is still selection by
one model response under a narrow human-authored policy.

The policy allows only:

- a fact about the keeper or world; or
- a decision said to remain true tomorrow.

It forbids instructions, reminders, and passing feelings, and says most moments should keep nothing. That is
not a neutral memory interface. It privileges propositional fact and declared decision over episodic,
affective, procedural, bodily, uncertain, and unfinished forms of continuity. The code provides no evidence
that this is the right memory ontology for residents.

The felt-report ledger partly defeats that rule: elective `recall` can return recent felt reports even when
the resident did not keep them, and anchor extraction reads the last ten automatically. The result is an
unclear split between deliberate memory and automatically retained model self-description.

## Memory retrieval changes with provider configuration

Without an embedder, a prompt receives up to ten recent kept notes, displayed oldest to newest. With an
embedder, the runtime instead considers up to forty notes and selects at most eight whose cosine similarity to
the current prompt context is positive, using a fixed diversity term. If retrieval returns no hits, it falls
back to recency.

The same embedder also removes a new keepsake when its similarity to an existing note exceeds `0.78`.
Without an embedder, that semantic duplicate filter does not run.

This means switching provider, embedding model, credentials, or embedding availability changes both what the
resident can remember at a moment and what it is permitted to store. Those are cognitive-policy changes, not
merely performance optimizations. No run receipt currently makes that policy difference obvious enough for
behavioral comparison, and no evaluation establishes that positive cosine, forty candidates, eight results,
or `0.78` preserve useful continuity.

## The memory side file is a second authority, not an index

Every keepsake is written to both the append-only ledger and `kept_memory.jsonl`. On read, the runtime loads
the side file first, then copies ledger-only notes into it. It does not verify that side-file notes have a
corresponding ledger event.

A deterministic reproduction placed one well-formed note only in `kept_memory.jsonl` with an empty ledger.
`memories()` returned it as durable resident memory. Therefore a copied, edited, partially restored, or
corrupted side file can put a claim into later prompts without canonical ledger provenance.

The side store was built for an old rolling ledger cap. That cap is gone. The file should become a verified,
rebuildable projection or be removed after migration. Until then, “the ledger is the only state” and complete
memory provenance are false guarantees.

## What can be claimed today

WorldWeaver currently has:

- a durable actor identifier;
- human- or seed-authored canonical prompt identity;
- a careful proposal/inspection/adoption path for exact growth text;
- model-selected propositional keepsakes;
- optional semantic retrieval and duplicate filtering;
- a portable allowlist and local generation fence for moving a stopped hearth.

It does not yet have one coherent identity authority or one coherent memory authority. It does not preserve
all live behavior under a path-only hearth move, honor the chronotype it records at birth, refresh mutable
world facts, or justify calling host configuration unchanging ground truth.

## Repair requirements

1. Store a stable resident display name in resident-owned identity metadata and make folder names purely
   operational. Key any stable behavioral assignment to `actor_id` or an explicit resident-owned setting.
2. Choose one chronotype representation, give it a plain operational meaning, and either honor the chosen
   value or remove it. Do not infer one trait and silently run another.
3. Reduce `LoopTuning` to live controls plus a clearly isolated legacy parser. Report ignored legacy fields to
   an operator instead of implying that they still work.
4. Replace `GROUND TRUTH (unchanging)` with versioned, scoped capability facts. Distinguish durable identity,
   current host configuration, current world affordances, and philosophical uncertainty.
5. Refresh mutable capability facts or rebuild the core when their revision changes. Allow later evidence to
   correct a stale host claim.
6. Remove absolute privacy, no-pressure, no-egress, and nothing-left-behind language until the corresponding
   software boundary is both true and testable.
7. Preserve the explicit growth adoption lifecycle. Either remove the unused semantic gate or redesign it as
   a correctly typed, narrowly named relevance check; do not call cosine similarity contradiction detection.
8. Define memory categories and authority explicitly. Do not quietly equate all durable memory with factual
   propositions while automatically reusing unselected self-report elsewhere.
9. Derive selected memory from the append-only ledger. Any search index or side materialization must carry
   source event IDs and be disposable.
10. Record the effective embedding/retrieval policy with each run and compare recency, semantic retrieval,
    and no automatic recall using controlled seeded facts rather than preferred personality outcomes.

## Required tests before interpreting continuity

- Export and import one hearth under a different host path; assert that actor ID, display name, chronotype,
  prompt-example assignment, and effective cognitive flags do not change.
- Change a mutable world capability while a core is alive; assert that the next applicable prompt receives a
  new fact revision rather than stale “unchanging” prose.
- Show that every prompt memory has one canonical source event and that deleting a derived index changes no
  result after rebuild.
- Compare recency and semantic retrieval on deliberately seeded factual, episodic, affective, procedural, and
  uncertain memories.
- Ensure a resident can remember evidence that corrects an erroneous host briefing.
- Verify that growth cannot enter the system prompt without candidate, inspection, and adoption evidence.
- Verify that editing ignored compatibility tuning produces an explicit warning rather than silent no-op.
- Record provider/model/retrieval changes in run metadata before comparing resident behavior.

Until these hold, a stable actor ID proves continuity of identifier and ledger ownership, not continuity of
the live policy that shapes the resident.
