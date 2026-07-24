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

## Referencing objects: names, ids, and keyids

Three ways to name the object you mean — in softcode's `get()` and anywhere
a command takes an object:

```python
get('rusty key')      # by NAME  — first match, local first; never raises
get('#3fa9c2b1-...')  # by raw ID — the exact, permanent uuid
get('$banknet_core')  # by KEYID — a friendly, unique, stable handle
```

**Name** is convenient but is not identity: it takes the *first* match and
never complains about ambiguity, so a second object sharing the name can
silently capture the reference. Fine for a one-off lookup, a trap for a
stored reference that must always point at one specific object.

**Keyid** fixes that for the objects that need it — a well-known singleton
like a bank core, a weather master, or a zone brain. Give one a handle with
`@keyid`, then reference it as `$<handle>` forever:

```text
@keyid BankNet Core = banknet_core     set (refused if another object holds it)
@keyid BankNet Core                    show the current handle
@keyid BankNet Core =                  clear it
```

A keyid is **opt-in** (unkeyed objects cost nothing at creation), **unique**
(only one live object holds a given handle — a clash is refused, never
merged), **stable** (it does not change when you `@name` or re-own the
object), and **identity, not data**: `@set obj/keyid` is refused in favor of
`@keyid`, and `@clone` never copies it (a copy lands keyless, just as it gets
a fresh uuid). The `$` prefix is the default and is game-tunable
(`KEYID_SIGIL` in `config.py` — any length, e.g. `"$$"` or `"key:"`).

See [Object identity](../design/object-identity.md) for the full model, and
the [ATM tutorial](../showcase/004_atm_terminal.md) for referencing a shared
master object by a stable handle in practice.

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

### Area reset (repop)

A zone can **return to its authored state on a timer, but only while no
player is inside** — the whole area repops at once when nobody's watching
(unlike per-room spawners, which top up while you stand there). Attach the
`zone_reset` behavior to the master and configure it with plain `@set`:

```text
@behavior Castle Brain = zone_reset        the master repops its zone
@set Castle Brain/reset_interval = 300      try to reset every 5 min
@set Castle Brain/reset_spec = [{"prototype": {"name": "a guard", "tags": ["npc"], "attrs": {"hp": 20}}, "room": "#castle_gate", "count": 2}]
```

When the zone is due and holds **no players**, the master **clears its prior
spawns and reloads the `reset_spec` fresh** (so a killed guard is back — but
never pops on top of you, and mobs from a since-removed entry vanish), then
fires **`ON_RESET`** for everything the spec doesn't cover:

```text
@set Castle Brain/ON_RESET = trigger me/reseal_doors
```

`reset_spec` entries use the spawner's prototype vocabulary; `room` is an
object id (`#castle_gate`) or a room tag. Reset-spawns are persistent
canonical contents (not ephemeral). An occupied zone simply defers — it
resets the instant it empties (by design: an area never returns to canonical
while someone's watching).

## Paired exits (doors)

A two-way `@dig` creates *two* exit objects, and anything that treats
them as one door (the mirror hooks of the
[lockable door](../showcase/025_lockable_door.md)) needs each side to
know its sibling. The engine owns that relationship end to end:

```text
@dig The Vault = vault door, vault door   the two faces are PAIRED at birth
@pair vault door                          show the partner
@pair vault door = <far exit or #id>      marry hand-built @open exits,
                                          double doors, or re-pair
@pair vault door =                        divorce (both sides)
```

Each side's `partner` attribute holds the other's `#id`; scripts read it
with `V('partner')`. Because a stored reference can go stale, every
write path that could invalidate it maintains it: `@link` and `@unlink`
on a paired exit **dissolve** the pairing on both sides (loudly, so a
retargeted exit never drags a mirror along to an unrelated door), and
`@destroy` of one side clears the survivor.

## Templates (`@parent`)

Write a capability once, as attributes on a **template** object, and any
object you `@parent` to it inherits the lot: default values, `ON_<EVENT>`
hooks, `$`-commands. The child's own attribute always shadows the
template's; writes always land on the child (a template value is a
default, never shared state); deleting a child's attribute re-exposes the
template's. Editing the template fixes every child at once.

```text
@create LockableDoor Template
@set LockableDoor Template/on_open = if target is me: remove_tag(V('partner'), 'closed')
@set LockableDoor Template/on_close = if target is me: add_tag(V('partner'), 'closed')
@parent vault door = LockableDoor Template     adopt (control both objects)
@parent vault door =                           clear
```

Tags, behaviors, locks, and fields do **not** inherit — they are
per-instance identity. The idiom for stamping fully-kitted copies is one
**exemplar**: parent it, tag it, attach behaviors, then `@clone` it
(clones copy tags and behaviors and keep the parent link). `@examine`
shows anything inherited in its own marked section. The full model:
[Templates](../design/templates.md).

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
spent an hour writing. A `keyid` (the unique handle set with `@keyid`,
above) is always skipped by `@clone` and never writable with `@set` — no
flag needed; it is a unique identity, like the uuid.

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
- **Keyids carry over; conflicts don't merge.** A friendly `$keyid`
  (see above) travels in the file like any attribute. Re-importing the
  *same* object (matched by id) overwrites its keyid in place; but a keyid
  the file assigns to one object while a *different* live object already
  holds it becomes a `! conflict` and blocks apply — never a silent steal.

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
tags, locks, behaviors, and references. On a fresh-id (clone) import,
any attribute value that IS an exported id — bare or `#`-prefixed, a
door's `partner`, a terminal's stored core id — is rewritten to the
copy's own object, so stored references re-wire instead of pointing
back at the original. Passwords are always stripped;
for a full backup, copying the SQLite file is simplest. A `$keyid` handle
carries over only when free: cloning a keyed object into a world that
already holds that handle lands the copy **keyless** (logged), never
merged — re-key it with `@keyid` if it should be the new singleton.

## Builder power tools

```text
@eval <code>              run softcode ad-hoc, report the result
                          (@eval result = len(search_world(tag='npc')))
@foreach <search> = <cmd> run a command per match (%o = each #id)
                          (@foreach tag:rat = @teleport %o = The Cellar)
@stats                    live metrics: tick interval, behavior load,
                          scheduled waits, active combat — check when laggy
@rolls on|off             echo your skill-check dice for debugging
quell / unquell           drop to (and restore from) mortal perception
                          and authority — test dark/hidden as a player
```

Admins bypass ALL perception (dark, hidden, invisible) and authority —
which is why the superuser sees a hidden key. `quell` is how you test a
scene honestly as a mortal without making a second character.

## Multi-line input (heredocs)

Softcode attributes are just strings, so a whole script can go on one line
with `;` between statements — but that gets brutal to read. Instead, open a
**multi-line block**: end a command line with `'''`, and the session collects
every line after it — *indentation intact* — until a line that is exactly
`'''`. The block runs as one command:

```text
@set here/on_enter='''
if get_attr(enactor, 'boots'):
    pemit(enactor, 'Your boots hold.')
else:
    damage(enactor, 1)
    pemit(enactor, 'A board snaps under your weight!')
'''
```

That stores the whole indented body in `on_enter`, and it execs as real
sandboxed Python — blocks, loops, `if`/`else`, same engine as a one-liner,
just readable. It works with any command that takes a value (`@set`,
`@desc`, and friends).

- **`@abort`** on its own line discards a block — handy if you mistype the
  opening line. A block is also capped at a sane line count as a backstop
  against an unterminated one.
- **Normal command mode only** — a heredoc never starts while a `prompt()`
  wizard is capturing input, or at the login screen.
- **Configurable delimiters.** `HEREDOC_OPEN` / `HEREDOC_CLOSE` in `config.py`
  (both `'''` by default). Make them **distinct** — `HEREDOC_OPEN = '<<<'`,
  `HEREDOC_CLOSE = '>>>'` — if your scripts contain `'''` themselves (a
  triple-quoted string, say), so a body line of `'''` no longer ends the
  block.

## Ownership and safety valves

- `controls()` is the one authority predicate: self, owner, admins,
  builders-over-unowned, and your objects act with *your* authority
  (Penn-style delegation).
- **`halt` freezes softcode.** An object tagged `halt` runs no softcode
  at all — its `$`-commands and `^listen` patterns stop matching, its
  `ON_<EVENT>` and `on_check` hooks stop firing, and its queued script
  commands are dropped. `@tag <obj> = halt` to freeze, `@untag <obj> =
  halt` to release. Player built-in commands are unaffected (they
  dispatch outside the softcode path), so halting a *player* quarantines
  their automation without locking them out of the game.
- **A halted owner freezes everything they own** — the fail-safe. `halt`
  is inherited one level: an object is frozen if its own tag is set *or*
  its owner's is. So `@tag <someplayer> = halt` instantly silences every
  gadget, NPC, and room-script that player owns, in one move, without
  tagging each. (Inheritance is single-level by design — it does not walk
  a whole owner chain.)
- `@chown` **auto-halts** objects carrying scripts — old code never runs
  with the new owner's authority. `@untag <obj> = halt` after review.
- `@force <target> = <command>` runs a command as something you
  control, through the real dispatcher (target's own permissions
  apply). Player possession is opt-in via their control lock.
