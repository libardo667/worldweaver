# Topology: make speech physical (locality by default) — archived

## Metadata

- ID: 63-topology-make-speech-physical
- Type: major
- Owner: Levi
- Status: complete and archived (2026-07-17)
- Risk: high — touches the effector's output routing; the seam the canonical-reset live test proved is the engine
- Depends On: nothing hard; pairs with [[64-plural-salience]]. Both are the **world-side** of the chosen-vs-unchosen invariant (see ROADMAP standing invariant).

## Problem

The 2026-06-06 canonical-reset + re-seed test proved the topic-monoculture is **not** the perception coupling Major 60 fixed, and **not** composition (a deliberately diverse cast converged anyway). The locus moved one layer out — into the **wiring**.

The seam (verbatim from the live code, `effectors.py :: _speak`): a resident's speech to a specific person who **isn't co-located** is published to `__city__` as a public broadcast — *"so they can actually hear it, instead of into an empty local room."* In a spread-out world, most directed speech therefore becomes a citywide post, and the citywide channel **saturates** with whatever topic is live. Major 60's content-blind floor then samples that channel — but **a content-blind random sample of a saturated channel is still the monoculture.** The floor reduced the *volume* of the citywide channel, not its *topic distribution*. You cannot sample diversity out of a feed that is all one note.

Mr. Review's diagnosis: the fix cannot live at the sampling layer (input); it has to **de-saturate the source** (output). Saturation is an artifact of *non-physical* broadcast-as-default — the world let one private remark reach every mind.

## Completion Note — 2026-07-17

The transport change had already landed in the live CognitiveCore path and was covered by focused tests:

- speech with no target, or speech to someone present, is posted only to the current room;
- speech addressed to an absent person uses the private letter transport and records
  `speech_carried`; it never falls back to `__city__`;
- only an explicit `city`/`citywide`/`broadcast` target produces `city_broadcast_sent`;
- an optional per-resident broadcast cooldown can make repeated broadcasts land locally instead;
- perceived speech records whether it was local, direct, or citywide, and relational delivery events
  retain stable speaker, listener, location, utterance, and reply evidence;
- the pulse contract now explains the local/private/public reach of speech instead of presenting
  `city` as an unexplained generic target.

The two remaining acceptance bullets asked for new live-population runs. Those are useful later as
research about the effect size, but they are not missing architecture and are deliberately outside the
current architecture queue. The work item therefore closes on the deterministic transport contract and
its tests.

## Proposed Solution

**Make speech physical.** Restore the correspondence between speech and presence:

- **Locality by default.** Speech reaches **who is present** (the room). This is the default and the fallback — *not* a citywide broadcast.
- **A deliberate, costly, directed carry.** Reaching a specific *absent* person is a distinct, intentional act — a directed/private carry to *that person* (a DM-like channel), not an ambient post to everyone. Reaching the *whole* city is a true, deliberate broadcast (a town crier act), rarely taken, never the fallback for "they weren't standing next to me."

This changes **who can hear**, never **what may be said** — a world-physics property (sound travels, rooms exist), not a behavior target. It is law-safe in the cleanest possible way, and it attacks the *root*: de-saturate the channel and **a content-blind sample of a now-plural channel is diverse by construction.** You don't sample a monotopic feed cleverly; you stop having one feed.

**Secondary, complementary knob:** ration **addressed→attend** on the active channel (the chosen-vs-unchosen principle applied to output the way Major 60 applied it to input — a mind can't be pulled into every citywide naming). Principled but secondary: it treats the *symptom* (being pulled) not the *cause* (saturation). Keep it as a knob; watch it doesn't insulate away the local responsiveness that works.

**Explicitly NOT:** a "diversity floor" that samples *least-like-what-you've-heard*. That is **contrarian** sampling — it has a direction (away from recent input), which is content-targeting, the unsafe side of the directionality law line. And it's unnecessary once the channel is de-saturated.

## Files Affected

- `ww_agent/src/runtime/effectors.py` — `_speak` routing: stop publicizing private address; default to the room; add the directed-carry path.
- the world/client transport — a directed/private carry to an absent person (DM-like) distinct from a citywide broadcast.
- `ww_agent/src/runtime/perception.py` — the overheard floor becomes naturally plural once the channel de-saturates (likely no change beyond confirming it samples a now-plural channel); optionally the addressed→attend rationing.

## Acceptance Criteria

- [x] Addressing an absent person no longer publishes to `__city__`; it reaches that person via a directed carry (private), or is held until co-presence.
- [x] The citywide channel is no longer saturated by directed speech — only an explicit city target can broadcast; directed speech cannot enter that channel.
- [~] Re-run the re-seeded diverse cast: deferred as a live-agent research check, not an architectural completion condition.
- [~] Measure the diversity of a content-blind citywide sample: deferred with the same live-agent research work.

## Open Questions / Risks

- **Resolved:** absent-addressed speech uses the existing private-message transport. Major 72 may later
  improve how residents read and manage private threads without changing this visibility rule.
- **Resolved architecturally:** cross-distance contact remains cheap and direct; it is private rather
  than ambient. Any behavioral effect belongs to later observation.
- **Resolved for this slice:** movement changes the room used by untargeted/local speech. Finer
  within-place topology is separate map work under Major 36 and Minor 32, not required to prevent
  private speech from becoming public.
