# 014. Basic Container

> Checklist item 14 — [now] — *db.container, on_check wards, block(), weight-attr conventions*

**What you'll build:** A canvas sack that holds at most 3 items and
10 lbs. Overfill it and you get a specific, numeric refusal — and no
code path, polite or not, can sneak an eleventh pound inside.

**Concepts:** The `container` attribute convention and the built-in
`put`/`get from`/`open`/`close` machinery, **`on_check` wards** — the
softcode veto that runs in the engine's permission pass — `block()`,
action inspection (`atype`, `target`, `adata`), summed `weight`
attributes, and an `ON_PUT` reaction for friendly feedback.

This is the first build in the arc that *intercepts* the engine instead
of adding commands to it.

## How it works

**What the engine already gives you.** Set `container = true` on a
thing and the stock commands do the rest: `put <item> in <it>`,
`get <item> from <it>`, `open`/`close` (a `closed` tag blocks both
directions), and `look` lists its contents. That's a complete working
container with zero scripting.

**What nothing checks yet is capacity.** REALM deliberately has no
weight kernel — weight is a *convention*: items carry a `weight`
attribute (the vending machine's prototypes stamp one on every product)
and anything that cares sums them. The enforcement point is the
**ward**: an `on_check` attribute runs during the engine's *permission
pass*, before the action happens, on every action this object
participates in (as target, actor, or room). Inside it you get a
read-only view of the world plus the in-flight action — `atype` (the
action type string), `target`, `actor`, `adata(key)` for its payload —
and one power: `block(reason)`. A blocked action never happens and the
actor is told why.

Wards are decision-only *by construction*: the check-pass namespace has
no `set_attr`, no `say`, no `create_obj` — a ward can veto, not act.
Reactions belong in `ON_<EVENT>` scripts, which run after. This is the
same interception surface behaviors and locks use, which is what makes
the rule a law of physics rather than a politeness observed by
well-behaved commands: `put`, a scripted `give`, a spawner — everything
funnels through the same check pass.

**One ward, two rules.** The `put` action arrives as
`atype == 'item:on_put'` with the container as `target` and the item in
`adata('item')`. The ward computes the current load, then blocks on
item count or on weight — each with the numbers in the message. Vague
errors are the number one way container builds frustrate players; say
*why*, with math.

## Build it

The sack — built-in container behavior plus our two limits as plain
data, and a description that counts its own contents:

```text
@create canvas sack
drop canvas sack
@desc canvas sack = A patched canvas sack. [[n = len(contents(me)); result = f'It bulges around {n} item{"" if n == 1 else "s"}.']]
@set canvas sack/container = true
@set canvas sack/capacity = 3
@set canvas sack/weight_limit = 10
```

The ward. `mine` filters to "someone is putting something into *me*";
unset weights count as 0 (`get_attr(..., 'weight', 0)`); then two
guarded `block()` calls — full-by-count first, overweight second:

```text
@set canvas sack/on_check = mine = atype == 'item:on_put' and target is me; item = adata('item'); adding = get_attr(item, 'weight', 0); held = len(contents(me)); load = sum([get_attr(o, 'weight', 0) for o in contents(me)]); cap = V('capacity', 3); limit = V('weight_limit', 10); block(f'The {name(me)} is stuffed full - {cap} items is its limit.') if mine and held >= cap else None; block(f'At {adding} lbs that would overload the {name(me)} ({load} of {limit} lbs used).') if mine and held < cap and load + adding > limit else None
```

And the friendly running total — an `ON_PUT` *reaction* on the sack.
One timing fact worth learning here: event hooks fire while the action
is being gated, **before** the item actually moves, so the script
counts `contents + 1`:

```text
@set canvas sack/on_put = pemit(enactor, f'The {name(me)} now holds {len(contents(me)) + 1} of {V("capacity", 3)} items.')
```

Props to test with — weights are just attributes (the bottle cap and
spoon deliberately have none, so they weigh 0 and only the item count
stops them):

```text
@create pebble
@set pebble/weight = 1
@create brick
@set brick/weight = 4
@create lead ingot
@set lead ingot/weight = 8
@create bottle cap
@create rusty spoon
```

## Try it

`@create` leaves the props in your inventory, so stow away:

```text
put pebble in canvas sack
put brick in canvas sack
put lead ingot in canvas sack
put bottle cap in canvas sack
put rusty spoon in canvas sack
look canvas sack
close canvas sack
get pebble from canvas sack
open canvas sack
get pebble from canvas sack
```

Expected beats: pebble and brick go in with running totals (`The
canvas sack now holds 2 of 3 items.`); the 8 lb ingot is refused with
the math — `At 8 lbs that would overload the canvas sack (5 of 10 lbs
used).` — and stays in your hands; the weightless bottle cap fits
(3 of 3); the spoon hits the count wall — `The canvas sack is stuffed
full - 3 items is its limit.`; `look` shows `It bulges around 3 items.`
plus the contents list; while closed, both `put` and `get ... from`
answer `canvas sack is closed.`; open it and the pebble comes back out.

## Going further

- **Volume too:** give items a `bulk` attribute and add a third guarded
  `block()` — the ward pattern extends to any per-item quantity.
- **Straining seams:** in the `[[...]]` description block, append
  `' Its seams are straining.'` when `load > limit * 0.8`.
- **A locked footlocker:** add `key_id`/`locked` attributes and the
  stock `lock`/`unlock`/`open` commands gate it exactly like the
  [lockable door](025_lockable_door.md) — containers and doors share
  the closed/locked machinery.
- **Nested weight:** make the load sum recurse one level into contained
  containers — or decide, as many games do, that a sack of sacks is a
  problem for the philosophers.
