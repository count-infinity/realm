# 172. World audit report

> Checklist item 172 — [now] — *search_world() introspection: orphans, broken exits, oversized attrs*

**What you'll build:** an `audit` command that scans the whole world and
reports its faults — objects with no location (orphans), exits that lead
nowhere (dangling `destination`), and attributes bloated past a sane
size. A builder's linter. (Builder permission — auditing reads the world,
which builders may do wholesale.)

**Concepts:** `search_world()` as a full-world scan, `loc()` for orphan
detection, `get('#' + id)` to test an exit's destination, and `o.db.all()`
to walk an object's attributes for size — all in one sandboxed report.

## How it works

**`search_world()` with no filter is the whole world.** The query caps at
500 objects but returns *everything* when you pass no tag/attr/name — the
scan set for an audit. From there each check is a comprehension:

- **Orphans** — a thing with `loc(o) is None` that isn't a room or a
  player is floating unreferenced; it'll never be seen or reached. (Rooms
  legitimately have no location; players may be between rooms — exclude
  both.)
- **Broken exits** — an exit's `destination` attribute is a room id.
  `get('#' + str(destination))` resolves it; if that's falsy, the exit
  points at a deleted or mistyped room and traversal dead-ends.
- **Oversized attributes** — walk `o.db.all()` and flag any value whose
  `str()` is longer than a threshold. Runaway log lists, a description
  someone pasted a novel into, an accidentally-appended-to attribute:
  size is the smell. (Use `len(str(v))`, not a type check — the sandbox
  forbids `isinstance`.)

Run it as a stored verb for a nice report, or paste the same logic into
`@eval` for a one-off — the audit *is* softcode, so it's as extensible as
your list of things worth checking.

## Build it

The auditor and its report — three scans over one world snapshot, a
headline count, then the offenders:

```text
@create auditor
drop auditor
@set auditor/cmd_audit = $audit: world = search_world(limit=500); orphans = [name(o) for o in world if loc(o) is None and not has_tag(o, 'room') and not has_tag(o, 'player')]; broken = [name(e) for e in world if has_tag(e, 'exit') and not get('#' + str(get_attr(e, 'destination', '')))]; fat = [name(o) + '/' + k for o in world for k, v in o.db.all().items() if len(str(v)) > 1000]; pemit(enactor, 'AUDIT: ' + str(len(orphans)) + ' orphan(s), ' + str(len(broken)) + ' broken exit(s), ' + str(len(fat)) + ' oversized attr(s).'); [pemit(enactor, '  orphan: ' + o) for o in orphans]; [pemit(enactor, '  broken exit: ' + e) for e in broken]; [pemit(enactor, '  oversized: ' + f) for f in fat]
```

## Try it

Plant one of each fault and run the linter:

```text
audit
  AUDIT: 1 orphan(s), 1 broken exit(s), 1 oversized attr(s).
    orphan: stray bolt
    broken exit: de
    oversized: heavy tome/lore
```

Fix them — `@teleport` the orphan into a room (or `@destroy` it),
`@link` the broken exit at a real room, `@set` the bloated attribute back
to something reasonable — and re-run until the counts are zero. The same
body pasted after `@eval` is a throwaway check when you don't want a
standing object:

```text
@eval result = len([o for o in search_world(limit=500) if loc(o) is None and not has_tag(o, 'room') and not has_tag(o, 'player')])
```

## Engine gaps

- The sandbox forbids `isinstance` (and `type`), so "oversized" is judged
  by `len(str(v))` rather than by value type — a deliberately coarse but
  robust heuristic. Long *scripts* will trip a low threshold too, which is
  why 1000 characters is a reasonable floor for flagging genuine data
  bloat rather than legitimate verbs.

## Going further

- **More checks:** flag rooms with no exits (`not exits(r)` — dead-end
  islands), exits whose destination is a *thing* not a room, or NPCs
  missing an expected attribute — each is one more comprehension.
- **Zone-scoped:** pass a zone name and audit only `zone_rooms(z)` and
  their contents when a full-world scan is more than you need.
- **Scheduled:** attach the auditor to a slow `script_ticker` and `remit`
  its report to a builders-only room, or `oob()` it to a dashboard.
- **Fix-it mode:** an `audit fix` variant could `destroy_obj` orphans and
  `del_attr` bloat — but preview first (the
  [dry-run discipline](169_zone_mass_edit.md)) before you let a linter
  mutate the world.
