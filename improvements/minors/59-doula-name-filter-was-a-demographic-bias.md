# The doula's name filter was a demographic bias — accept any name, reject only non-names

## Problem

`DoulaLoop._looks_like_name` (ww_agent/src/loops/doula.py) gated every dealt resident's name through
`re.fullmatch(r"[A-Z][a-z]+(?: [A-Z][a-z]+)?", s)` — **ASCII-only, exactly one or two words, no hyphens,
no apostrophes, no accents** — and then rejected the name if **any** word appeared in a place/role-word
blocklist. That silently bounced a large fraction of real human names:

- accented names — `Tiago Gonçalves`, `José Martínez`, `Müller`, `Renée` (non-ASCII letters)
- apostrophe names — `Patrick O'Sullivan`, `D'Angelo`
- hyphenated names — `Anne-Marie`, `Park Min-jun`
- the Korean surname `Park`, plus `Brooks`/`Banks`/`Forest`/`Glen` — bounced as "place words"
- mononyms (`Sukarno`) and 3+ part names (`Maria del Carmen`) — bounced by the two-word cap

Surfaced when the gemini-seeded re-deal **stalled**: the doula kept generating valid diverse names
(`Gonçalves`, `O'Sullivan`, `Jihoon Park`) and rejecting every one, so population wouldn't advance.
The deeper damage is silent: the filter **undercut the doula's own diversity pools** (`_NAME_TRADITIONS`,
`_ORIGINS`) and biased *every prior cast* (SFO, PDX, the whole convergence/casting investigation) toward
anglo-ASCII names — a confound hiding inside the casting work itself.

## Proposed Solution

Don't validate name *shape* (per [*Falsehoods Programmers Believe About Names*](https://www.kalzumeus.com/2010/06/17/falsehoods-programmers-believe-about-names/),
McKenzie 2010 — there is no reliable structural rule). Accept the standard international-name set —
**Unicode letters + space + hyphen + apostrophe + period** (the `[\p{L}\s.'-]` rule,
[brettrawlins.com](https://brettrawlins.com/blog/regular-expression-for-international-names/)), with
punctuation only *between* letters (`O'Neil` ok, `O'` not). Reject **only LLM failure modes**: empty,
digits/IDs, stray markup/sentence punctuation (`:;!?()[]/`), and runaway length/word-count (an
explanation or refusal). The real thing the place-word blocklist was groping at — the model **echoing
the location** instead of naming a person — is caught precisely at the call site (`name == location`),
so a place-word *surname* survives.

## Files Affected

- `ww_agent/src/loops/doula.py` — `_looks_like_name` rewritten (Unicode-permissive); location-echo guard
  added at the de-novo dealing call site. Shared with the-stable fork if it carries a doula — reconverge.

## Acceptance Criteria

- [x] Accepts: Gonçalves, O'Sullivan, Jihoon Park, Anne-Marie, José, Müller, Maria del Carmen, Ngô Thị Huyền, Sukarno, Park Min-jun, Renée. (tested)
- [x] Rejects: `Agent 7`, `x`, `name: John`, `(no name)`, `O'`, `-Marcus`, `12345`, a URL, a refusal sentence. (tested)
- [ ] On a gemini re-deal, the realized cast's demographic spread matches the doula's intended diversity pools (no anglo-ASCII skew).

## Risks & Rollback

- A refusal/explanation ≤5 words with no punctuation could slip through (rare under the `max_tokens=12`,
  "name only" prompt); accept the small risk rather than re-introduce a name-shape/word blocklist (the
  bias). Rollback = revert the function; but the old rule is the bug, so prefer fixing forward.
