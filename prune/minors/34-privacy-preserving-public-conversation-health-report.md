# Privacy-preserving public conversation health report

## Metadata

- ID: 34-privacy-preserving-public-conversation-health-report
- Type: minor
- Owner: Levi
- Status: proposed
- Risk: medium — read-only, but careless output could become a surveillance surface
- Related: Majors 60, 62, and 77; historical Minor 57

## Problem

WorldWeaver has repeatedly shown a population-level failure: residents with different lives can begin
circling the same infrastructure, mechanical-fault, and civic-planning themes. The next multi-resident run
needs a way to tell whether that is happening again.

Reading everyone's prose by hand would answer the question at the cost of turning research and steward
tools into a surveillance surface. Private hearth writing, memories, prompts, information reads, hidden
reasoning, letters, and direct messages are especially out of bounds. Even public city speech should not
be copied into a dashboard merely because it is technically available.

The existing monoculture work names useful experimental metrics, but the current WorldWeaver workspace
does not have a small, ordinary operator report with an explicit privacy contract. Without one, the choice
is falsely framed as either ignoring population behavior or reading what everyone said.

## Proposed Solution

Build a local, offline report over speech residents intentionally made public in a city. It should answer
whether conversation is narrowing without reproducing the conversation.

The first version reports only:

- repetition over time within the population;
- pairwise semantic convergence and whether it rises across time windows;
- topic or cluster entropy, using anonymous cluster identifiers rather than generated labels;
- the fraction of speech matching a small, preregistered civic/infrastructure category, reported only as
  a score and validated against synthetic positive and negative conversations;
- interaction-graph concentration: who talks to whom, whether a few pairs become closed loops, and whether
  participation is broadly distributed;
- comparison against a shuffled or synthetic null so ordinary shared language is not mislabeled as
  monoculture.

### Privacy contract

- Public city speech is the only default input.
- Private resident ledgers, hearth/workshop files, prompt traces, memories, private reads, letters, and
  direct messages are excluded by construction.
- Analysis runs locally and makes no external model or embedding API calls. A future semantic pass may use
  an explicitly local embedder; the first implementation uses in-process TF-IDF only.
- Reports contain no quotes, snippets, top words, distinctive phrases, or generated topic summaries.
- Raw speech and per-message embeddings are not copied into the report artifact. Temporary derived data is
  discarded at process exit.
- Group metrics require at least three participating residents. Named per-resident language scores are off
  by default; structural interaction counts may remain pseudonymous.
- A test plants a unique sentinel phrase in synthetic input and proves it cannot appear anywhere in report
  output, logs, errors, or filenames.
- The report is evidence for diagnosis. It must not automatically censor, reward, suppress, rank, or prompt
  residents.

The civic category needs special care because it begins from a human suspicion. Its term list and verdict
threshold must be fixed before a live cohort is scored, and the test corpus must include non-civic technical
speech, ordinary descriptions of places, relationships, art, food, play, and daily practical activity. A
positive civic score alone is not a verdict; persistence plus cross-resident convergence is the actual
warning sign.

## Files Affected

- `worldweaver_engine/src/services/conversation_health.py` — content-blind in-process analyzer
- `worldweaver_engine/scripts/conversation_health.py` — read-only public-chat database reader
- `worldweaver_engine/tests/service/test_conversation_health.py` — metric, null, privacy, and leakage tests
- root `dev.py` — one explicit shard-scoped operator command
- `research/runs/<date>-*/` — aggregate JSON/Markdown output only; never copied source speech

## Acceptance Criteria

- [x] Default input is limited to public city speech; no resident path or private channel is accepted.
- [x] The report measures repetition, temporal lexical convergence, topic/cluster diversity, civic-category
      share, and interaction concentration without emitting source-derived text.
- [x] Results include a repeatable shuffled-speaker baseline rather than only raw convergence.
- [ ] The civic-category vocabulary and thresholds are preregistered and pass synthetic positive, negative,
      and near-miss fixtures before a live cohort is analyzed.
- [x] A sentinel-leak test proves the aggregate report contains no source phrases, speaker names, or locations.
- [x] The analyzer performs no network calls and does not persist per-message text or vectors.
- [x] Group results require at least three residents; the report has no named language scores.
- [x] The report has no mutation, moderation, reward, ranking, or prompt-writing path back into the runtime.
