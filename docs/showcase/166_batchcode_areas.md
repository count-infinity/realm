# 166. Batchcode areas

> Checklist item 166 — [now] — *area files, @export/@import plan-apply, @foreach bulk edits, packs*

**What you'll build:** a two-room zone built in-game, mass-edited with
one `@foreach`, exported to a version-controllable **area file**, edited
in a text editor, and re-installed with `@import`'s Terraform-style
plan/apply cycle. (Builder permission throughout — these are the OLC
world-authoring commands.)

**Concepts:** REALM's world-file workflow — `@zone`, `@foreach` bulk
operations, `@export` to `data/areas/<zone>.realm`, `@import` **plan**
→ `@import/apply`, stable-id sync, and how packs ship the same files as
bundles.

## How it works

Evennia's "batchcode" is a Python file the server runs to build a world.
REALM's equivalent is **softcode-first** and needs no second language,
because a REALM world is already data: rooms, exits, NPCs, their
triggers, locks, and attributes all round-trip through JSON. Two moves
cover the whole batch-building story.

**Bulk edits live in `@foreach`.** `@foreach <search> = <command>` runs
one builder command for every matching object, substituting each match's
`#id` for `%o`. Search by `tag:`, `attr:`, or name. Tag your rooms into
a zone and a single line stamps them all — no clicking through fifty
rooms to flip one flag.

**Areas are files, sync is a plan.** `@export <zone>` writes every room
tagged `zone:<zone>`, their contents, and the zone's masters to
`data/areas/<zone>.realm` — a JSON worldio file where each object carries
its `attrs`. `@import <zone>` is **Terraform-style**: it prints a *plan*
(a dry-run diff of file against world, matched by stable object id) and
changes nothing; `@import/apply <zone>` executes it. You must control
every object the plan would touch; world objects not in the file are
reported as orphans, never auto-deleted. So the area file is a source of
truth you keep in version control: export after in-game edits, import
after file edits, and the plan keeps the two honest.

Packs are the same mechanism shipped as a folder — a manifest plus
worldio files. `@pack` lists the built-ins (`gurps-scifi` ships with the
engine); `@pack <name>` imports one whole.

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

One bulk edit over the zone — stamp every `keep` room at once
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

`Exported 2 objects to areas/keep.realm.` Ask for a plan — against the
unchanged world it reports nothing to do:

```text
@import keep
```

Now open `data/areas/keep.realm` in your editor, find the Gatehouse
entry, and add a key to its `attrs`:

```json
  "motto": "None shall pass."
```

Back in game, the plan shows exactly one change; `@import/apply` commits
it:

```text
@import keep
@import/apply keep
```

```text
Plan for area 'keep':
  ~ update   Gatehouse   (attrs (motto))
  0 to create, 1 to update, 0 orphaned, 0 conflicts.
```

The Gatehouse answers to its new attribute immediately — no restart, no
reload.

## Try it

- `@foreach tag:zone:keep = @set %o/patrolled = true` then
  `@examine Gatehouse` — the flag is on both rooms.
- Delete `keep.realm`'s Barracks entry and `@import keep` — the plan
  reports it as an **orphan** (in the world, not in the file) and leaves
  it in place; import never deletes.
- Edit a room in-game *after* exporting, then `@import` — if the file
  and world both changed the same object, the plan flags a **conflict**
  instead of clobbering; re-export, merge, apply.

## Going further

- **Whole quarters travel:** the same flow moves entire zones between
  worlds — rooms, exits, NPCs, triggers, locks — which is how the bigger
  showcase builds ship. See [response scripting in data](241_yaml_responses.md)
  for NPC repertoires carried the same way.
- **Bulk by attribute:** `@foreach attr:patrolled = @behavior %o =
  script_ticker, interval:30` animates every flagged room in one line.
- **Ship a pack:** wrap your area files in a directory with a `pack.json`
  manifest and any REALM game can `@pack` it — the content-packs guide
  covers the manifest.
- **CLI drive:** the same worldio files import from the command line for
  CI/seed workflows — see [CSV world import](173_csv_import.md) for the
  external-source angle.
