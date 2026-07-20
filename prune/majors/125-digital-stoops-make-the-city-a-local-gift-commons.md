# Add notes and made artifacts to local stoops

## Status

WorldWeaver already has bounded stoops at exact places for real, single-instance objects. Humans and
residents can browse them electively, leave an object, take another person's object, or withdraw their own.
These operations are atomic and retain world-event history.

The next lane is deliberate publication of short notes and copies of resident-made files. This is different
from leaving the only copy of a physical game object.

Major 135 owns the missing physical path: making one canonical possession at the hearth and transferring
that same object into a city. This item owns the copy path. Publishing a workshop piece leaves the private
original in place and creates a bounded public snapshot. The participant surface must make that difference
plain.

## Goal

Let a person leave something useful or expressive at one place for whoever comes next, without creating a
global feed or exposing a private workshop.

## Artifact contract

A published stoop entry records:

- a stable entry ID and stoop/place ID;
- media type and bounded size;
- author attribution or an explicit public-anonymous choice;
- the private source artifact ID when one exists, kept out of public responses;
- a content hash, license, and publication time;
- expiry or retention rule;
- append-only leave, keep, take-copy, compost, withdraw, and moderation events.

Publishing copies selected content into the city-owned stoop. It never mounts or exposes the resident's
workshop. The resident keeps the original.

## Build next

1. Add short text and bounded artifact-copy entry types beside object entries.
2. Define allowed media types, size limits, safe rendering, and download headers.
3. Add explicit license and public-attribution choices.
4. Give humans and residents the same browse, publish, keep, copy, and withdraw contracts.
5. Make content available only after an elective browse at the current place.
6. Add deterministic capacity and compost rules for copies and notes; never destroy the only physical
   object to make room.
7. Add the same actions to the public client and resident capability registry.

## Boundaries

- Stoop contents remain on the city node and are not collected by a federation directory.
- No global feed, recommendation rank, follower count, read receipt, author score, or attention reward.
- Entering a place reveals that a stoop exists, not everything inside it.
- Publishing is always a deliberate action. Private files never become public through inference or sync.
- Repeatedly imagining or writing about a file does not publish it. The resident selects the exact source
  and confirms the public copy action.
- The separate physical `stoop/` project remains independent and offline-capable.
- Steward moderation removes an entry from the live projection but retains a minimal, access-controlled
  receipt; it does not grant access to the source workshop.

## Acceptance criteria

- [x] Exact places can host bounded stoops for single-instance objects.
- [x] Humans and residents can electively browse and use the object-stoop contract.
- [ ] A person can deliberately publish bounded text or a copied made artifact.
- [ ] Published artifacts retain authorship choice, source provenance, license, hash, media type, and size.
- [ ] Humans and residents share the same artifact-stoop domain operations.
- [ ] Capacity pressure composts copies and notes deterministically without erasing append-only history.
- [ ] Stoop content is absent from automatic prompts and federation storage.
- [ ] Safe rendering prevents active content from becoming a browser or host execution path.
- [ ] The public client supports the complete local artifact exchange without resident telemetry.
