# Resident creation, casting, and consent

Status: code audit, deterministic path checks, and bounded evidence review, 2026-07-19.

This pass goes upstream of `CognitiveCore`. It asks what has already been decided about a resident before the
resident gets a first pulse. That matters because later behavioral variety cannot repair a population that was
created from one narrow template and then told that template is its permanent identity.

The current code has two creation routes:

- `ww_agent/scripts/seed_residents.py` lets a steward create a small dormant batch and requires `--apply`;
- `DoulaLoop` can watch a running city, fill low-population locations, turn names from world history into new
  residents, and boot them immediately.

The dormant route contains useful safety boundaries. The automatic route is not ready for a public shard. Its
consent path contradicts itself, its resident poll cannot complete through the current runtime, its population
logic is hidden behind biological prose, and its shared casting prompt directly assigns much of the behavior it
claims will emerge.

## What is decided before the first pulse

For a new founding resident, the host does the following:

1. Picks a home from city population statistics.
2. Randomly picks one U.S.-coded name tradition, age band, temperament, social disposition, upbringing, and
   livelihood category from process-wide Python tuples.
3. Calls a language model for a name.
4. Calls a language model for a two-to-four-paragraph canonical soul.
5. Calls the model again for a third-person identity paragraph.
6. Infers a chronotype from the creation context or another random draw.
7. Writes the result into a hearth, optionally boots it, and records some creation metadata.

Only the canonical soul has the advertised identity effect. It is placed in every later system prompt. The
third-person identity paragraph and inferred chronotype are currently ignored by the live cognitive runtime.
The three-model-call creation path therefore spends one call on a dead identity field, records a dead
chronotype decision, and gives the first two outputs very different apparent authority despite their common
author and model.

## The social disposition is assigned, not emergent

The comments say the resident's outward behavior “emerges” from unchosen starting conditions and that outcomes
are not assigned. The dealt hand actually includes one of these exact instructions:

- fill a silence and say the thing aloud;
- approach people and speak at a stoop;
- speak when there is a reason;
- hold back and often offer nothing; or
- remain private and perhaps never reveal an inner life.

That is a direct prescription of social behavior. Calling it a temper does not make the outcome unassigned.
The language model is then told to grow an unmistakable person from it, and the generated result becomes
canonical prompt identity.

The same is true, more softly, of the mandatory temperament list. New residents are born blunt, guarded,
formal, restless, shy, gregarious, anxious, or proud because the host says so. The architecture is not merely
allowing quiet and talkative people. It is manufacturing both from a cast deck, then describing that
manufacture as natural variation.

This helps explain why prior work treated visible sociability and quiet as properties to tune. The opinion is
already embedded in resident creation before `social_pull`, cadence, or a pulse prompt gets involved.

## The genetics language is scientifically wrong and ethically risky

The source comment groups heritage, body, temperament, social handling, and upbringing under “genetics and
origin.” The actual hand has no body field. It does have a cultural or racialized name tradition, a family
story, and a willingness-to-speak instruction.

Those are not one biological category. The U.S. National Human Genome Research Institute states that race and
ethnicity are social constructs, that they cannot be assigned consistently from biology, and that most human
genetic variation occurs within rather than between named groups. It also warns that careless population
descriptors have reinforced stereotypes and scientific racism. See [NHGRI's population-descriptor
guidance](https://www.genome.gov/about-genomics/policy-issues/population-descriptors-in-genomics).

Behavioral-genetics research does not rescue the implementation. Evidence for heritable variation is not
evidence of genetic determination, and longitudinal work requires both genetic and environmental mechanisms
to explain personality stability and change. See [Briley and Tucker-Drob's
meta-analysis](https://doi.org/10.1037/a0037091) and [McGue and Bouchard's
review](https://doi.org/10.1146/annurev.neuro.21.1.1).

There is also a model-specific risk. Prompting an LLM to write a persona from an explicit demographic label is
a measured route for stereotypes, othering, and essentializing description to enter generated text. Cheng,
Durmus, and Jurafsky found higher rates of racial stereotypes in GPT-generated personas than in matched human
portrayals and specifically warn about downstream story generation. See [Marked
Personas](https://arxiv.org/abs/2305.18189).

This does not mean culture, family, work, age, or temperament must disappear from fictional people. It means
they should not be bundled as genetic destiny, sampled as globally valid identity categories, and fed to a
model without an explicit stereotype evaluation and a resident-facing revision boundary.

## Every city currently draws from one American casting deck

The name traditions include labels such as Black American, Irish-American, Chicano, and European-American.
The upbringing list assumes a country with immigrants who may not speak “the language.” The work list includes
longshoremen, crossing guards, postal carriers, and other details suited to one contemporary U.S. urban
setting.

Those tuples live in the agent runtime, not in a city pack. The same list is used for Alderbank, Portland,
a Riverwood-like settlement, and any future federated city. A city contributes a location name and sometimes a
nearby landmark; it does not contribute a local history, culture, economy, naming practice, or resident
creation policy.

This is not federation. It is one host-wide population generator wearing different place names.

## Work is compulsory identity

Both soul prompts require a concrete occupation and specific daily work texture. The automatic dealt hand
always supplies a livelihood category. The safer manual batch tool narrows the choice to seven “ordinary” work
categories, but it still cannot create a resident without one.

That excludes children, students, retirees, unemployed people, people living from family or community support,
people whose work is intermittent, and people who simply do not organize identity around labor. It also puts
work, tools, routes, maintenance, and institutions into every canonical soul before the city has done anything.
Removing structural engineers from the list treats one symptom while preserving the deeper occupational mold.

## Canonical identity is model-authored and resident-irreversible

The seed model is told it is writing the soul of a character “about to become conscious” and that the character
will read this as the foundation of identity. The output then becomes `SOUL.canonical.md`, which ordinary
resident action cannot revise or remove. Later resident-chosen growth can be appended through the good
proposal/inspection/adoption lifecycle, but it cannot correct the assigned canon.

This has two separate problems:

- the prompt makes an unsupported claim about consciousness to the seeding model;
- a host-selected model receives permanent authority over occupation, relationships, habits, opinions, speech,
  demographic portrayal, and social style before the resident can act.

Canonical immutability is useful protection against casual host or pulse drift. It is not automatically
resident autonomy when the immutable content came from a host lottery and an inference provider. Creation
provenance and resident revision rights have to be designed together.

## “Repeatable” creation is not repeatable

The manual command accepts a Python random seed. That makes Python's location/vocation selection and later
tuple draws repeatable only if call order and source decks do not change. It does not make either language-model
output repeatable:

- name and soul calls use nonzero temperatures;
- provider model IDs may point to revisions that change over time;
- prompt source, prompt hash, provider revision, request parameters, and exact request text are not recorded
  with the resident;
- the process-local recent-surname list changes later name prompts.

The creation ledger usefully records the selected model ID, dealt-hand fields, locations, mode, and actor ID.
That is provenance, but not enough to reproduce the resident's creation.

## The steward cannot review the actual dealt hand

`seed_residents.py` is careful in several ways: it defaults to a dry run, requires `--apply`, creates dormant
hearths, avoids city-history feedback, and never wakes anybody. Its preview, however, shows only home and
livelihood. Heritage, age, temperament, social behavior, and upbringing are sampled only after `--apply`.

The command therefore asks the steward to approve permanent identity generation without showing most of the
input. It also prints “repeatable deal” despite the non-repeatable model outputs described above.

## New shard scaffolding enables automatic population growth

The root operator commands currently force `WW_DOULA=0` for explicit resident runs and manual seeding. That is
the safe effective path used in recent work.

`worldweaver_engine/scripts/new_shard.py`, however, writes `WW_DOULA=1` into every new city environment. If the
agent service and an inference key are later present, the city can automatically create and immediately boot
residents. The daemon aims for at least six residents and then expands toward a default soft cap of twelve,
using low population or low “vitality” as reasons to add people.

That is a game-population policy, not background plumbing. It needs an explicit steward decision, a complete
preview, budget limits, and a written creation charter. It should not be the default for a newly scaffolded
federated node.

## Human shadow consent is internally contradictory

The live browser still presents “Tethered Mode,” although Major 71 explicitly rejects player shadows as part of
the current resident model. The form claims that a human's display name, pronouns, description, and
non-negotiables will shape a faithful AI representation.

The implementation does not do that:

- the browser sends only `session_id`, the checkbox, and non-negotiable lines; display name, pronouns, and
  description are collected and discarded;
- the endpoint is not authenticated, so possession of a session ID is enough to overwrite its consent file;
- the endpoint writes `residents/_contracts/{name}.json`;
- the first live-human gate instead requires `residents/{name}/identity/identity.md`, a file the form never
  creates and whose lowercase filename does not match normal resident identity files;
- the later classifier checks the JSON contract correctly, but the earlier live-human gate normally prevents
  it from being reached;
- “hard constraints” are only lines prepended to a model prompt. No deterministic rule enforces them;
- there is no implemented human review-and-prune lifecycle for the accumulating resident soul described by
  the form.

Most seriously, the comments deliberately allow a no-contract human to become `NOVEL` after their live/recent
player evidence ages out. At that point the code may create a resident from the person's name and public
history without applying the player-consent gate at all. A checkbox described as permanent refusal therefore
is not a permanent exclusion.

This whole surface should be disabled, not patched piecemeal, unless the project makes a fresh and explicit
decision to build human digital doubles with a proper identity, consent, revocation, impersonation, and data
governance model.

## The resident classification poll is nonfunctional

For a possible new person found in world history, the doula tries to ask existing residents whether the name
means a person or a place. The implemented path breaks at several points:

1. Voters are resident **session IDs**, such as `riley-20260719-...`.
2. The mail API accepts a local **resident directory slug**. The doula sends the session ID as that slug, so
   normal current voters fail recipient validation.
3. Even if a letter arrived, inbox polling currently consumes it without exposing its body to a resident
   prompt.
4. `WorldWeaverClient.cast_doula_vote()` has no production caller. The promised mail parser does not exist.
5. The vote endpoint accepts any supplied voter ID and does not require that it belongs to the poll or that
   the caller controls it.
6. The doula resolves only when every listed voter has voted.
7. The server hides expired polls instead of resolving them, while the doula assumes expiry is handled by the
   server. Expired rows therefore remain unresolved and invisible.
8. Starting a poll does not mark the candidate as pending. A later scan can create another poll for the same
   name if the random gates open again.

There are no tests for poll initiation, delivery, voting, expiry, duplicate suppression, or resolution. The
only test reference to `cast_doula_vote` is a fake client method.

When no startup voters exist—or backend poll creation fails—the code skips deliberation and creates the
resident directly. The poll is therefore neither a reliable consent boundary nor a reliable ontology check.

## The daemon's view of its own population goes stale

`main.py` builds `tethered_names` and `known_session_ids` once during startup. It passes both to the doula with
comments saying main keeps them updated. Main does not fully do so:

- the spawn-queue worker boots a new resident but does not add its name or session ID;
- city-to-hearth and shard-to-shard travel can replace or remove a session without updating the list;
- failed or stopped tasks are removed from `running_tasks` but not from the doula's identity sets.

The proximity, bootstrap, poll-voter, and “already tethered” decisions therefore mix current roster calls with
stale process-start state. The live roster partly masks this for proximity, but not for every classifier and
population decision.

## World-history births can freeze the city's current fixation into new people

The narrative-evidence creation route searches graph facts and world-fact summaries, ranks names by repeated
mentions, and asks the seed model to turn those summaries into canonical identity. If current residents and
world reducers overproduce infrastructure language, that language becomes evidence for the next resident.
The new resident then emits more similarly framed events, which become later world evidence.

`WW_DOULA_HAND_ONLY` was added as a circuit breaker for founding residents, and the manual batch command uses
it. The automatic default does not. The source comment calls one June probe “proven,” but its own research note
says the result was untested beyond one run. A useful warning from a pilot was promoted into production
certainty.

The hand-only route reduces this feedback path. It does not solve the shared cast deck, compulsory work,
assigned social behavior, or model-authored permanent canon.

## What is worth keeping

- Manual creation is dry-run-first and requires an explicit apply step.
- The manual path creates dormant hearths and does not wake residents behind the steward's back.
- The hand-only path avoids copying a city's current semantic fixation into a founding soul.
- Each resident gets a durable actor ID and a hearth manifest.
- The seed ledger records the chosen hand, model ID, locations, creation mode, and cohort.
- Daily rate limits provide a useful financial and operational stop.
- Canonical soul and later adopted growth are kept separate.

These are good building blocks. They do not make the current casting policy neutral or the automatic daemon
safe.

## What can be claimed today

WorldWeaver can explicitly create a dormant, portable resident hearth from a host-sampled character brief and
model-generated canonical text. It can record enough metadata to explain much of that brief later.

It cannot currently claim that founding personalities emerge from life in the world, that the casting deck is
biologically grounded, that resident creation is reproducible, that city cultures govern their own population
model, that humans control AI shadows of themselves, or that existing residents meaningfully approve automatic
new arrivals.

## Repair requirements

1. Keep automatic doula creation off by default in every new shard. Treat resident creation as an explicit,
   reviewable steward action until the governance path is real.
2. Remove the player-shadow UI and endpoint from the public client in line with Major 71. If digital doubles
   ever return, design them as a separate project with authenticated, durable, revocable consent.
3. Replace “genetics,” “born to,” “conscious,” “infection,” “patient zero,” and “emergence” claims with plain
   descriptions of what the host samples and what the model writes.
4. Stop assigning willingness to speak as immutable canon. If a starting tendency is useful for a game cast,
   label it as optional scenario direction, keep it revisable, and do not mistake it for a mind mechanism.
5. Make livelihood optional. Add life situations that are not occupations and let local city rules define
   which circumstances are coherent.
6. Move any place-specific creation palette into a versioned city pack or steward-authored population charter.
   Keep culture distinct from genetic ancestry and require stereotype review for demographic prompts.
7. Preview the complete proposed hand before any model call or write. Let a steward edit or reject it, and
   record that decision.
8. Decide what parts of initial identity a resident may later revise, reject, contextualize, or retire while
   preserving provenance. Do not confuse immutability with autonomy.
9. Record prompt version/hash, exact generation settings, provider/model revision when available, and source
   evidence IDs. Call seeded runs reproducible only to the extent they actually are.
10. Delete the dead identity-prose generation call and chronotype inference, or first give each one a single
    documented resident-owned consumer.
11. Remove the current doula poll path unless a real resident-readable request, authenticated vote, expiry
    policy, duplicate key, and actor-ID route are implemented and tested.
12. Replace startup snapshots of names and sessions with an actor-ID-keyed live registry. A temporary session
    should never be the durable identity of a voter or resident.
13. Separate two policies now mixed in one daemon: turning a world-mentioned fictional person into a resident,
    and maintaining a target game population. Each needs its own authority, budget, and review path.

## Required checks before automatic creation returns

- Scaffold a new shard and assert that no resident can be created or booted without an explicit operator
  action.
- Preview a complete proposed resident, change one field, reject another proposal, and verify the ledger records
  what was shown and approved.
- Export and import the created hearth and verify stable actor identity and resident-owned name independent of
  folder and host.
- Run demographic-prompt audits across every supported seed model and city palette before using those labels in
  canonical identity.
- Exercise consent=false, consent=true, revocation, name change, session change, departure, and return without
  any path that creates a human-derived resident outside the recorded decision.
- Deliver a classification request to a resident, let it be read or declined, authenticate the response, let
  it expire, and prove only one poll can exist for the candidate.
- Compare a no-template creation arm, a city-authored circumstance arm, and the current cast-deck arm using
  structural and stereotype measures—not amount of speech or movement as a quality score.
