# 014. Basic Container

> Checklist item 14 ([now]): *container tag, on_check wards, block(), weight-attr conventions*

**What you'll build:** A canvas sack that holds at most 3 items and 10 lbs.
Overfill it and you get a specific, numeric refusal, and the refusal comes
from the engine's own permission pass, not from any command's good manners.

**Concepts:** the `container` tag and the built-in `put`/`get from`/
`open`/`close` machinery, **`on_check` wards** (the softcode veto that runs
in the engine's permission pass) with
[`block()`](../reference/softcode.md#event-data-namespace), action inspection
([`atype`, `target`, `adata`](../reference/softcode.md#event-data-namespace)),
summed `weight` attributes, and an
[`ON_PUT`](../reference/softcode.md#lifecycle-hooks) reaction for friendly
feedback.

This is the first build in the arc that *intercepts* the engine instead of
adding commands to it. It leans on the
[vending machine](002_vending_machine.md) for the `weight` attributes its
products carry, and on the [slot machine](001_slot_machine.md) for reading
an action's payload.

## How it works

The finished sack is one tag, two data attributes, one ward, and one
reaction. The tag turns on the engine's container verbs, the attributes hold
the limits, the ward vetoes any `put` that would break them, and the
reaction reports the running total. This section answers three questions:
what the tag already does, where weight lives when the engine has none, and
how a script gets to say no to the engine itself.

### What does the `container` tag already give you?

Tag a thing `container` (it is a tag, not an attribute) and the stock
commands do the rest: `put <item> in <it>`, `get <item> from <it>`, and
`open`/`close`, where the `closed` tag refuses both directions, and `look`
lists the contents of an open container. That is a complete working
container with zero scripting.

### Where does capacity live, if the engine weighs nothing?

Nothing checks capacity yet, because REALM deliberately has no weight
kernel. Weight is a *convention*: items carry a `weight` attribute (the
[vending machine](002_vending_machine.md)'s prototypes stamp one on every
product) and anything that cares sums them. The sack's two limits are
likewise plain data, a `capacity` count and a `weight_limit`, so a bigger
sack is a `@set`, not a script edit.

### How does a script veto the engine?

The enforcement point is the **ward**: an `on_check` attribute runs during
the engine's *permission pass*, before the effect happens, on every action
this object participates in (as target, actor, or room). Inside it you get
a read-only view of the world plus the in-flight action:
[`atype`](../reference/softcode.md#event-data-namespace) (the action type
string), `target`, `actor`, and `adata(key)` for its payload. You also get
one power the reaction pass never has: `block(reason)`. A blocked action
never happens, and the actor is told why.

Wards are decision-only *by construction*: the check-pass namespace has no
`set_attr`, no `say`, no `create_obj`, so a ward can veto but cannot act.
Reactions belong in [`ON_<EVENT>`](../reference/softcode.md#lifecycle-hooks)
scripts, which fire only if the action was not blocked and see the same
`atype`/`target`/`actor`/`adata` names (the
[slot machine](001_slot_machine.md) reads `adata('amount')` that way). The
difference is direction, not visibility: a ward alone gets `block()`, and a
reaction alone gets to change the world. The split is the engine's
before/apply/after trio ([action phases](../design/action-phases.md)):
`on_check` sees the world before the effect, `ON_<EVENT>` runs once the
decision is made. Locks and Python behaviors run in this same permission
pass, which is what makes the rule a law of physics rather than a
politeness observed by well-behaved commands: every `put`, typed by a
player or driven by a script, funnels through the same check.

### One ward, two rules

The `put` action arrives as `atype == 'item:on_put'` with the sack as
`target` and the item in `adata('item')` (see the
[payload table](../reference/softcode.md#guard-on-target)). The ward
filters to exactly that case, computes the current load, then blocks on
item count or on weight, each with the numbers in the message. Vague errors
are the number one way container builds frustrate players, so say *why*,
with math.

## Build it

The two scripts here are `'''` multi-line blocks (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)).

**The sack.** Create it and give it a living face: the `[[...]]` block in
the description runs per look, so it counts the contents fresh with
[`contents(me)`](../reference/softcode.md#fn-contents) every time:

```text
@create canvas sack
drop canvas sack
@desc canvas sack = A patched canvas sack. [[n = len(contents(me)); result = f'It bulges around {n} item{"" if n == 1 else "s"}.']]
```

**Built-in behavior plus the limits as plain data.** The `container` tag
switches on the stock verbs, and the two limits are ordinary attributes the
ward will read:

```text
@tag canvas sack = container
@set canvas sack/capacity = 3
@set canvas sack/weight_limit = 10
```

**The ward.** Its steps in order: filter to "someone is putting something
into *me*", read the incoming item and its weight with
[`get_attr`](../reference/softcode.md#fn-get_attr) (defaulting unset
weights to 0), sum the current load, then block on count first and weight
second. [`V('capacity', 3)`](../reference/softcode.md#fn-v) is shorthand
for `get_attr(me, 'capacity', 3)`, and
[`name(me)`](../reference/softcode.md#fn-name) keeps the messages honest on
a renamed sack:

```text
@set canvas sack/on_check = '''
if atype == 'item:on_put' and target is me:  # the ward hears every action this sack is part of, so filter to puts aimed at it
    item = adata('item')
    adding = get_attr(item, 'weight', 0)  # an unset weight reads as 0
    held = len(contents(me))
    load = sum([get_attr(o, 'weight', 0) for o in contents(me)])
    cap = V('capacity', 3)
    limit = V('weight_limit', 10)
    if held >= cap:
        block(f'The {name(me)} is stuffed full - {cap} items is its limit.')
    elif load + adding > limit:
        block(f'At {adding} lbs that would overload the {name(me)} ({load} of {limit} lbs used).')
'''
```

That first line earns its length. The ward fires for *every* action the
sack participates in (getting the sack itself arrives as `item:on_get`),
so without the `atype` filter a full sack would refuse to be picked up,
and without [`target is me`](../reference/softcode.md#guard-on-target) it
would answer for actions aimed elsewhere. Write `is`, not `==`: it is an
identity check.

**The friendly running total.** An `ON_PUT` *reaction* on the sack tells
the putter where they stand, via
[`pemit`](../reference/softcode.md#fn-pemit). It needs the same guard,
because `ON_PUT` fires on every object in the room: unguarded, a second
sack standing nearby would announce its own count whenever you fed this
one. Like every reaction hook, it sees the world *after* the effect (the
[action-phases trio](../design/action-phases.md)), so the item it reports
is already inside and [`contents(me)`](../reference/softcode.md#fn-contents)
counts it:

```text
@set canvas sack/on_put = '''
if target is me:  # ON_PUT fires on every object in the room, so guard it
    pemit(enactor, f'The {name(me)} now holds {len(contents(me))} of {V("capacity", 3)} items.')
'''
```

**Props to test with.** Weights are just attributes. The bottle cap and
spoon deliberately have none, so they weigh 0 and only the item count stops
them:

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

`@create` leaves the props in your inventory, so stow away. The count line
arrives from the `ON_PUT` hook, the "You put" line from the command itself:

```text
> put pebble in canvas sack
The canvas sack now holds 1 of 3 items.
You put a pebble in the canvas sack.

> put brick in canvas sack
The canvas sack now holds 2 of 3 items.
You put a brick in the canvas sack.

> put lead ingot in canvas sack
At 8 lbs that would overload the canvas sack (5 of 10 lbs used).

> put bottle cap in canvas sack
The canvas sack now holds 3 of 3 items.
You put a bottle cap in the canvas sack.

> put rusty spoon in canvas sack
The canvas sack is stuffed full - 3 items is its limit.
```

The 8 lb ingot is refused with the math and stays in your hands, because a
blocked action never happens. The weightless bottle cap fits, and the spoon
hits the count wall instead. Now read the sack and work the hatch:

```text
> look canvas sack
canvas sack
A patched canvas sack. It bulges around 3 items.

Contains:
  pebble
  brick
  bottle cap

> close canvas sack
You close the canvas sack.

> put rusty spoon in canvas sack
canvas sack is closed.

> get pebble from canvas sack
canvas sack is closed.

> open canvas sack
You open the canvas sack.

> get pebble from canvas sack
You pick up a pebble.
```

While the `closed` tag is on, both directions answer `canvas sack is
closed.` with no scripting from you; open it and the pebble comes back out.

## Going further

- **Volume too:** give items a `bulk` attribute and add a third guarded
  `block()` to the ward; the pattern extends to any per-item quantity.
- **Straining seams:** in the `[[...]]` description block, append
  `' Its seams are straining.'` when the summed load passes
  `limit * 0.8`.
- **A locked footlocker:** give it a `key_id` attribute and a matching
  key, and the stock `lock`/`unlock` commands manage its `locked` tag
  exactly as on the [lockable door](025_lockable_door.md), since
  containers and doors share the closed/locked machinery.
- **Nested weight:** make the load sum recurse one level into contained
  containers, or decide, as many games do, that a sack of sacks is a
  problem for the philosophers.
