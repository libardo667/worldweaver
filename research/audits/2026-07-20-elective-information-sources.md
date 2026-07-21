# Elective information source audit

Date: 2026-07-20

## Question

When a resident chooses to read a source, what actually enters the model prompt? Is it a current record,
someone's writing, a deterministic calculation, or model-authored interpretation presented as fact?

This audit covers every source that the shared registry could advertise before the audit. It follows each
source from its underlying data through selection and rewriting to the final model call. It does not inspect
private resident prose.

## Result

The basic read boundary is worth keeping. A read is private, bounded to one source, cannot directly change
the world, and returns to one final model call. Most city game sources read canonical shard records and add
only mechanical explanations of the actions those records permit.

The main fault was labelling. Sources that omitted a provenance label silently became `local-knowledge`, and
the production prompt discarded provenance, freshness, locality, visibility, and egress before the resident
chose a source. Returned source text also had no explicit boundary separating content from instructions.

Three advertised sources were withdrawn:

- `investigate` described itself as world history but searched model-authored event summaries from only the
  resident's current session and discarded the underlying event identity and time;
- `chatter` described a live citywide commons, but the engine's current chat endpoint cannot write to its
  reserved `__city__` channel;
- `news` can cause server-side public RSS access, but resident-scoped external-network grants do not exist.

## Source-by-source findings

| Source | Underlying input | Selection and transformation | Decision |
| --- | --- | --- | --- |
| `recall` | The resident's legacy keepsake file and canonical `memory_kept` / `felt_sense_logged` ledger events | Literal case-insensitive query, or the last three keepsakes and last felt sense; returns the resident's exact stored text | Keep. The audit repaired the missing canonical `memory_kept` path. |
| `measure` | The resident's arithmetic expression | Parses a bounded arithmetic-only syntax tree; no names, calls, files, or network; returns the numeric result | Keep as local computation. |
| `eats` | A hard-coded San Francisco food guide written into this repository | Normalizes a neighborhood name and returns at most three stored restaurant notes | Keep for San Francisco only, labelled `authored-reference` and `undated`; it is not resident knowledge or current fact. |
| `news` | KQED or San Francisco Standard RSS, fetched by the shard and cached for an hour | Returns up to four headline strings in feed order; publisher and publication time are currently lost | Do not advertise until Minor 122 provides an explicit resident-scoped egress grant and the records preserve publisher attribution. |
| `places` | Steward-authored city-pack landmarks and coordinates in the shard database | Resolves the named place, calculates distance, sorts nearest first, and returns up to six landmark names with a mechanical “near” label | Keep as `authored-reference` at `pack-version`, not first-hand perception. Fictional packs without coordinates may return unavailable. |
| `investigate` | Semantic search over `WorldFact` summaries derived from world events | Previously restricted the query to the current session, then returned only summary prose while dropping event ID, event type, actor, time, and delta | Remove. A future public-history source needs typed public events and stable evidence IDs, not digested summaries. |
| `chatter` | Attributed messages stored on the reserved `__city__` chat channel | Name match, literal body match, or newest-first; exact speaker, body, and time. The audit removed the old personality-embedding ranking | Do not advertise until an explicit authenticated citywide publish/read contract exists. Keep the deterministic provider as implementation material. |
| `travel` | Routes and currently registered nodes returned by the configured federation directory | Literal route/city/node filter; reports live nodes or an honest unavailable route and adds the exact travel target | Keep. Label as `federation-record`, live, and egress. This is configured federation discovery, not open-web access. |
| `objects` | Canonical carried and co-located object records plus current co-presence | Optional literal object filter; returns at most twelve descriptions, ownership/location state, and exact typed action targets | Keep as a live `shard-record`. Object description prose remains attributed to the object record rather than being presented as neutral perception. |
| `making` | Canonical local material balances and steward-declared recipes | Optional literal filter; reports counts, whether requirements are met, and the exact typed recipe target | Keep as a live local `shard-record`. The extra prose is mechanical, not dramatic narration. |
| `exchanges` | Canonical actor-scoped exchanges, carried objects, and current co-presence | Optional literal person/object filter; renders exact terms and typed accept, decline, cancel, or offer targets | Keep as a private live `shard-record`. It does not move an object until a typed action succeeds. |
| `access` | Canonical place policy, grants, pending requests, place names, and co-presence | Requires an exact or uniquely matching place; renders policy state and typed request/controller choices | Keep as a private live `shard-record`. It reports permission state rather than predicting social consequences. |
| `stoops` | Canonical stoop entries and the resident's carried-object records at the exact place | Blank lists local stoops and leave choices; a uniquely named stoop returns its entries and typed take/withdraw choices | Keep as a live local `shard-record`. Descriptions and stoop prompts are authored artifact records, not engine narration. |
| `growth` | Pending identity-proposal events in the resident's private canonical ledger | Blank selects latest; exact event ID selects one proposal; returns the exact proposed words, evidence IDs, and the separate typed adoption target | Keep in the hearth only as `self-memory`. Inspection is required but never counts as adoption. |
| `gifts` | Append-only private delivery notices and files inside the resident-owned `workshop/given` scope | Blank lists recent delivery names and notes; exact safe path opens bounded text, PDF, or image content | Keep when explicitly enabled. File-scope deny rules and size limits apply. Images now reach only the after-read model call. |
| `files` | Explicitly authorized read roots filtered by hard secret denies plus `.gitignore` and `.familiarignore` | Blank lists root names only; exact path returns one 12 KB text page, bounded media extraction, or one directory listing | Keep when explicitly granted. The automatic source advertisement no longer leaks filenames. |

## Runtime changes made by the audit

- Missing provenance now becomes `unknown`, not `local-knowledge`.
- The source list shown before a choice includes egress, provenance, freshness, locality, and visibility.
- Returned records show source, egress, provenance, selection mode, freshness, locality, visibility, and time
  when present.
- A provider cannot relabel its records as a different source.
- The production reference loop does not cache reads by default. Even when an older caller opts into caching,
  live and immediate records are never cached.
- Returned text is enclosed in an explicit “elective source material” block and cannot change the response
  contract or claim that a world action succeeded.
- Scoped images are sent only to the final inference call after the resident chose to open them.
- Hearth whispers are delivered exactly as written; the host no longer rewrites them to sound more direct or
  urgent.

## Remaining work

1. Implement Minor 122 before restoring public-web sources such as `news`.
2. Define an authenticated citywide channel before restoring `chatter`; do not overload exact-place speech.
3. If a public-history source is needed, build it from typed public events with stable IDs, time, authorship,
   visibility, and deterministic filters. Do not return generated event summaries as ground truth.
4. Preserve publisher or author attribution inside sources such as RSS headlines and authored object or stoop
   descriptions where the underlying record can supply it.
5. Finish Major 65's durable grant, limit, inspection, and revocation records. The registry is a capability
   list, but it is not yet a complete permission system.
