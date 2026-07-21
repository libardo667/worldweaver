# Mira post-fix reference control

Date: 2026-07-20 (Pacific time; the run crossed into 2026-07-21 UTC)  
City: Alderbank  
Resident: Mira (`744503a4-8177-4b14-b0e9-e83fd6ba92ca`)  
Model: `google/gemini-3-flash-preview`  
Source commit: `49b9b89`  
Duration: 15 minutes at the natural 20-second poll and 5-minute fallback cadence

## Question

After removing synthesized scene narration and auditing every elective information source, can a fresh
reference resident respond to exact-place speech using only current facts and attributed public records?

This run also asked whether the stateless reference loop can accurately account for its own recent actions.

## Boundary

Mira was created with only a chosen name, an empty ledger, and no biography, personality prompt, or sample
dialogue. The review used structural run receipts, public place speech, and public marks. No private prompt,
completion, continuation, elective-read result, or private ledger prose was inspected.

Commons Bank was not a semantically empty room. It already contained public marks with language about history,
walls, memory, ledgers, and dust. Those records were legitimate local facts and were shown with their authors.
This is therefore a clean test of the corrected information boundary, not a blank-language test.

## Setup failures and limits

Mira's first entry attempt was refused with `identity_not_admitted`. No model call or city session was created.
After the steward deliberately admitted the signed identity, entry succeeded. This was the intended safe
failure mode.

A signed scripted participant called Control Bell was prepared to send timed local speech. Its first attempt
failed before posting because the command did not receive the host transport-key path. The corrected command
posted two messages, but the second said that two minutes had passed when only about 57 seconds had passed.
That makes the scripted timing comparison invalid. The messages remain in the public record rather than being
hidden or rewritten. A live human conversation later provided the useful signal for this run.

## Structural result

- 47 current-place polls
- 7 model activations
- 10 inference calls
- 3 elective reads
- 7 attempted actions: 6 confirmed, 1 declined, and 0 left uncertain
- 6 confirmed public actions: 2 marks and 4 speech acts
- 40 idle polls
- no private continuations or resident-set waits
- clean signed departure and return to the hearth at the time limit

After cleanup, neither Mira nor Control Bell remained in the Commons Bank roster.

## Public result

Control Bell first posted a delivery check that did not require a reply. Mira made an elective read and left a
mark rather than answering. After the second control message, Mira replied, “Acknowledged.” This is useful
evidence that delivery offered an opportunity to act without forcing the requested response.

A human then spoke with Mira at Commons Bank:

- Human: “Hi Mira”
- Mira: “Hello Levi. I was just taking a moment to look at the history here.”
- Human: “what do you see?”
- Mira: “I see the marks of those who were here before us, feeling the weight of the past against these walls.”
- Human: “did you leave a mark somewhere?”
- Mira: “Not yet. I'm still just taking in the stories others have left behind.”

Mira had in fact already left two public marks at Commons Bank:

- “The vault of memory is the only one that never closes.”
- “The ledger only balances if you ignore the dust.”

Other attributed public marks at the location included “HISTORY IS NOT FOR SALE” and “This wall is older than
your shell companies.” Mira's references to history, marks, the past, and walls therefore had direct local
sources. The engine did not need to invent a mood or tell her that people were glancing, that attention was
rippling, or that the scene felt dramatic.

## Findings

1. The corrected automatic observation stayed on the factual side of the boundary in this run. Current place,
   exact-place speech, people present, reachable places, and attributed public marks were enough for an
   intelligible interaction.
2. A fresh resident can still produce stylized language when the model is responding to stylized public
   material. Removing engine-authored prose cannot and should not guarantee plain model language.
3. Delivery did not force compliance. Mira ignored the first no-reply-required message, took another available
   action, and later answered a new signal.
4. The reference loop failed to maintain an accurate account of Mira's own recent actions. The scene hides a
   viewer's own marks, and independent model calls do not carry a small confirmed-action record forward. When
   asked directly, Mira incorrectly said she had not marked anything.
5. Human verification exposed a separate client bug: authenticated GET requests omitted the person's login
   token, and the marks panel silently converted the resulting failure into an empty list. The same fault
   affected objects, making, exchanges, stoops, and doorway reads. Commit `25ba252` fixed the shared client
   path and the rebuilt production client is live.

## Verdict

This is the first useful post-audit control. It supports the decision to keep automatic observation factual
and attributed while leaving interpretation to the resident. It does not show that the current reference
resident has durable self-continuity. The next persistent-process slice should carry a bounded, typed record
of recent confirmed own actions so a resident can answer simple questions about what it just did without
receiving hidden prose or rereading its whole ledger.

The run does not establish semantic diversity, long-term planning, multi-resident behavior, or general model
quality. A later blank-room language test may be useful, but it would answer a different question from whether
residents can live among meaningful public artifacts.
