# World Management

The operator's toolkit: finding things, organizing areas, controlling
attribute visibility, and moving worlds between games.

## Searching the world

Everything lives in one in-memory world (backed by SQLite), so search
is instant:

```text
@find lighthouse              name substring
@find/tag zone:castle         by tag
@find/attr key_id             objects HAVING an attribute
@find/attr value=50           attribute equals a value
@find/owner Keeper            by owner
```

Softcode gets the same power (results capped):

```python
search_world(tag='merchant')
search_world(attr='xp_multiplier')
zone_rooms('castle')           # rooms in a zone
zones_of(here)                 # ['castle', 'haunted']
tag_value(here, 'zone')        # 'castle' — any key:value tag namespace
```

## Zones (areas)

A zone is a `zone:<name>` tag on rooms plus one **master** object —
the area's brain:

```text
@zone here = castle                    add this room
@zone/master Castle Brain = castle     crown the master
@zone/rooms castle                     list membership
@zone here                             what zones am I in?
```

The master is consulted three ways:

1. **Zone-wide softcode** — `$`-commands and `^listen` patterns on the
   master work in every member room (the classic Zone Master Room).
2. **Zone-wide events** — the master's `ON_ENTER`, `ON_DEATH`,
   `ON_PAYMENT`... fire for events in any member room.
3. **Numeric policy** — engine systems read attributes off the master:
   `@set Castle Brain/xp_multiplier = 1.2` makes every kill in the
   castle worth 20% more. Overlapping zones take the most generous
   value.

Rooms may belong to several zones; a room's masters are whoever shares
its zone tags.

## Attribute flags

Attributes are **readable by default** (game mechanics depend on it —
traps read `hp`, shops read `value`). Four flags adjust that, stored
per object and managed with `@attr`:

```text
@attr vault/gm_notes = secret          controllers-only (softcode + @examine)
@attr statue/inscription = visual      shown on plain player examine
@attr shrine/on_pray = safe            @set/@wipe refuse until !safe
@attr relic/quest_token = no_clone     skipped by @clone
@attr vault/gm_notes = !secret         remove a flag
@attr vault                            list flagged attributes
```

`password` is always unreadable from softcode, no flag needed. `@wipe`
spares `safe` attributes; `safe` is good insurance on softcode you
spent an hour writing.

## Import / export (areas as files)

Two ways in, for two jobs.

### Builder workflow: `@export` / `@import` (in-game, terraform-style)

A builder iterating on their own area works entirely in-game. Files
live in a sandbox (`data/areas/`, names only — no paths):

```text
@export castle          write data/areas/castle.realm (zone castle:
                        its rooms, their contents, and masters)
@areas                  list importable files
@import castle          show a PLAN (dry run — what would change)
@import/apply castle    execute the plan
```

Import is **stable-id sync**: objects are matched by their permanent
id (a UUID — a match is always *the same object re-imported*, never a
collision), so re-importing an edited file updates the live area in
place instead of duplicating it. The plan is a Terraform-style diff:

```text
Plan for area 'castle':
  + create   Guardroom
  ~ update   The Keep   (name: "Keep" → "The Keep"; attrs (banner))
  - orphan   goblin     (in world, not in file; left untouched)
  ! conflict Yard       (you don't control this object)
```

Rules that keep it safe:

- **Every touched object is control-gated** — anything you can't
  control becomes a `! conflict` and blocks apply.
- **Orphans are never deleted.** Objects in the area's rooms that
  aren't in the file are reported, not destroyed — `@destroy` them
  yourself if you mean to.
- **Sync moves objects to their file state.** If a player looted a
  quest sword out of the Keep, re-import returns it there — and the
  plan shows that (`~ update  iron sword  location: Alice → The Keep`)
  before anything happens. Nothing applies without you seeing the plan.

Area membership is computed, not tagged: rooms by their `zone:` tag,
contents by *being located in* an area room — so NPCs and items don't
carry zone tags. Once imported, `@tel castle` (or to the entry room)
to visit; areas aren't auto-linked into the surrounding world.

### Operator workflow: `realm export` / `realm import` (CLI, clone)

For distributing a reusable module (three taverns from one file) or a
full backup, the CLI clones with **fresh ids** — every import is
independent, never collides:

```bash
realm export backup.realm                  # whole world (players excluded)
realm export castle.realm --zone castle    # one area
realm import castle.realm                  # merge as a fresh copy
```

Both forms carry attributes (softcode included — it's just strings),
tags, locks, behaviors, and references. Passwords are always stripped;
for a full backup, copying the SQLite file is simplest.

## Ownership and safety valves

- `controls()` is the one authority predicate: self, owner, admins,
  builders-over-unowned, and your objects act with *your* authority
  (Penn-style delegation).
- `@chown` **halts** objects carrying scripts — old code never runs
  with the new owner's authority. `@untag <obj> = halt` after review.
- `@force <target> = <command>` runs a command as something you
  control, through the real dispatcher (target's own permissions
  apply). Player possession is opt-in via their control lock.
