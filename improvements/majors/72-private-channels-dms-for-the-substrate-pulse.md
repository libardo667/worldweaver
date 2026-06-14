# Private channels (DMs) reborn for the substrate + pulse

## Decision and lineage

DMs exist in the world only as a **fossil of the demoted "mail loop."** The Major 49 rebuild took the old
four loops — fast / slow / **mail** / wander — and demoted them to pure sensorimotor mechanism beneath the
salience-pulse. The proactive-DM behavior lived in the mail loop's slow/fast interplay (roughly: *resident
talks about an absent person → the loop polls "send them a message?" → confirm → send*), and the rebuild
removed that **trigger**. What survived is an orphan: residents still `GET /api/world/dm/inbox/<name>`
every perceive, but nothing sends — an inbox poll for a mailbox nothing can fill.

This major brings private channels back, **re-architected to the pulse model** rather than restored as the
loop-era poll: a DM becomes (1) a **deliberate pulse ACT** — a private, directed message the resident
*chooses* to send to a named peer — and (2) a **first-class PERCEPT** — a received DM feeds `perceive` →
salience → can ignite a reply. Send → perceive → reply, all inside the one pulse cycle; no second loop.

- **Closes/supersedes:** the loop-era mail mechanism (now dead-code-by-trigger; the inbox-read orphan).
- **Coordinates with:** Major 60 (chosen-vs-unchosen / locality — a DM is the *private* channel; "don't
  publicize a private address" means directed-to-a-person speech should be private by default, not the
  citywide megaphone); Major 65 (tools/acts the world affords — DM-send is such a verb); Major 66 (log
  edges — a DM is a directed `sender→recipient` edge with `in_reply_to` + a `private` flag). The
  `effectors.py` "address an absent person → carry as a letter" path is the partial send-path to formalize.
- **Status:** proposed (2026-06-09, operator's call), sparked by finding the vestigial inbox-poll while
  inspecting the pen-vs-substrate KEEP recording. **Parked — do NOT implement during the pen-vs-substrate
  run** (it would change the cohort's behavior mid-experiment).

## Problem (evidence)

Matured `ww_pdx_grow` D2 cohort channel mix: **local room chat 1020, city broadcast 263, DM 0.** The KEEP
recording shows `dm/inbox` GETs every perceive but **`speech_carried` = 0** — polled-but-empty by
construction. Two compounding causes: (a) the send-*trigger* was removed with the mail loop; (b) the live
`effectors.py` directed-carry→letter path rarely fires because the clustered cohort is almost always
co-present, so addressed speech routes to local chat. A resident has no way to deliberately reach an absent
peer privately, and received DMs are never perceived as salient.

## Shape (sketch, to be designed)

- **SEND = a deliberate pulse act.** Let the pulse choose *private-directed* vs *local-room* vs *citywide*
  for an addressed utterance (today private-vs-local is an accident of co-presence, not a choice). Reuse the
  `send_letter` path; provenance-tag the act `private, directed`.
- **PERCEIVE = received DMs as real percepts.** Wire the `dm/inbox` read into `perceive` so a received DM
  enters the `heard` set (flagged private) → contributes surprise/salience → can ignite a reply pulse with
  `in_reply_to` the DM. This is what closes the loop without a second loop.
- **SALIENCE/affect.** A DM from a *kept* peer is inherently high-salience (private, aimed at you); let the
  drive/salience reflect that. Grief/coupling-safe: no behavior target, no reward gradient.
- **Locality/safety (Major 60 spine).** DMs are private *by construction* — the deliberate private channel
  that "don't publicize a private address" calls for. Content-blind world-slices stay public; DMs never
  broadcast. DF-legal.
- **Edges (Major 66).** Log each DM as a directed edge (`perceived_by`, `in_reply_to`, `private=true`) so
  the relational ledger and reciprocity metrics see the private channel, not just the public ones.

## Falsifier / when it's NOT worth it

Pre-register before building (brief discipline): does a private channel add relational signal *beyond*
local chat, or just **relocate** convergence into a private monoculture (the Major 60 "swapping a template"
trap)? Run a null. Note DMs only matter under a **scattered/cross-cluster topology** — in a tightly
clustered cohort everyone's co-present and the channel rarely fires, so this pairs with the topology lever;
on its own, against a clustered cast, it may show ~nothing (which is itself the result).

## Not now

Parked behind the pen-vs-substrate experiment. Could scope down to a MINOR if the `send_letter` reuse +
inbox-as-percept turns out to be the whole job; promoted to MAJOR here because it touches the pulse
contract, perception, and the locality/privacy spine at once.
