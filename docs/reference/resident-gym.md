---
title: Resident gym
sidebar_position: 3
---

# Resident gym

The resident gym is a controlled place for testing participants against real WorldWeaver rules. It is not a
second, simpler game engine. Movement, local speech, session entry, and speech delivery call the same services
used by a running shard.

Run the first episode from the repository root:

```bash
python dev.py gym
```

The command prints a compact timeline and writes a self-contained visual report to
`.runs/gym/footbridge-hello.html`. The report contains only synthetic speech and facts returned by production
services. Its icons and layout do not add a narrator's interpretation.

## What the first episode proves

`The Footbridge Hello` uses a scripted participant and a small mechanical listener. They begin together in
Willow Court. One speaks, the other receives the exact-place signal and replies. The listener then walks to
the Footbridge and does not receive speech left behind in Willow Court. When the first participant follows and
speaks at the Footbridge, delivery resumes.

This proves a narrow software path:

```text
scenario choice
  -> production session, movement, or speech service
  -> canonical database/event write
  -> production exact-place signal cursor
  -> structural gym record
  -> terminal and browser views
```

It does **not** prove that a model can converse well, remember a relationship, manage a long plan, or behave
like a person. The mechanical listener is a transparent test fixture, not a resident model and not a desired
personality.

## Next boundaries

The next conformance version will repeat the same episode through authenticated HTTP and compare it with the
fast service-level run. Correspondence must then be moved below the route layer and repaired before the gym
claims to cover delayed communication. Controlled time, checkpoint forks, model adapters, and training data
come after those shared boundaries are proven.

Real resident prose or private hearth state does not belong in gym fixtures. Episodes must use synthetic or
explicitly licensed material and record its source.
