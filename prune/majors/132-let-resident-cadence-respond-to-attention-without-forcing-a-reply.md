# Let resident cadence respond to attention without forcing a reply

## Status

The resident host currently checks the world on a fixed cadence. A normal city run waits 20 seconds between
ticks. Local speech is classified as direct when it names or tags the resident, but a city resident cannot
discover that speech until the next poll. Unlike a keeper whisper at the hearth, city speech also has no
event signal that can wake a sleeping runner early.

Keep the current cadence for the larger Alderbank baseline. Test any cadence change separately so changes
in conversation, movement, cost, and responsiveness can be compared with the same cohort shape.

## Problem

A fixed 20-second poll makes an occupied town feel sluggish to a human. Lowering the interval for every
resident all the time would hide the delay by buying many more scene reads, embedding calls, and possible
model calls. It would also make a quiet resident unnaturally busy.

The runtime needs to distinguish three separate decisions:

1. when to check whether something changed;
2. whether a change deserves the resident's attention;
3. whether the resident chooses to answer or act.

A direct message or local `@name` should shorten the first delay and may open the second decision. It must
not decide the third. Being reachable is not the same as being obligated to reply.

## Proposed solution

1. Give the resident host an interruptible wait instead of an unconditional sleep. A world adapter may
   signal that new addressed input is available; timeout still produces the ordinary quiet tick.
2. Add a narrow city notification path for actor-addressed local chat and, once Major 39 settles its thread
   model, direct mail. Prefer a cheap event cursor or long poll over repeatedly fetching the full scene.
3. Keep the CognitiveCore's current direct-attention rule: addressed input can cause an attentive pulse,
   but the pulse remains free to reply, defer, move, keep working, or do nothing.
4. Allow bounded per-resident cadence to change with recent structural state. Start with a small state
   machine rather than model-written timing:
   - quiet or resting: slow baseline checks;
   - recently active or co-present: normal checks;
   - newly addressed or sharply aroused: one prompt early, followed by a short responsive window;
   - repeated quiet checks: back off again.
5. Put minimum and maximum intervals, cooldowns, and inference-cost guards in configuration. Do not derive
   urgency by reading or scoring the private prose of a message.
6. Record structural timing evidence: signal time, next observation time, whether attention ignited, whether
   any act followed, and the number and cost of extra checks. Do not record message bodies in the report.
7. Run a matched Alderbank trial after the fixed-cadence baseline. Compare time-to-notice for addressed
   events, ordinary tick volume, inference calls, actions, rest, and cleanup.

## Files affected

- `ww_agent/src/resident.py`
- `ww_agent/src/runtime/cognitive_core.py`
- `ww_agent/src/runtime/perception.py`
- `ww_agent/src/world/city_world.py`
- `ww_agent/src/world/client.py`
- `ww_agent/scripts/resident_once.py`
- `ww_agent/scripts/resident_cohort.py`
- `worldweaver_engine/src/api/game/world.py`
- `worldweaver_engine/tests/`
- `ww_agent/tests/`
- `docs/how-to/run-residents.md`

## Boundaries

- Faster notice never means forced speech or a guaranteed reply.
- Public local speech can wake only residents who are physically present and explicitly addressed.
- Citywide chatter remains elective and must not become an interrupt feed.
- Mail remains slower correspondence unless its final shared thread contract explicitly says otherwise.
- A steward may set cost and rate limits, but may not use hidden prose analysis to rank a person's urgency.
- One busy place must not wake every resident in the city.
- Fixed cadence remains available as the control and rollback path.

## Acceptance criteria

- [ ] A city resident can be notified of newly addressed local speech without polling a full scene in a
  tight loop.
- [ ] A direct local address causes the next observation sooner than the quiet baseline, within a documented
  upper bound.
- [ ] Receiving an address does not require the resident to reply or act.
- [ ] Unaddressed citywide chatter does not shorten a resident's cadence.
- [ ] Quiet and resting residents back off to the configured baseline without accumulating wake signals.
- [ ] Cadence limits and cost guards are configurable per host or resident run.
- [ ] Bounded-run reports show content-blind notice latency, tick volume, inference use, and cleanup.
- [ ] A matched Alderbank trial compares fixed and responsive cadence without changing the cohort, model,
  action-tendency setting, or test duration.
- [ ] Shutdown, hearth parking, travel, and exclusive hearth leases still work while a wait is interrupted.

## Risks and rollback

An event-driven wake path can create notification storms, race with travel, or turn social attention into a
coercive engagement mechanic. Coalesce repeated signals, scope them by actor and exact place, cap the fast
window, and preserve the resident's action choice. If those guarantees fail, disable responsive cadence and
return to the fixed timer while keeping the timing measurements.
