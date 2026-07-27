# 166. Batchcode areas

> Checklist item 166 ([now]): *area files, @export/@import plan-apply, @foreach bulk edits, packs*

**What you'll build:** a two-room zone built in-game, mass-edited with
one `@foreach`, exported to a version-controllable area file, edited in a
text editor, and re-installed with `@import`'s Terraform-style plan/apply
cycle. Builder permission carries throughout, since these are the OLC
world-authoring commands.

**Concepts:** REALM's world-file workflow: [zones](../reference/softcode.md#tags-zones),
`@foreach` bulk operations, `@export` to `data/areas/<zone>.realm`,
`@import` plan then `@import/apply`, stable-id sync, and how packs ship
the same files as bundles.

## How it works

The finished workflow is a loop: build a zone in-game, stamp it with one
bulk edit, freeze it to a file you can commit, edit that file in your
editor, and fold the edits back in through a reviewed plan. This section
answers the two questions that loop rests on: how one command edits many
objects, and how a file and the live world stay in sync.

Evennia's "batchcode" is a Python file the server runs to build a world.
REALM reaches the same goal without a second language, because a REALM
world is already data: rooms, exits, NPCs, their triggers, locks, and
attributes all round-trip through JSON. Two moves cover the whole
batch-building story, `@foreach` for bulk edits and the `@export`/`@import`
file cycle for versioned areas.

**Bulk edits live in `@foreach`.** `@foreach <search> = <command>` runs
one builder command for every matching object, substituting each match's
`#id` for `%o`. Search by `tag:`, `attr:`, or name. Tag your rooms into a
zone and a single line stamps them all, with no clicking through fifty
rooms to flip one flag.

**Areas are files, and sync is a plan.** `@export <zone>` writes every
room tagged `zone:<zone>`, their contents, and the zone's masters to
`data/areas/<zone>.realm`, a JSON worldio file where each object carries
its `attrs`. Because a room's exits and objects are its contents, they
travel with the room, so a two-room zone holding three exits exports as
five objects. `@import <zone>` is Terraform-style: it prints a *plan* (a
dry-run diff of file against world, matched by stable object id) and
changes nothing, while `@import/apply <zone>` executes it. You must control
every object the plan would touch, and world objects not in the file are
reported as orphans, never auto-deleted. So the area file is a source of
truth you keep in version control: export after in-game edits, import
after file edits, and the plan keeps the two honest.

Packs are the same mechanism shipped as a folder, a manifest plus worldio
files. `@pack` lists the built-ins (`gurps-scifi` ships with the engine),
and `@pack <name>` imports one whole. See [JSON content packs](235_content_packs.md)
for the pack side of this story.

## Build it

Dig two rooms and tag them into a zone (the exporter takes whatever
carries the tag):

```text
@dig Gatehouse = gate, back
gate
@zone here = keep
@dig Barracks = barracks, out
barracks
@zone here = keep
out
```

One bulk edit over the zone stamps every `keep` room at once
(`%o` becomes each room's `#id`):

```text
@foreach tag:zone:keep = @set %o/patrolled = true
```

Both rooms now carry `patrolled = true`. Capture the zone as a file and
list what's installable:

```text
@export keep
@areas
```

The export reports `Exported 5 objects to areas/keep.realm.`: the two
rooms plus the three exits that live inside them. Ask for a plan, and
against the unchanged world it reports nothing to do:

```text
@import keep
```

Now open `data/areas/keep.realm` in your editor, find the Gatehouse
entry, and add a key to its `attrs`:

```json
  "motto": "None shall pass."
```

Back in game, the plan shows exactly one change, and `@import/apply`
commits it:

```text
@import keep
@import/apply keep
```

The first of those prints the plan:

```
Plan for area 'keep':
  ~ update   Gatehouse   (attrs (motto))
  0 to create, 1 to update, 0 orphaned, 0 conflicts.
```

The Gatehouse answers to its new attribute immediately, with no restart
and no reload.

## Try it

Confirm the bulk edit reached both rooms, then examine either one:

```
> @foreach tag:zone:keep = @set %o/patrolled = true
Set Gatehouse/patrolled = True
Set Barracks/patrolled = True
Ran '@set %o/patrolled = true' for 2 object(s).

> @examine Barracks
Tags: room, zone:keep

Attributes:
  patrolled: True
```

Two file-edit variations round out the workflow:

- Delete `keep.realm`'s Barracks entry and `@import keep`: the plan
  reports Barracks as an **orphan** (in the world, not in the file) and
  leaves it in place, because import never deletes.
- The plan flags a **conflict** and refuses an object when the file gives
  it a friendly `keyid` that another live object already holds, or when
  the plan would touch an object you do not control. Absent a conflict the
  file is the source of truth, so `@import/apply` makes the world match the
  file. Re-export after in-game edits to fold them into the file before you
  edit and re-import.

## Going further

- **Whole quarters travel:** the same flow moves entire zones between
  worlds (rooms, exits, NPCs, triggers, locks), which is how the bigger
  showcase builds ship. See [response scripting in data](241_yaml_responses.md)
  for NPC repertoires carried the same way.
- **Bulk by attribute:** `@foreach attr:patrolled = @behavior %o =
  script_ticker, interval:30` animates every flagged room in one line.
- **Ship a pack:** wrap your area files in a directory with a `pack.json`
  manifest and any REALM game can `@pack` it. The
  [content packs guide](../guides/content-packs.md) covers the manifest.
- **CLI drive:** the same worldio files import from the command line for
  CI and seed workflows. See [CSV world import](173_csv_import.md) for the
  external-source angle.
