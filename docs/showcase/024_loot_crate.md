# 024. Loot Crate

> Checklist item 24 ([now]): *ON_OPEN one-shot flags, weighted rand tables, lazy spawning*

**What you'll build:** A sealed supply crate that decides what is inside
at the moment its seal first breaks. The first open draws twice from a
weighted loot table and spawns the prizes into the crate itself. Close
it, reopen it, shake it: the depot only packs a crate once.

**Concepts:** [`ON_OPEN`](../reference/softcode.md#lifecycle-hooks) as a
lazy-spawn point (the hook runs after the open applies, so a prize
[`create_obj`](../reference/softcode.md#fn-create_obj)'d into the crate
is waiting when the player looks), a one-shot flag (`seeded`) that
[`set_attr`](../reference/softcode.md#fn-set_attr) writes to gate the
hook, a weighted table held as a plain attribute (`[[name, weight], ...]`)
and read with [`V`](../reference/softcode.md#fn-v), and a self-calling
lambda that folds a [`rand`](../reference/softcode.md#fn-rand) roll down
the table. It shares the [gift box](012_gift_box.md)'s `ON_OPEN` shape
and the [bag of holding](017_bag_of_holding.md)'s recursive lambda.

## How it works

The crate stays empty and cheap until someone opens it. That first open
runs a single hook that draws two prizes from a weighted table, spawns
them inside, and sets a flag so the crate never packs itself again. This
section answers three questions: why the loot is spawned late, how one
flag makes the whole thing one-shot, and how the table drives the odds.

### Why the crate spawns its loot late

Nothing exists inside the crate until the open happens, which is cheaper
than pre-stocking a warehouse of crates and lets the contents depend on
the moment of opening (the opener, the zone, the time of day). The timing
that makes this seamless comes from the action-phase trio
([action phases](../design/action-phases.md)): an
[`ON_OPEN`](../reference/softcode.md#lifecycle-hooks) hook runs in the
reaction pass, **after** the open has applied, and only because it
applied. By the time the hook runs, the crate is already open
([`has_tag(me, 'closed')`](../reference/softcode.md#fn-has_tag) is False),
so [`create_obj(..., me)`](../reference/softcode.md#fn-create_obj) drops
each prize into an open crate. The reaction pass finishes before the
player's next command, so the loot is sitting inside when they look. This
is the same post-state `ON_OPEN` the [gift box](012_gift_box.md) throws
its fanfare from.

### How one flag makes it one-shot

The whole idempotency mechanism is the `seeded` flag: the hook does
nothing when it is set, and sets it in the same pass as the spawn, so
every open after the first is an ordinary box opening. Keeping the flag
rather than tearing out the hook is deliberate, because a re-armable
variant (see "Going further") is then one
[`del_attr`](../reference/softcode.md#fn-del_attr) away.

The hook also has to guard on identity. An `ON_<EVENT>` hook fires on
**every** object in the room, not only the one that was opened, so the
body opens with `if target is me:` (see
[Guard on `target`](../reference/softcode.md#guard-on-target)). Without
it, opening any other container standing in the room would pack this
crate. It is the same guard the [gift box](012_gift_box.md) uses, keyed
by identity with `is`, never `==`.

### How the table drives the odds

The odds live in the `loot` attribute as plain data,
`[["a rusty gear", 60], ["a sealed med kit", 30], ["a plasma core", 10]]`,
weights summing to 100, so a balance pass is a `@set` rather than a script
edit. The draw is a self-calling lambda that folds one roll down the
table: roll [`rand(1, 100)`](../reference/softcode.md#fn-rand); if the
roll fits within the first entry's weight, take that name; otherwise
subtract the weight and recurse on the rest of the table. The
`len(t) == 1` clause makes the last entry absorb any remainder, so the
table stays correct even if someone edits the weights to sum under 100.
It is the recursion trick from the
[bag of holding](017_bag_of_holding.md)'s weigher: a script runs in one
namespace, like module scope, so the lambda's own name `draw` resolves
when it calls itself. The crate takes two independent draws, so a
10-weight plasma core (10% per draw) turns up at least once about 19% of
the time (1 - 0.9 * 0.9).

## Build it

The crate is a container sealed by hand. No lock is needed, because the
`closed` tag is the whole seal, and the stock `close` builtin sets it:

```text
@create supply crate
@tag supply crate = container
drop supply crate
@desc supply crate = A scuffed drop-crate. Stenciled across the lid: CONTENTS RANDOMIZED AT DEPOT.
close supply crate
```

The odds are plain data, one `[name, weight]` pair per prize, the weights
summing to 100 (`@set` parses the JSON, so this stores as a real list):

```text
@set supply crate/loot = [["a rusty gear", 60], ["a sealed med kit", 30], ["a plasma core", 10]]
```

The seeding hook is a `'''` multi-line block: end the `@set` line with
`'''`, write the indented body, and close with a line of just `'''`. It
guards to this crate, checks the one-shot flag, then draws twice, sets
the flag, spawns both prizes inside the crate, and lets the room hear the
seal break:

```text
@set supply crate/on_open = '''
if target is me:  # ON_OPEN fires on every object in the room, so guard it
    if not V('seeded', 0):  # one-shot: pack the crate only on the first open
        draw = lambda t, r: t[0][0] if r <= t[0][1] or len(t) == 1 else draw(t[1:], r - t[0][1])
        set_attr(me, 'seeded', 1)
        create_obj(draw(V('loot'), rand(1, 100)), [], me)  # location me: spawn inside the crate
        create_obj(draw(V('loot'), rand(1, 100)), [], me)
        remit(loc(enactor), 'Something rattles and settles inside the crate as the seal breaks.')  # loc(enactor): a held crate's loc(me) is its holder, not the room
'''
```

Reading the draw: `t[0][0]` is the first entry's name and `t[0][1]` its
weight, so a roll within that weight takes the prize, while a higher roll
subtracts the weight and recurses on `t[1:]`.
[`remit`](../reference/softcode.md#fn-remit) reaches the whole room
through [`loc(enactor)`](../reference/softcode.md#fn-loc), the room where
the opener stands, which is correct even when the crate is opened in a
player's hands.

## Try it

```text
> open supply crate
Something rattles and settles inside the crate as the seal breaks.
You open the supply crate.

> look supply crate
supply crate
A scuffed drop-crate. Stenciled across the lid: CONTENTS RANDOMIZED AT DEPOT.

Contains:
  a rusty gear
  a sealed med kit
```

The two lines under `Contains:` vary with the roll: most opens turn up
gears, med kits show up often enough, and now and then the plasma core
that makes the habit pay. Take your loot, then prove the flag holds:

```text
> get rusty gear from supply crate
You pick up an a rusty gear.

> close supply crate
You close the supply crate.

> open supply crate
You open the supply crate.
```

No rattle and no fresh goods the second time, just whatever you left
behind (the loot names carry their own article, which is why the pickup
line doubles it). `@examine supply crate` shows `seeded: 1`, so the depot
has moved on.

## Going further

- **Real item stats:** spawn from prototypes instead of bare names. The
  [vending machine](002_vending_machine.md)'s per-item dicts
  (`{"name": ..., "weight": ...}`) let each
  [`create_obj`](../reference/softcode.md#fn-create_obj) stamp
  attributes, so the med kit heals and the gear carries
  [weighable](017_bag_of_holding.md) heft.
- **Re-arm on zone reset:** a zone master's
  [`ON_RESET`](../reference/softcode.md#lifecycle-hooks) that runs
  [`del_attr(crate, 'seeded')`](../reference/softcode.md#fn-del_attr) and
  [`add_tag(crate, 'closed')`](../reference/softcode.md#fn-add_tag) turns
  one-shot into once-per-repop, so a dungeon's chests refill when the
  dungeon does.
- **Opener-scaled loot:** the hook already knows `enactor`, so feed
  [`get_attr(enactor, 'level', 1)`](../reference/softcode.md#fn-get_attr)
  into which table you draw from (`loot_deep` versus `loot`) and the
  crate scales without a single extra object.
- **Mimic odds:** add one more weighted entry, `["MIMIC", 5]`, and a
  branch that skips the spawn on drawing it and runs
  [`start_combat(me, enactor)`](../reference/softcode.md#fn-start_combat)
  instead. The best loot table entry is teeth.
