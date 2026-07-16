# 024. Loot Crate

> Checklist item 24 — [now] — *ON_OPEN one-shot flags, weighted rand tables, lazy spawning*

**What you'll build:** A sealed supply crate that decides what's
inside at the moment its seal first breaks — two pulls from a weighted
loot table, spawned into the crate a heartbeat before the lid rises.
Close it, reopen it, shake it: the depot only packs a crate once.

**Concepts:** `ON_OPEN` as a lazy-spawn point (the hook fires while
the open is being gated — *before* the lid is actually off — so loot
created into the crate is there when the player looks in), a
**one-shot flag** (`seeded`) guarding the hook, a **weighted table as
data** (`[[name, weight], ...]` in a plain attribute), and a recursive
one-line draw that walks it.

## How it works

**Lazy spawning.** Nothing exists inside the crate until someone
opens it. That's cheaper than pre-stocking a warehouse of crates, and
it means the contents can depend on the *moment* of opening — the
opener, the zone, the phase of the moon. The timing that makes it
seamless is 014's fact about hooks: `ON_OPEN` runs during the gate,
before the `closed` tag comes off, so `create_obj(..., me)` has the
goods waiting when the lid physically opens one beat later.

**One-shot means one flag.** The whole idempotency mechanism is
`seeded`: the script does nothing if it's set, and sets it in the same
breath as the spawn. Every open after the first is just a box opening.
(Re-armable variants — see below — are one `del_attr` away, which is
why the flag beats destroying the hook.)

**The table is data; the draw is a fold.** The odds live in a plain
attribute — `[["a rusty gear", 60], ["a sealed med kit", 30],
["a plasma core", 10]]`, weights summing to 100 — so a balance pass is
an `@set`, not a script edit. The draw walks it recursively: roll
`rand(1, 100)`; if the roll fits under the first entry's weight,
that's the prize; otherwise subtract and recurse down the tail. It's
the same self-passing lambda trick as the
[bag of holding](017_bag_of_holding.md)'s weigher — one line, any
table length. Two independent draws per crate; a 10-weight plasma core
is a 19% chance of turning up at least once.

## Build it

The crate, sealed by hand — `close` needs no lock; a `closed` tag is
the whole seal:

```text
@create supply crate
@set supply crate/container = true
drop supply crate
@desc supply crate = A scuffed drop-crate. Stenciled across the lid: CONTENTS RANDOMIZED AT DEPOT.
close supply crate
```

The odds, as data:

```text
@set supply crate/loot = [["a rusty gear", 60], ["a sealed med kit", 30], ["a plasma core", 10]]
```

The seeding hook — draw twice, flag once, and let the room hear it:

```text
@set supply crate/on_open = draw = lambda draw, t, r: t[0][0] if r <= t[0][1] or len(t) == 1 else draw(draw, t[1:], r - t[0][1]); (set_attr(me, 'seeded', 1), create_obj(draw(draw, get_attr(me, 'loot'), rand(1, 100)), [], me), create_obj(draw(draw, get_attr(me, 'loot'), rand(1, 100)), [], me), remit(loc(me), 'Something rattles and settles inside the crate as the seal breaks.')) if not get_attr(me, 'seeded', 0) else None
```

Reading the draw: `t[0][0]` is the first entry's name, `t[0][1]` its
weight; the `len(t) == 1` guard makes the last entry catch any
remainder, so the table stays correct even if someone edits the
weights to sum under 100.

## Try it

```text
open supply crate
```

The room hears `Something rattles and settles inside the crate as the
seal breaks.` — and `look supply crate` shows two spawned prizes:
mostly gears, med kits often enough, and now and then the plasma core
that makes the habit pay. Take your loot, then prove the flag:

```text
get rusty gear from supply crate
close supply crate
open supply crate
```

No rattle, no fresh goods — just whatever you left behind.
`@examine supply crate` shows `seeded: 1`; the depot has moved on.

## Going further

- **Real item stats:** spawn from prototypes instead of bare names —
  the [vending machine](002_vending_machine.md) pattern of per-item
  dicts (`{"name": ..., "weight": ...}`) stamps attributes on each
  `create_obj`, so the med kit heals and the gear has
  [weighable](017_bag_of_holding.md) heft.
- **Re-arm on zone reset:** a zone master's `ON_RESET` that
  `del_attr(crate, 'seeded')` (and `add_tag`s it `closed`) turns
  one-shot into once-per-repop — the dungeon's chests refill when the
  dungeon does.
- **Opener-scaled loot:** the hook knows `enactor` — feed
  `get_attr(enactor, 'level', 1)` into which table attribute you draw
  from (`loot_deep` vs `loot`), and the crate scales without a single
  extra object.
- **Mimic odds:** one more weighted entry — `["MIMIC", 5]` — and a
  guard that, on drawing it, skips the spawn and
  `start_combat(me, enactor)` instead. The best loot table entry is
  teeth.
