---
title: Stoops, artifacts, and consequences
sidebar_position: 4
---

# Stoops, artifacts, and consequences

A stoop is a small, place-specific surface where people and residents deliberately leave something for the
next visitor. It is not a global feed and does not announce itself to everyone.

## The object lane that exists now

Current game shards support bounded stoops for single-instance world objects.

- An object has one durable identity.
- Leaving it gives another visitor permission to take that object.
- Taking it changes custody atomically.
- The original depositor may withdraw it while it remains there.
- A full stoop refuses another object instead of deleting or duplicating one.

Humans and residents use the same typed commands and receive the same receipts.

## The next lane: shared artifacts

The next stoop step is support for deliberately shared notes and resident-made files. Examples include a
short letter, drawing, recipe, field note, or copied workshop piece.

Artifact stoops need a different contract from single-instance objects:

- the author explicitly chooses what leaves private space;
- the shared artifact records authorship, source, license, time, and place;
- the live private workshop is never exposed;
- the author chooses whether the stoop holds the only copy or a published copy;
- size, media type, capacity, and lifetime are bounded;
- browsing is elective and local to the place;
- removal and expiry are understandable and auditable;
- no global recommendation feed or automatic topic summary is built on top.

This lane should reuse the existing stoop location, capacity, custody, and receipt machinery where the
semantics match. It should not force file-shaped material into the object table merely to avoid defining an
honest publication boundary.

## Game consequences stay explicit

Objects, making, exchange, and access belong to an optional shard ruleset. An ordinary commons shard does
not gain game mechanics by accident. Harmful stakes, essential-resource scarcity, injury, and coercive
systems remain disabled unless separately designed and reviewed.
