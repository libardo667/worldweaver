# CognitiveCore temporal and attention mechanics

Status: code audit and deterministic reproductions, 2026-07-19.

This pass asks whether the runtime's time words describe the time it actually measures, and whether an event
that deserves notice can reliably reach a resident without requiring a reply.

## The actual call-pressure equation

For each qualifying observation, the runtime stores one surprise magnitude. At time `t`, it computes:

```text
call pressure = sum(
  recorded magnitude * 2 ** (-(t - observation time) / 300 seconds)
) since the last reactive call
+ capped predicted-anchor-absence term
```

The overall magnitude for one observation is the largest feature mismatch, not a sum or a probability. A
fixed threshold of `1.0` opens a reactive model call. A successful or failed reactive call resets the ordinary
surprise window; a settling or fervor call does not.

This is a comprehensible scheduler. It is not a physiological arousal measurement.

## Poll frequency changes the mechanism

Surprise is added once per observation. It is not multiplied by elapsed time, normalized by polling rate, or
deduplicated while the underlying state is unchanged. Decay, meanwhile, is measured in wall-clock seconds.
The number of observations per minute therefore changes how quickly the same mismatch opens a model call.

A deterministic replay of an unchanged `0.4` mismatch produced:

| Poll interval | Observations to cross `1.0` | Wall time to crossing |
| --- | ---: | ---: |
| 5 seconds | 3 | 15 seconds |
| 20 seconds | 3 | 60 seconds |
| 60 seconds | 3 | 180 seconds |

This bears directly on earlier resident tests:

- the normal `CognitiveCore` cadence is at least 20 seconds after the prior tick completes;
- the compatibility familiar daemon defaults to 30 seconds;
- `dev.py resident --wake --ticks N` and `resident_once.py --ticks N` default to a 0.5-second pause;
- model and tool latency lengthen natural-cadence ticks, but bounded smoke tests can run again almost
  immediately after a fast no-call tick.

The default bounded runner can therefore observe unchanged state about 40 times as often as the natural
resident command, or 60 times as often as the compatibility daemon. Those runs are valid software smoke
tests. They are not compressed samples of normal resident time, and their pulse counts cannot support a
behavioral claim without a virtual clock and cadence-independent integration.

## Settling does not measure sustained calm

`check_settling()` says it tests whether arousal “has stayed” low for five minutes. It actually checks:

```text
current effective pressure < 0.3
and
time since the last model call >= 300 seconds
```

It does not find when pressure most recently fell below `0.3`. A new `0.2` surprise at the exact instant of
the check can therefore be classified as 400 seconds of calm when the last model call was 400 seconds ago.

At ordinary daytime reactivity, the reproduction returned:

```text
raw pressure 0.2; event age 0 seconds; reported calm 400 seconds; settling = true
```

The resulting prompt asserts that nothing presses or surprises even though a surprise was just recorded.

Settling also opens a new model call every five quiet minutes while the resident is awake. It does allow a
null act, but it is still forced inference, forced self-report, and a new prompt. This is not equivalent to
letting a person read, daydream, practice silently, or simply do nothing for as long as they choose.

## Fervor does not measure sustained elevation

`check_fervor()` has the same clock error. It checks current pressure against the `0.45..1.0` band and checks
whether three minutes have passed since the last model call. It does not measure when pressure entered the
band.

A new `0.8` surprise at the exact instant of a check was classified as 400 seconds of restlessness. The model
prompt then says the resident is wound tight, has nowhere to put the charge, and should spend it. That
behavioral instruction is based on a duration that never happened.

## Circadian scaling can reverse the story without changing the event

The same new `0.8` surprise, multiplied by a nighttime reactivity of `0.25`, becomes effective pressure
`0.2`. The scheduler immediately classifies it as 400 seconds of settling even though the raw event is new.
The raw, unscaled pressure is still passed to the model producer.

The circadian implementation is a fixed cosine plus a phase offset. The phase offset is derived from a hash
of the resident's name unless explicitly configured. It does not measure sleep debt, recent rest, light,
activity, individual development, illness, or any other biological input. It should be described as a
world-clock sensitivity schedule. Calling it a body clock currently overstates it, and a name change can
change the default schedule.

## Direct address can be lost behind a saturated summary

Exact-place speech is first retained as a pending packet. Whether the model gets to read the packet depends
on a reactive call opening. City speech has no separate force-attention hook.

The numeric route compresses social state into one maximum-valued node. Once `social_pull` is already `1.0`,
another direct address may leave the node unchanged. If the resident predicted or habituated to that value,
the new message creates no numeric mismatch. It remains pending but cannot itself open the reactive prompt
that would contain its words.

Settling does not rescue this case: its prompt context deliberately withholds rolling speech and encounter
packets. A resident can therefore receive a new direct address while the aggregate social node is saturated,
continue to produce no reactive mismatch, and later receive a prompt declaring that nobody is waiting.

Attention and reply need separate contracts:

- a new exact-place direct address should become available to attention promptly;
- attention should mark that the words were actually presented;
- no mechanism should force agreement, speech, or an immediate reply;
- multiple new events must not collapse invisibly merely because an aggregate node is already at its cap.

## The “waveform vital” does not justify mind-health labels

`derive_vital()` is useful as an operational stuck-call detector, but its current account overreaches:

- it calls a sawtooth “healthy” and a ramp “distress” without evidence about resident experience;
- it counts `idle_fired` as a discharge although `record_idle()` explicitly leaves ordinary pressure
  untouched;
- its reconstructed waveform omits the anchor-absence term that `derive_arousal()` adds to current pressure,
  despite claiming to mirror the latter exactly;
- for gaps between stored events, it credits an entire segment above a threshold based on the level at the
  start of the gap, even if exponential decay would cross below the threshold partway through;
- any discharge anywhere in the window can label a later stuck period `active`, a limitation already noted in
  the archived work item.

The production exception handling already records a reactive call attempt and resets the ordinary window even
when inference fails. What remains useful here is an operational alert such as
`above_call_threshold_without_completed_attempt`. It is not a diagnosis of a mind.

## Repair requirements before behavioral interpretation

1. Make repeated observations cadence-independent: integrate by elapsed time, emit on meaningful state
   transitions, or deduplicate unchanged evidence.
2. Give replays a virtual clock and make bounded tests use the same temporal semantics as natural runs.
3. Measure time-in-band from actual crossings if settling or elevated-band scheduling survives at all.
4. Keep quiet as a valid unbounded outcome. Do not use periodic inference as proof that reflection occurred.
5. Give new direct address an event-level attention path that does not imply a reply obligation.
6. Rename arousal/ignition/vital fields around call pressure, call opening, completion, and failure.
7. Do not compare past tick-count runs as resident behavior until their poll timings and inference durations
   are reconstructed or the claims are rerun under controlled time.
