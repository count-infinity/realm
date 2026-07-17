# 173. CSV world import

> Checklist item 173 — [now] — *validate-then-apply, idempotent via external-id tags, a shipped sample CSV*

**What you'll build:** an importer that turns spreadsheet rows into rooms
— validate first, apply on the word `apply`, and re-run safely because
every row carries a stable **external id** so a second import *updates*
instead of duplicating. A sample CSV ships alongside this tutorial.
(Builder permission: the importer is a builder tool that creates world.)

**Concepts:** rows as data, **validate-then-apply**, **idempotency** via
`extid:<key>` tags (`search_world` finds the prior import), and where the
in-game path meets the file-driven CLI/area workflow.

## How it works

**A spreadsheet is a table; a room is a row.** Give each row an external
id, a name, and a description — `extid,name,description` — and importing
is: for each row, find the room already tagged `extid:<key>`; update it
if it exists, create it (tagged with that key) if it doesn't. The shipped
[`building_tools_rooms.csv`](building_tools_rooms.csv) is the canonical
source; in-game you hand the importer the rows and it does the rest.

**Validate, then apply.** A bad batch should fail *before* it half-builds
a world. So the importer parses every row first and refuses the whole
run if any row has the wrong column count — you fix the sheet and re-run.
With `apply` it creates/updates; without it, it just previews ("would
import ..."), the same [dry-run discipline](169_zone_mass_edit.md) the
zone editor uses.

**External ids make it idempotent.** The `extid:<key>` tag is the join
key between the sheet and the world. Because every row is matched on it,
importing the same file twice is a no-op-or-update, never a duplicate —
the same stable-id promise the [area importer](166_batchcode_areas.md)
makes, expressed as a tag. That's what makes a CSV a *source you re-sync*,
not a one-shot paste.

**Getting the rows in.** Softcode can't read files and `@set` takes one
line, so in-game you paste the sheet as a JSON list of CSV-line strings
(one `@set`), and the importer splits each on commas — genuine CSV
parsing and validation, driven from data you can regenerate from the
`.csv`. For file-driven, unattended loads, the same rooms travel as an
[area file](166_batchcode_areas.md) via `@import` or the `realm` CLI;
this in-game path proves the create/validate/idempotent semantics.

## Build it

The importer, its rows (pasted from the sheet as JSON), and the verb:

```text
@create room importer
drop room importer
@set room importer/rows = ["r1,Guardroom,Spears line the wall.", "r2,Armory,Racks of dented steel."]
@set room importer/cmd_csv = $csv *: mode = trim(arg0); rows = V('rows', []); parsed = [[c.strip() for c in row.split(',')] for row in rows]; bad = [p for p in parsed if len(p) != 3]; pemit(enactor, 'VALIDATION FAILED: ' + str(len(bad)) + ' malformed row(s); fix them first.') if bad else None; [(set_attr(hit[0], 'desc_extras', [['', p[2]]]) if hit else set_attr(create_obj(p[1], tags=['room', 'extid:' + p[0]]), 'desc_extras', [['', p[2]]]), pemit(enactor, '  ' + ('updated ' if hit else 'created ') + p[1])) for p in parsed if not bad and mode == 'apply' for hit in [search_world(tag='extid:' + p[0])]]; [pemit(enactor, '  would import ' + p[1] + ' (extid ' + p[0] + ')') for p in parsed if not bad and mode != 'apply']
```

## Try it

Preview, then commit:

```text
csv check
  would import Guardroom (extid r1)
  would import Armory (extid r2)
csv apply
  created Guardroom
  created Armory
```

Run `csv apply` **again** — the rooms already carry their `extid:` tags,
so this time:

```text
csv apply
  updated Guardroom
  updated Armory
```

One Guardroom, not two — idempotent. Edit a description in the sheet,
re-paste the `rows`, and `csv apply` syncs it in place. A malformed batch
is refused whole:

```text
@set room importer/rows = ["r1,Ok,fine", "junk"]
csv apply
  VALIDATION FAILED: 1 malformed row(s); fix them first.
```

Nothing is created — validate-then-apply kept a broken sheet from
half-building your world.

## Going further

- **More columns:** extend the tuple to `extid,name,description,zone` and
  `add_tag(room, 'zone:' + p[3])` so the sheet places rooms into areas —
  then [export the zone](166_batchcode_areas.md) to a file.
- **Exits from a second sheet:** an `exits.csv` of `from_extid,dir,to_extid`
  rows, imported after the rooms, `create_obj`s the links — matched by the
  same external ids.
- **File-driven:** keep the `.csv` under version control and generate the
  `rows` JSON (or an area file) from it in a build step; the CLI importer
  loads it unattended for seeding and CI.
- **Delete detection:** compare `search_world(tag='extid:...')` against
  the sheet's keys and report rooms whose row vanished — the orphan half
  of a sync, echoed like the [world audit](172_world_audit.md).
