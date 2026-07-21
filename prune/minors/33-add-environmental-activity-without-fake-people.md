# Add environmental activity without fake people

## Status

The misleading predecessor has been removed from the live path. On 2026-07-20, an audit found that the scene
endpoint was expanding weather, time, headcount, event count, and city-pack `vibe` prose into invented people,
queues, glances, conversations, silhouettes, and social pressure. The reference resident received those
labels as if they were immediate surroundings. The scene endpoint and reference loop no longer generate or
consume that material, and generic historical event summaries are no longer part of the current-scene
snapshot. This work item owns the honest replacement; until it exists, the engine should report less rather
than improvise.

The retired `CognitiveCore` path still contains older code that converts rough weather, event count, and
`ambient_presence` into internal pressure signals. It is not called by the production resident host, but none
of that code should be copied into the reference loop without satisfying the boundaries below.

## Problem

A place can feel mechanically empty when no full resident is present. The old proposal solved this by
inventing “ambient people” such as workers, regulars, and crowds. That would create apparent persons who
cannot actually speak, remember, consent, or continue as actors.

The useful part is environmental activity: measured weather, light, declared opening hours, machinery,
water, fire, and scheduled systems. A typed event can also have a current visible consequence, but an old
event summary is history rather than present perception. These can make places distinct without pretending
that generated scenery is a population.

## Build next

1. Define a small deterministic `environmental_activity` projection derived from city-pack schedules,
   local time, weather, declared fixtures, and recent typed world events.
2. Allow it to attach to a canonical place or sublocation with source IDs and expiry.
3. Return concrete observations such as current rainfall, a running mill, a lit oven, or a delayed ferry only
   when a declared or measured source supports that exact claim.
4. Let it affect ordinary engine affordances only through explicit rules, such as a closed shop or wet path.
5. Expose the same facts to humans and residents without an LLM-generated narrator paragraph.
6. Give stewards a source-and-expiry diagnostic without turning it into resident surveillance.

## Boundaries

- Keep four kinds of information distinct:
  - measured or engine-owned facts;
  - steward-authored setting descriptions;
  - attributed participant expression;
  - derived or synthetic interpretation.
- Only measured or engine-owned current facts may arrive as direct automatic perception.
- Setting descriptions must be labelled as authored descriptions. Participant expression must retain its
  author. Derived interpretation must never masquerade as something the resident directly sensed.
- Environmental activity is not a person, actor, speaker, correspondent, or relationship target.
- It cannot create chat, letters, memories, intentions, or fake crowd testimony.
- If real non-resident characters are later needed, they require an explicit NPC model and product decision.
- The projection is derived from inspectable inputs and expires or updates deterministically.
- The runtime does not inject random activity merely to force a resident reaction.
- Weather plus headcount does not prove umbrellas, sheltering, queues, glances, conversations, or attention.

## Acceptance criteria

- [ ] One versioned environmental-activity shape exists with source, place, time, and expiry.
- [ ] Activities derive deterministically from declared or typed facts.
- [ ] Humans and residents receive the same concrete local facts without paid narration.
- [ ] Activities may change affordances only through explicit engine rules.
- [ ] No activity can impersonate a person or produce social events.
- [ ] Diagnostics show source and expiry without private resident data.
