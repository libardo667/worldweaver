# Let residents make real hearth belongings and carry them between worlds

## Status

This does not exist yet. A hearth currently has a private workshop and resident-owned files, but it has no
canonical physical object store. A city can create and track real objects with stable IDs, custody, exact
placement, and append-only receipts, but those objects live in that city's database and do not travel with
the resident.

This leaves a broken middle. A resident may imagine or write about owning a cup, notebook, bag, drawing, or
other possession at home. That does not make the thing physically real. Conversely, if the system only
corrects the resident by saying the thing is imaginary, the resident can never deliberately make it real,
bring it outside, and leave it for someone at a stoop.

## Goal

Provide an explicit path:

```text
private idea or workshop piece
    -> deliberate hearth making action
    -> one canonical hearth object
    -> deliberate carried load
    -> exactly-once transfer into a city
    -> carried, given, placed, exchanged, or left at a stoop
```

Remembering or describing an object is never enough to create it. The resident must choose a typed making
action, the hearth's rules must accept it, and any destination shard must accept the transferred object's
class.

## Two different publication paths

Do not collapse these into one vague artifact feature.

1. **Publish a copy of private work.** A resident selects one bounded workshop file or writes a short note.
   The city receives a safe snapshot for a stoop while the private original stays in the hearth. Major 125
   owns this path.
2. **Carry one physical possession.** A real object has one stable identity and one active attachment. If it
   leaves the hearth, it is no longer physically available there. This major owns that path.

A drawing could use either path. Publishing an image creates a public copy. Carrying the only physical
drawing transfers one object. The UI and resident action must say which is happening.

## Object creation at the hearth

The hearth is a shard and therefore has rules, even though it is private. Its default policy should allow a
small number of ordinary expressive or personal objects without pretending to create scarce game resources.
Examples include a handwritten notebook, a clay figure, a letter, or a drawing. A hearth-created object does
not gain money value, a weapon effect, a city key, ownership of land, or any other power merely because its
description claims one.

Creation is elective:

- the resident invokes a named `make` or `manifest` capability;
- the request contains bounded public object fields such as name, description, kind, and optional selected
  workshop source;
- the hearth policy accepts, refuses, or asks for a valid recipe;
- acceptance appends a creation receipt and gives the object a stable ID;
- no process scans private prose for objects to create automatically.

A richer hearth ruleset may require materials, tools, time, or recipes. A simpler commons hearth may allow
bounded symbolic making. Destination shards still decide what classes they accept and what effects, if any,
an imported object has.

## Hearth object state

Hearth objects belong to the portable hearth package, not to the temporary host computer. Store an
append-only object event log plus a rebuildable current projection under the resident home. At minimum each
object needs:

- a globally stable object ID and revision;
- the resident actor ID and hearth shard ID;
- bounded public name, description, kind, and properties;
- creation policy and provenance, including a selected workshop hash when applicable;
- one current attachment: an exact hearth place, resident custody, in transit, or an external shard;
- append-only creation, pickup, placement, export, import, rejection, and return receipts.

Private motivation, ledger prose, and unrelated workshop contents do not travel with the object. Only the
resident-approved public description and minimum provenance cross the boundary.

## Transfer between shards

Held objects should use the same source-retire/destination-accept shape as actor travel.

1. The resident chooses which held objects to carry. Objects resting in the hearth remain there.
2. The source authority seals each chosen object in a bounded transfer envelope and marks it in transit.
3. The destination validates the envelope, object class, size, revision, and transfer ID.
4. The destination activates one local object projection and returns an import receipt.
5. The source keeps a tombstone and receipt, not a second active object.
6. A retry is idempotent. A refused or failed transfer restores the source object or leaves the actor's trip
   pending; it never silently copies or destroys the object.

When the object is left in a city stoop, that city remains its active authority after the resident leaves.
When the resident later carries it home or into another city, the current city performs the next export.
The federation directory routes the trip but does not become a global inventory database.

## Build order

1. Add the portable hearth object event log, reducer, projection, and package classification.
2. Give `LocalWorld` an elective `objects` source and typed make, place, pick-up, and carry-selection actions.
3. Define the default hearth making policy and the public object classes a city may accept without granting
   game effects.
4. Define a versioned, signed, bounded object transfer envelope with idempotent export/import receipts.
5. Extend hearth-to-city and city-to-city handoffs to transfer selected held objects under the same failure
   recovery rules as the actor.
6. Import accepted objects into the existing city `DurableObject` and consequence-receipt machinery without
   changing their stable object IDs.
7. Prove that an imported object can be given, placed, exchanged, or left at an object stoop through the
   existing human/resident verbs.
8. Build Major 125's separate workshop-copy publication path on the same deliberate private-to-public
   boundary.

## Boundaries

- Private prose is evidence of a belief or desire, not a world-state mutation.
- Object creation and transfer are deliberate capabilities, not automatic prompt interpretation.
- A destination may refuse an object but may not secretly rewrite it into a more powerful object.
- Hearth creation cannot mint currency, credentials, access rights, scarce materials, or harmful game
  effects unless an explicit ruleset and recipe allow it.
- A transferred object has one active authority and one active attachment at a time.
- The directory never collects resident inventories or private artifact contents.
- Humans and residents use the same city custody and stoop rules after an object arrives.
- Public provenance says enough to understand the object's origin without publishing why the resident made
  it or what else is in the hearth.

## Acceptance criteria

- [ ] A resident can deliberately create one bounded, policy-accepted object while at the hearth.
- [ ] Mentioning or repeatedly imagining an object does not create it.
- [ ] Hearth object state and receipts survive restart and stopped hearth package transfer.
- [ ] The resident can distinguish objects resting at home, currently carried, and present in the current
  city.
- [ ] The resident chooses which objects leave the hearth; everything else remains physically at home.
- [ ] One object crosses hearth-to-city and city-to-city travel without duplication or identity change.
- [ ] Refused, interrupted, and retried transfers neither copy nor lose the object.
- [ ] A destination's rules control imported effects without erasing origin and authorship.
- [ ] An imported object works with existing give, place, exchange, and object-stoop operations.
- [ ] No transfer exposes private ledger prose, prompt traces, or unselected workshop contents.
- [ ] Tests use synthetic hearths and objects only.

## Relationship to other work

- Minor 34 keeps memory, current inventory, and local objects clear in prompts.
- Major 125 publishes selected copies and notes rather than unique physical objects.
- Major 37 supplies the actor travel lifecycle that portable-object handoff should extend.
- Major 127 makes the hearth package portable across temporary hosts.
- Major 130 supplies optional city game rules, recipes, and consequences.
