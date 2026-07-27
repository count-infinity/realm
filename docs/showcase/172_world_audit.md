# 172. World audit report

> Checklist item 172 ([now]): *search_world introspection: orphans, broken exits, oversized attrs*

**What you'll build:** an `audit` command that scans the whole world and
reports its faults: objects with no location (orphans), exits that lead
nowhere (a dangling `destination`), and attributes bloated past a sane size.
It is a builder's linter for the world. You assemble it with builder commands
(`@create` and `@set`), and the scan reads world state that is open to
inspection.

**Concepts:** [`search_world()`](../reference/softcode.md#fn-search_world) as a
full-world scan, [`loc()`](../reference/softcode.md#fn-loc) for orphan
detection, [`get()`](../reference/softcode.md#fn-get) on an id to test an exit's
destination, and `o.db.all()` to walk an object's attributes for size, all in
one sandboxed report.

## How it works

The finished object is a single thing you drop in a room, carrying one
`$audit` command. Type `audit` and it takes one snapshot of the world with
`search_world()`, runs three checks over that snapshot as list comprehensions,
prints a headline count, and then lists the offenders. This section answers
three questions: what makes the snapshot, how each check decides a fault, and
why size (not type) judges the last one.

**Why one `search_world()` call is the whole world.** The query accepts filters
for tag, attribute, name, and value, and applies every filter you pass. Pass
none and it returns every cached object, up to its `limit`, which is why the
build passes `limit=500`: that is the ceiling the engine clamps to, so it is
the widest snapshot a single scan can take. Everything after this reads from
that one list, so the report is internally consistent.

Each check is then a comprehension over the snapshot:

- **Orphans.** A thing whose `loc(o)` is `None`, and that is neither a room nor
  a player, floats unreferenced, so it will never be seen or reached. Rooms
  legitimately have no location, and a player may sit between rooms for a beat,
  so both are excluded by their tags.
- **Broken exits.** An exit stores its target room's id in a `destination`
  attribute. `get('#' + str(destination))` resolves that id to an object, and a
  falsy result means the exit points at a deleted or mistyped room, so
  traversal dead-ends there.
- **Oversized attributes.** Walk `o.db.all()` and flag any value whose `str()`
  runs longer than a threshold. A runaway log list, a description someone
  pasted a novel into, or an attribute appended to by accident all read as
  bloat, and size is the reliable tell.

**Why size, not type, judges bloat.** The sandbox treats `isinstance` and
`type` as forbidden names, so a value check by type is off the table. Measuring
`len(str(v))` is the robust alternative. A long *script* trips a low threshold
too, so 1000 characters is a sensible floor: it flags genuine data bloat while
leaving legitimate verbs alone.

You run it as a stored verb for a repeatable report. The same body pasted after
`@eval` is a throwaway check when you want an answer once, because the audit
*is* softcode, so it is as extensible as your list of things worth checking.

## Build it

First create the auditor and drop it in the room so its `$audit` command is in
reach:

```text
@create auditor
drop auditor
```

Now give it the command. The body takes one world snapshot, builds the three
offender lists, prints the headline count, and then emits each offender on its
own line:

```text
@set auditor/cmd_audit = $audit:'''
world = search_world(limit=500)
orphans = [name(o) for o in world if loc(o) is None and not has_tag(o, 'room') and not has_tag(o, 'player')]
broken = [name(e) for e in world if has_tag(e, 'exit') and not get('#' + str(get_attr(e, 'destination', '')))]
# len(str(v)) stands in for a type check: the sandbox forbids isinstance, and sheer size is the tell.
fat = [f'{name(o)}/{k}' for o in world for k, v in o.db.all().items() if len(str(v)) > 1000]
pemit(enactor, f'AUDIT: {len(orphans)} orphan(s), {len(broken)} broken exit(s), {len(fat)} oversized attr(s).')
for o in orphans:
    pemit(enactor, f'  orphan: {o}')
for e in broken:
    pemit(enactor, f'  broken exit: {e}')
for f in fat:
    pemit(enactor, f'  oversized: {f}')
'''
```

The three offender lists use [`name()`](../reference/softcode.md#fn-name),
[`has_tag()`](../reference/softcode.md#fn-has_tag), and
[`get_attr()`](../reference/softcode.md#fn-get_attr), and every line reports
through [`pemit()`](../reference/softcode.md#fn-pemit), which delivers to the
enactor after the script finishes.

## Try it

Plant one of each fault and run the linter:

```text
> audit
  AUDIT: 1 orphan(s), 1 broken exit(s), 1 oversized attr(s).
    orphan: stray bolt
    broken exit: de
    oversized: heavy tome/lore
```

Fix them and re-run until the counts reach zero: `@teleport` the orphan into a
room (or `@destroy` it), `@link` the broken exit at a real room, and `@set` the
bloated attribute back to something reasonable. The same body pasted after
`@eval` is a throwaway check for when you want the count once, without a
standing object:

```text
@eval result = len([o for o in search_world(limit=500) if loc(o) is None and not has_tag(o, 'room') and not has_tag(o, 'player')])
```

## Going further

- **More checks:** flag rooms with no exits
  ([`exits()`](../reference/softcode.md#fn-exits) empty means a dead-end
  island), exits whose destination is a *thing* rather than a room, or NPCs
  missing an expected attribute. Each is one more comprehension.
- **Zone-scoped:** pass a zone name and audit only
  [`zone_rooms()`](../reference/softcode.md#fn-zone_rooms) and their contents
  when a full-world scan is wider than you need.
- **Scheduled:** attach the auditor to a slow `script_ticker` and
  [`remit()`](../reference/softcode.md#fn-remit) its report to a builders-only
  room, or [`oob()`](../reference/softcode.md#fn-oob) it to a dashboard.
- **Fix-it mode:** an `audit fix` variant could
  [`destroy_obj()`](../reference/softcode.md#fn-destroy_obj) orphans and
  [`del_attr()`](../reference/softcode.md#fn-del_attr) bloat, but preview first
  (the [dry-run discipline](169_zone_mass_edit.md)) before you let a linter
  mutate the world.
</content>
</invoke>
