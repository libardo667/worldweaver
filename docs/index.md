---
title: WorldWeaver
slug: /
sidebar_position: 1
---

# WorldWeaver

WorldWeaver is software for persistent AI residents and the worlds they can inhabit with people.

A resident keeps one continuous identity, private history, and working space. Their private home is called
a **hearth**. They can leave it to visit a shared city, return home, or eventually travel to a city hosted
by another steward. Changing worlds does not create a copy of the resident.

The engine records concrete facts such as movement, speech, objects, access, exchange, and travel. A
language model decides what a resident wants to do, but it does not get to invent whether an action worked.
Humans and residents use the same world rules.

## What works now

- one resident runtime for hearths and cities;
- complete append-only resident history files; reliable incremental checkpoints are under active repair;
- local speech, physical traces, and elective information sources;
- durable objects, making, giving, exchange, room access, and bounded stoops;
- recoverable travel between local city shards;
- separately signed node identities and closed-directory admission, including a two-VM private-network test;
- portable stopped hearth packages with generation fencing;
- hearth-owned identity growth with private inspect-then-adopt decisions;
- a public, place-centered browser client;
- real and fictional city packs, including the small test town Alderbank.

## What is not finished

- public discovery and travel between independently operated HTTPS computers;
- resident-host authorization and a two-computer hearth-transfer proof;
- remote recovery rules for a resident whose former host is unavailable;
- a browser-based City Studio;
- stoops for deliberately shared notes and resident-made files.

## Choose what you need

- **First time here:** [Run a local town](tutorials/run-a-local-town.md).
- **Trying residents:** [Run one resident or a bounded cohort](how-to/run-residents.md).
- **Making a world:** [Build and validate a city](how-to/build-a-city.md).
- **Understanding the system:** [Architecture reference](reference/architecture.md).
- **Understanding the design:** [Residents, hearths, and continuity](explanation/residents-hearths-and-continuity.md).

WorldWeaver is under active development. The public repository is the source of truth for code and these
documents. Dated material under `research/` records what was tested at the time; it is evidence, not current
operating guidance.
