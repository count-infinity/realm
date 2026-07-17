# 182. Object snapshot / restore

> Checklist item 182 — [now] — *serialize named db attrs and roll them back, the snapshot/@clone/@export granularity ladder, admin authority over any object*

**What you'll build:** a `Restoration Vault` that freezes an object's
state and rolls it back on demand — `snapshot <obj> = <fields>` captures
the fields you name, `restore <obj>` writes them back, `snapshots` lists
what's on file. Perfect for the "reset the shop after the festival"
chore.

**Concepts:** serializing **named db attributes** into a keyed dict,
restoring them in place, an index kept by hand (softcode has no
attribute-enumeration primitive — an honest limit stated plainly), the
**granularity ladder** (field-set → `@clone` → `@export`), and **admin
authority** letting the vault restore *any* object, players included.

## How it works

**Snapshot the fields that drift.** During an event a stall's `price`
swings, its `stock` empties, an NPC's `mood` sours. A snapshot copies the
db attributes you *name* into a dict, keyed by the object's id, on the
vault; restore writes each key back with `set_attr`. That's the whole
mechanism — `{f: get_attr(t, f) for f in fields}` out, `[set_attr(t, k,
v) for k, v in snap.items()]` back.

**The honest limit: softcode can't enumerate an object's attributes.**
There is no `attrs(obj)` primitive, so you snapshot a *declared* field
list rather than "everything." In practice that's a feature — you capture
the mutable state that matters and leave identity alone. Two things a
field snapshot deliberately does **not** cover: an object's `description`
(it's not a db attr — it lives on the object itself) and its structure
(tags, behaviors, locks, contents). Which brings us to the ladder.

**The granularity ladder — pick the right backup for the job:**

| Tool | Granularity | Restores in place? | Captures |
|---|---|---|---|
| this vault | named db **fields** | yes (live) | the attrs you list |
| `@clone` | one **object** | no (a separate copy) | attrs + tags + behaviors + locks + description |
| `@export` | a whole **zone** | via `@import` plan→apply | every room + contents + masters, to a file |

Reach for the field snapshot for live "undo" of state; `@clone` for a
frozen structural spare; `@export`/`@import` (see
[batchcode areas](166_batchcode_areas.md)) to version a whole zone on
disk. Each is the right answer at its own scale.

**Admin authority is why it can restore players.** `set_attr` on another
player needs ADMIN (or ownership), so the vault is admin-owned — the
staff-tool boundary the [permission tour](183_permission_tiers.md) draws.
A builder-owned vault could snapshot world props but never write a
player's sheet.

**The index is kept by hand.** Because attrs can't be listed, the vault
tracks which ids it holds snapshots for in an `index` list, and a
`label_<id>` for a friendly name, so `snapshots` can render the catalog.

## Build it

A workshop object to snapshot, and the vault:

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

The three verbs — capture, roll back, and the catalog:

```text
@set Restoration Vault/cmd_snapshot = $snapshot * = *: t = get(trim(arg0)); fields = [f for f in trim(arg1).split() if f]; (pemit(enactor,'Only staff may snapshot.') if not has_tag(enactor,'admin') else (pemit(enactor,f'No object named {trim(arg0)}.') if not t else (set_attr(me, 'snap_'+t.id, {f: get_attr(t, f) for f in fields}), set_attr(me, 'label_'+t.id, name(t)), set_attr(me, 'index', [i for i in (V('index') or []) if i != t.id] + [t.id]), pemit(enactor,'Snapshot of ' + name(t) + ' saved: ' + ', '.join(fields) + '.'))))
@set Restoration Vault/cmd_restore = $restore *: t = get(trim(arg0)); snap = V('snap_'+t.id) if t else None; (pemit(enactor,'Only staff may restore.') if not has_tag(enactor,'admin') else (pemit(enactor,f'No object named {trim(arg0)}.') if not t else (pemit(enactor,'No snapshot on file for ' + name(t) + '.') if snap is None else ([set_attr(t, k, v) for k, v in snap.items()], pemit(enactor,'Restored ' + str(len(snap)) + ' field(s) to ' + name(t) + '.')))))
@set Restoration Vault/cmd_snaps = $snapshots: idx = V('index') or []; (pemit(enactor,'Only staff.') if not has_tag(enactor,'admin') else (pemit(enactor,'No snapshots on file.') if not idx else [pemit(enactor,f'- {V("label_"+i,"?")} (#{str(i)[:8]})') for i in idx]))
```

## Try it

Freeze the stall, let an "event" wreck it, then roll it back:

```text
snapshot market stall = price stock
   -> Snapshot of market stall saved: price, stock.
@set market stall/price = 999
@set market stall/stock = 0
restore market stall
   -> Restored 2 field(s) to market stall.
(price is 10 again, stock is 5)
```

The catalog, and a graceful miss:

```text
snapshots
   -> - market stall (#a1b2c3d4)
restore Restoration Vault
   -> No snapshot on file for Restoration Vault.
```

Admin authority reaches players too — snapshot a character's `title`, let
it drift, and restore it:

```text
snapshot Vandal = title
restore Vandal
   (Vandal's title is back to whatever you snapshotted)
```

A non-staff character who tries `snapshot market stall = price` is
refused: `Only staff may snapshot.`

## Going further

- **Named saves** — key snapshots by `t.id + '/' + label` so one object
  can hold "pre-festival" and "post-festival" states side by side.
- **Timed auto-restore** — pair with `expire()`: snapshot, run your
  event, and let an `ON_EXPIRE` fire `restore` automatically at closing
  time (the [jail timer](177_jail_system.md) pattern).
- **Structural spare** — for a backup that survives a `@destroy`, `@clone`
  the object first; the field snapshot restores state, the clone restores
  *being*.
- **Zone-scale rollback** — before a big build, `@export castle`; if it
  goes wrong, `@import castle` shows a plan and `@import/apply` puts it
  back ([item 166](166_batchcode_areas.md)).
