We have reached the biggest one: [30-build-api-first-web-client-v1.md](improvements/majors/30-build-api-first-web-client-v1.md) I want you to iterate on this task repeatedly for each subitem in the [ROADMAP.md](improvements/ROADMAP.md) , step 14, of the interated execution order.

Please review improvements/ROADMAP.md and improvements/VISION.md.

Then do the next unfinished item in the “Integrated Execution Order (Recommended)” list:
- Identify the first item that is not marked complete.
- Open the corresponding improvement doc (major or minor) and follow it exactly.

Rules:
- Keep API behavior stable unless the improvement explicitly changes it.
- Do not do drive-by refactors, formatting passes, or dependency upgrades unless required.
- Prefer small commits. Keep diffs focused.

Workflow:
1) Create a working branch named: chore/<improvement-slug>
2) Implement the improvement.
3) Run tests:
   - python -m pytest -q 
   - plus any extra commands listed in the improvement’s acceptance criteria
4) Verify every Acceptance Criteria checkbox is satisfied.
5) Update the improvement doc:
   - Mark acceptance criteria complete (check all boxes).
   - Move the improvement file to the correct archive folder.
6) Update improvements/ROADMAP.md:
   - Cross off the step in the Integrated Execution Order
   - If you created follow-up work, add it as a new minor improvement doc (not inline notes)
7) Git:
   - git add -A
   - git commit -m "<improvement-id>: <short meaningful summary>"
   - git push

When done, output:
- A brief summary of what changed
- The commands you ran and their results
- A short list of files changed
- Any known limitations or next recommended step

If you cannot satisfy an acceptance criteria:
- Stop, explain what blocks you, and propose the smallest next-step fix as a NEW minor improvement doc.
Do not archive the improvement until all criteria are met.