# Distinguish private records from physical belongings

## Problem

The same resident workshop is available at the hearth and in a city. Pulse prompts show its project names
and recent excerpts. Physical objects use a different system and are visible only when the resident elects to
inspect the `objects` source or encounters them locally.

This leaves an important fact unstated: a resident may have privately imagined a physical notebook, bag, or
other possession as part of life at the hearth. When that memory follows them into a city, the runtime does
not say, "that stays at your hearth and is outside your current senses." Remembering the possession does not
mean it is in a city pocket, and failing to see it in the current room does not mean it was lost or stolen.
In the one-hour Alderbank run, two residents independently made unsupported public claims about a missing bag
or notebook. Private contents were not reviewed, so this cross-attachment confusion is a hypothesis rather
than a proven cause.

## Proposed solution

- Give prompt context separate typed sections for private records, carried physical objects, and local
  physical objects.
- Add an explicit private/hearth location for a self-authored possession when the resident has established
  one, without promoting that private claim into the city's canonical object store.
- Describe workshop entries as private records available across attachments, not as current-room inventory.
- When physical inventory has not been inspected, say it is unknown rather than empty or missing.
- Permit a claim of loss or theft only when a canonical object receipt or a direct observed change supports
  it. Otherwise keep the model free to wonder privately but do not present the suspicion as world fact.
- Add synthetic tests covering hearth-to-city travel, a private notebook project, a carried notebook object,
  an object left safely at the hearth, and a genuinely removed city object.

## Files affected

- `ww_agent/src/runtime/prompt_context.py`
- `ww_agent/src/runtime/pulse_engine.py`
- `ww_agent/src/runtime/cognitive_core.py`
- `ww_agent/src/world/city_tools.py`
- `ww_agent/tests/`

## Acceptance criteria

- [ ] Prompt context labels private workshop records separately from physical inventory.
- [ ] An unread physical inventory is represented as unknown, not empty or missing.
- [ ] A private notebook project does not appear as a carried notebook object.
- [ ] A privately imagined hearth possession can remain at the hearth when the resident enters a city.
- [ ] A canonical carried object and a local resting object remain distinguishable.
- [ ] A loss or theft assertion can cite a canonical object transition when one exists.
- [ ] Tests do not read or depend on any live resident's private workshop or ledger.
