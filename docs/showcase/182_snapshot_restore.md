# 182. Object snapshot / restore

> Checklist item 182 ([now]): *serialize named db attributes and roll them back, the snapshot / @clone / @export granularity ladder, admin authority over any object*

**What you'll build:** a `Restoration Vault` that freezes an object's state and
rolls it back on demand. `snapshot <obj> = <fields>` captures the fields you
name, `restore <obj>` writes them back, and `snapshots` lists what is on file.
It is the tool for the reset-the-shop-after-the-festival chore.

**Concepts:** serializing [named db attributes](../reference/softcode.md#fn-get_attr)
into a keyed dict, restoring them in place, an index kept by hand (softcode has
no attribute-enumeration primitive, an honest limit stated plainly), the
**granularity ladder** (a field set, then `@clone`, then `@export`), and
**admin authority** that lets the vault restore any object, players included.

## How it works

The vault is one object that carries three `$`-commands and a small pile of
saved states. A snapshot copies the db attributes you name
off a target into a dict, stores that dict on the vault under a key built from
the target's id, and remembers the target in an index so the catalog has
something to list. A restore reads the dict back and writes each field into
place. This section covers where the state lives, why the field list is
declared rather than discovered, when to reach past a field snapshot for
`@clone` or `@export`, and why the vault may rewrite a player's sheet at all.

### What a snapshot actually copies

During an event a stall's `price` swings, its `stock` empties, an NPC's `mood`
sours. A snapshot copies the db attributes you *name* into a dict keyed by the
object's id, held on the vault; restore writes each key back with
[`set_attr`](../reference/softcode.md#fn-set_attr) and reports the result to
the builder with [`pemit`](../reference/softcode.md#fn-pemit). That is the whole
mechanism: `{f: get_attr(t, f) for f in fields}` on the way out, and one
`set_attr(t, k, v)` per saved pair on the way back.

### Why you name the fields instead of grabbing everything

Softcode has no attribute-enumeration primitive: there is no `attrs(obj)`
function, so you snapshot a *declared* field list rather than everything. In
practice that is a feature, because you capture the mutable state that matters
and leave identity alone. A field snapshot deliberately leaves out two things:
an object's `description` (which lives on the object itself, not in a db
attribute, so `get_attr(t, 'description')` reads nothing) and its structure
(tags, behaviors, locks, contents). That is what the ladder is for.

### The granularity ladder (pick the right backup for the job)

| Tool | Granularity | Restores in place? | Captures |
|---|---|---|---|
| this vault | named db **fields** | yes (live) | the attrs you list |
| `@clone` | one **object** | no (a separate copy) | attrs, tags, behaviors, locks, description |
| `@export` | a whole **zone** | via `@import` plan then apply | every room, its contents, and masters, to a file |

Reach for the field snapshot for a live "undo" of state; `@clone` for a frozen
structural spare; `@export` / `@import` (see
[batchcode areas](166_batchcode_areas.md)) to version a whole zone on disk.
Each is the right answer at its own scale.

### Why the vault may rewrite a player's sheet

[`set_attr`](../reference/softcode.md#fn-set_attr) on another player requires
ADMIN (or ownership), so the vault is admin-owned, which is the staff-tool
boundary the [permission tour](183_permission_tiers.md) draws. A builder-owned
vault could snapshot world props but never write a player's sheet.

### How the catalog knows what is on file

Because the engine offers no way to list an object's attributes, the vault
keeps its own index: it tracks the ids it holds snapshots for in an `index`
list, plus a `label_<id>` for a friendly name, so `snapshots` renders the
catalog.

## Build it

First dig a room to work in, drop in a workshop object to snapshot, and stand
up the vault itself:

```text
@dig The Archive = archive, out
archive
@create market stall
drop market stall
@desc market stall = A trestle table of goods.
@set market stall/price = 10
@set market stall/stock = 5
@create Restoration Vault
drop Restoration Vault
@desc Restoration Vault = A humming cabinet of saved states. SNAPSHOT <obj> = <fields>, RESTORE <obj>, SNAPSHOTS.
```

The capture verb reads the target and the field list, gates on the `admin`
tag, and then stores three things: the field dict under `snap_<id>`, a friendly
name under `label_<id>`, and the target's id appended to `index` (dropping any
prior copy of that id, so re-snapshotting moves it to the end):

```text
@set Restoration Vault/cmd_snapshot = $snapshot * = *: '''
t = get(trim(arg0))
fields = [f for f in trim(arg1).split() if f]
if not has_tag(enactor, 'admin'):
    pemit(enactor, 'Only staff may snapshot.')
elif not t:
    pemit(enactor, f'No object named {trim(arg0)}.')
else:
    # key every saved state by the target's id so one vault holds many
    set_attr(me, 'snap_' + t.id, {f: get_attr(t, f) for f in fields})
    set_attr(me, 'label_' + t.id, name(t))
    set_attr(me, 'index', [i for i in (V('index') or []) if i != t.id] + [t.id])
    pemit(enactor, 'Snapshot of ' + name(t) + ' saved: ' + ', '.join(fields) + '.')
'''
```

The roll-back verb looks the target up, finds its saved dict, gates on `admin`,
reports a graceful miss when nothing is on file, and otherwise writes each saved
field back and reports the count:

```text
@set Restoration Vault/cmd_restore = $restore *: '''
t = get(trim(arg0))
snap = V('snap_' + t.id) if t else None
if not has_tag(enactor, 'admin'):
    pemit(enactor, 'Only staff may restore.')
elif not t:
    pemit(enactor, f'No object named {trim(arg0)}.')
elif snap is None:
    pemit(enactor, 'No snapshot on file for ' + name(t) + '.')
else:
    for k, v in snap.items():
        set_attr(t, k, v)
    pemit(enactor, 'Restored ' + str(len(snap)) + ' field(s) to ' + name(t) + '.')
'''
```

The catalog walks the hand-kept index and prints each entry's label and the
first eight characters of its id:

```text
@set Restoration Vault/cmd_snaps = $snapshots: '''
idx = V('index') or []
if not has_tag(enactor, 'admin'):
    pemit(enactor, 'Only staff.')
elif not idx:
    pemit(enactor, 'No snapshots on file.')
else:
    for i in idx:
        pemit(enactor, f'- {V("label_" + i, "?")} (#{str(i)[:8]})')
'''
```

## Try it

Freeze the stall, let an "event" wreck it, then roll it back:

```text
> snapshot market stall = price stock
Snapshot of market stall saved: price, stock.
> @set market stall/price = 999
> @set market stall/stock = 0
> restore market stall
Restored 2 field(s) to market stall.
```

After the restore, `price` reads 10 again and `stock` reads 5.

The catalog, and a graceful miss (the short id varies per object):

```text
> snapshots
- market stall (#a1b2c3d4)
> restore Restoration Vault
No snapshot on file for Restoration Vault.
```

Admin authority reaches players too. Snapshot a character's `title`, let it
drift, and restore it:

```text
> snapshot Vandal = title
Snapshot of Vandal saved: title.
> restore Vandal
Restored 1 field(s) to Vandal.
```

A non-staff character who tries `snapshot market stall = price` is refused with
`Only staff may snapshot.`

## Going further

- **Named saves:** key snapshots by `t.id + '/' + label` so one object can hold
  "pre-festival" and "post-festival" states side by side.
- **Timed auto-restore:** pair with [`expire()`](../reference/softcode.md#fn-expire):
  snapshot, run your event, and let an `ON_EXPIRE` on a throwaway timer fire
  `restore` automatically at closing time (the [jail timer](177_jail_system.md)
  pattern).
- **Structural spare:** for a backup that survives a `@destroy`, `@clone` the
  object first; the field snapshot restores state, and the clone restores being.
- **Zone-scale rollback:** before a big build, `@export castle`; if it goes
  wrong, `@import castle` shows a plan and `@import/apply` puts it back
  ([item 166](166_batchcode_areas.md)).
```