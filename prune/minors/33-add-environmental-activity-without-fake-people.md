# Add environmental activity without fake people

## Problem

A place can feel mechanically empty when no full resident is present. The old proposal solved this by
inventing “ambient people” such as workers, regulars, and crowds. That would create apparent persons who
cannot actually speak, remember, consent, or continue as actors.

The useful part is environmental activity: weather, light, opening hours, transit flow, machinery, water,
fire, scheduled work, and recent public events. These can make places distinct without pretending that
generated scenery is a population.

## Build next

1. Define a small deterministic `environmental_activity` projection derived from city-pack schedules,
   local time, weather, declared fixtures, and recent typed world events.
2. Allow it to attach to a canonical place or sublocation with source IDs and expiry.
3. Return concrete observations such as rain under an awning, mill noise, a lit oven, or a delayed ferry.
4. Let it affect ordinary engine affordances only through explicit rules, such as a closed shop or wet path.
5. Expose the same facts to humans and residents without an LLM-generated narrator paragraph.
6. Give stewards a source-and-expiry diagnostic without turning it into resident surveillance.

## Boundaries

- Environmental activity is not a person, actor, speaker, correspondent, or relationship target.
- It cannot create chat, letters, memories, intentions, or fake crowd testimony.
- If real non-resident characters are later needed, they require an explicit NPC model and product decision.
- The projection is derived from inspectable inputs and expires or updates deterministically.
- The runtime does not inject random activity merely to force a resident reaction.

## Acceptance criteria

- [ ] One versioned environmental-activity shape exists with source, place, time, and expiry.
- [ ] Activities derive deterministically from declared or typed facts.
- [ ] Humans and residents receive the same concrete local facts without paid narration.
- [ ] Activities may change affordances only through explicit engine rules.
- [ ] No activity can impersonate a person or produce social events.
- [ ] Diagnostics show source and expiry without private resident data.
