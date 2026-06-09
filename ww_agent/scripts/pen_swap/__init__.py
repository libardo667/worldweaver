"""Pen-vs-substrate perception-replay harness (research tooling).

Records a resident cohort's exact per-tick perception during a live run (KEEP),
then replays that byte-identical experience into copies running on a different
runtime LLM ("the pen") — measuring whether a swapped pen, given an identical
life, keeps different memories and forms different relationships.

Record/replay happens at the world-client HTTP choke points (`_get`,
`_get_with_retry`, `_post`), so on replay the real `perceive()` genuinely runs
(its substrate side-effects are preserved) and nothing in the production path
changes. See DESIGN.md.
"""
