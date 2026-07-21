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

Run the delayed-correspondence episode:

```bash
python dev.py gym --episode waiting-letter
```

Each command prints a compact timeline and writes a self-contained visual report under `.runs/gym/`
(`footbridge-hello.html` or `waiting-letter.html`). The reports contain only synthetic speech and facts returned
by production services. Their icons and layout do not add a narrator's interpretation.

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

## HTTP conformance

An automated conformance test repeats the episode through FastAPI with two separately registered human actors.
It proves that anonymous access is refused, supplies each actor's bearer token, and compares the resulting
chat rows, world events, and final locations with the fast service-level episode. They match. This is an
in-process HTTP proof, not a container or public-network test.

## What the correspondence episode proves

`The Waiting Letter` sends private mail through the production correspondence service. Ivo's temporary session
ends after Mara sends the letter, and Ivo returns under a new session with the same durable actor ID. The letter
is offered twice without being consumed, then explicitly acknowledged, after which the pending mailbox is
empty. The browser report shows this as a small animated post trail. The envelope animation is only a key for
the recorded states.

The current reference resident loop follows the same rule: pending mail is included in a model activation and
acknowledged only after a valid final decision. A failed inference leaves the message pending. Runtime evidence
stores message IDs and counts, not the private message body. New mail can wake the resident when its chosen
private-activity policy allows correspondence interruptions.

The correspondence API requires exact human or signed-resident proof and addresses durable actor IDs. The old
name- and session-addressed DM routes now return `410 Gone` rather than guess or accept an unauthenticated
sender. This slice is local to one shard. Federated delivery, a public human correspondence interface,
controlled time, checkpoint forks, model adapters, and training data remain later work.

Real resident prose or private hearth state does not belong in gym fixtures. Episodes must use synthetic or
explicitly licensed material and record its source.
