# 173. CSV world import

> Checklist item 173 ([now]): *validate-then-apply, idempotent via external-id tags, a shipped sample CSV*

**What you'll build:** an importer that turns spreadsheet rows into rooms. It
validates first, applies only on the word `apply`, and re-runs safely because
every row carries a stable **external id**, so a second import *updates* the
rooms instead of duplicating them. A sample CSV ships alongside this tutorial.
(Builder permission: the importer is a builder tool that creates world.)

**Concepts:** rows as data, **validate-then-apply**, **idempotency** via
`extid:<key>` tags ([`search_world`](../reference/softcode.md#fn-search_world)
finds the prior import), and where the in-game path meets the file-driven
CLI/area workflow.

## How it works

A spreadsheet is a table and a room is a row. Give each row an external id, a
name, and a description (the columns `extid,name,description`), and importing
becomes a simple rule: for each row, find the room already tagged
`extid:<key>`, update it if one exists, and create it (tagged with that key) if
none does. The shipped [`building_tools_rooms.csv`](building_tools_rooms.csv)
is the canonical source, and in-game you hand the importer the rows so it does
the rest.

### Why validate before applying?

A bad batch should fail before it half-builds a world, so the importer parses
every row first and refuses the whole run if any row has the wrong column
count, which means you fix the sheet and re-run. With `apply` it creates and
updates; without it, it only previews ("would import ..."), the same
[dry-run discipline](169_zone_mass_edit.md) the zone editor uses.

### What makes a re-import safe?

The `extid:<key>` tag is the join key between the sheet and the world. Because
every row is matched on it with `search_world`, importing the same file twice
updates rather than duplicates, the same stable-id promise the
[area importer](166_batchcode_areas.md) makes, expressed as a tag. That is what
makes a CSV a source you re-sync rather than a one-shot paste.

### How the rows get in

Softcode has no file-reading primitive, and `@set` takes a single line, so
in-game you paste the sheet as a JSON list of CSV-line strings in one `@set`,
and the importer splits each string on commas. That is genuine CSV parsing and
validation, driven from data you can regenerate from the `.csv`. For
file-driven, unattended loads, the same rooms travel as an
[area file](166_batchcode_areas.md) via `@import` or the `realm` CLI, and this
in-game path proves the create, validate, and idempotent semantics.

## Build it

Create the importer object and drop it so the builder shares its room:

```text
@create room importer
drop room importer
```

Paste the sheet as a JSON list of CSV lines. This is a plain data attribute, so
it stays on one line (a `'''` block would store the list as a raw string and
break the row split):

```text
@set room importer/rows = ["r1,Guardroom,Spears line the wall.", "r2,Armory,Racks of dented steel."]
```

The `csv` [command trigger](../reference/softcode.md#triggers-attributes-on-objects)
ties it together. It reads [`trim`](../reference/softcode.md#fn-trim) on the
argument to get the mode, reads the pasted rows with
[`V`](../reference/softcode.md#fn-v), splits every row on commas, and rejects
the whole batch with [`pemit`](../reference/softcode.md#fn-pemit) if any row
lacks its three columns. Otherwise it either previews each row or, on `apply`,
updates the room matched by `search_world` or mints a fresh one with
[`create_obj`](../reference/softcode.md#fn-create_obj) and
[`set_attr`](../reference/softcode.md#fn-set_attr):

```text
@set room importer/cmd_csv = $csv *: '''
mode = trim(arg0)
rows = V('rows', [])
parsed = [[c.strip() for c in row.split(',')] for row in rows]
bad = [p for p in parsed if len(p) != 3]
if bad:
    pemit(enactor, 'VALIDATION FAILED: ' + str(len(bad)) + ' malformed row(s); fix them first.')
elif mode == 'apply':
    for p in parsed:
        # the extid: tag is the join key: match the prior import before creating
        hit = search_world(tag='extid:' + p[0])
        if hit:
            set_attr(hit[0], 'desc_extras', [['', p[2]]])
            pemit(enactor, '  updated ' + p[1])
        else:
            room = create_obj(p[1], tags=['room', 'extid:' + p[0]])
            # empty condition shows this description line to every looker
            set_attr(room, 'desc_extras', [['', p[2]]])
            pemit(enactor, '  created ' + p[1])
else:
    for p in parsed:
        pemit(enactor, '  would import ' + p[1] + ' (extid ' + p[0] + ')')
'''
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

Run `csv apply` **again**. The rooms already carry their `extid:` tags, so this
time the importer updates them in place:

```text
csv apply
  updated Guardroom
  updated Armory
```

One Guardroom, not two, which is what idempotent means. Edit a description in
the sheet, re-paste the `rows`, and `csv apply` syncs it in place. A malformed
batch is refused whole:

```text
@set room importer/rows = ["r1,Ok,fine", "junk"]
csv apply
  VALIDATION FAILED: 1 malformed row(s); fix them first.
```

Nothing is created, because validate-then-apply kept a broken sheet from
half-building your world.

## Going further

- **More columns:** extend the tuple to `extid,name,description,zone` and
  [`add_tag`](../reference/softcode.md#fn-add_tag)`(room, 'zone:' + p[3])` so
  the sheet places rooms into areas, then
  [export the zone](166_batchcode_areas.md) to a file.
- **Exits from a second sheet:** an `exits.csv` of `from_extid,dir,to_extid`
  rows, imported after the rooms, `create_obj`s the links, matched by the same
  external ids.
- **File-driven:** keep the `.csv` under version control and generate the
  `rows` JSON (or an area file) from it in a build step; the CLI importer loads
  it unattended for seeding and CI.
- **Delete detection:** compare `search_world(tag='extid:...')` against the
  sheet's keys and report rooms whose row vanished, the orphan half of a sync,
  echoed like the [world audit](172_world_audit.md).
```

