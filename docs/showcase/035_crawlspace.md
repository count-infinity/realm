# 035. Size-Restricted Crawlspace

> Checklist item 35 ([now]): *stat-reading wards, helpful block() text*

**What you'll build:** A crawlspace between a cellar and a smugglers' nook
that only admits the lightly burdened. The ward weighs everything you carry,
and if you don't fit it tells you exactly by how much, in both directions, so
hauling loot *out* is the real puzzle.

**Concepts:** an [`on_check`](../design/action-phases.md) ward that computes
over the actor's inventory (a sum across
[`contents`](../reference/softcode.md#fn-contents)`(actor)`), attribute
conventions used as physics (`weight` on items, `max_load` on the exit),
numeric refusal text as game design, and the same ward stanza deployed on
both faces (the two-sided trick from the
[lockable door](025_lockable_door.md)).

## How it works

The crawlspace is one exit dug into two rooms, plus a short ward on each room.
The ward weighs whatever the walker is carrying, compares that against the
tunnel's limit, and refuses the crossing when the load is too great, quoting
both numbers so the refusal reads as a plan. This section answers four
questions: where the notion of "too heavy" comes from, where the limit lives,
why the identical ward line goes on both rooms, and why the refusal text does
arithmetic.

### Where does "too heavy" come from?

REALM ships no weight system, deliberately. An item's `weight` is just an
attribute, and the crawlspace is the first thing that cares about it. The ward
defines the rule locally by summing the weights of everything the actor
carries:

```
sum(int(get_attr(o, 'weight', 1)) for o in contents(actor))
```

[`contents`](../reference/softcode.md#fn-contents)`(actor)` is the walker's
inventory, and [`get_attr`](../reference/softcode.md#fn-get_attr)`(o,
'weight', 1)` reads each item's weight with a default of 1, so every unmarked
trinket still counts for a little and only the heavy props need an explicit
`weight`. Reads are open and a ward may compute, so ten different chokepoints
could weigh the world ten different ways with no shared framework.

### Where the tunnel's limit lives

The limit, `max_load`, is data on the crawlspace exit itself, so
`@set narrow crawlspace/max_load = 8` re-bores the tunnel without touching the
ward. The ward reads it fresh at every crossing with the same
`get_attr(..., 'max_load', 5)` call, defaulting to 5 if a face was never set.

### Why the same ward goes on both rooms

A walk is gated by actions that target **rooms**, not the exit: the engine
fires `event:on_leave` on the room you are leaving and `event:pre_enter` on
the room you are entering, each carrying the exit in its payload. An
[`on_check`](../design/action-phases.md) ward on the exit object itself never
runs for a traversal, because the exit is only a bystander to those actions,
and bystanders do not run their `on_check` softcode. So the ward lives on the
rooms.

Both faces of the crawlspace share the name `narrow crawlspace`, and
[`get`](../reference/softcode.md#fn-get)`('narrow crawlspace')` resolves the
local face first. That is why the *identical*
`@set here/on_check = ...` line works in the cellar and in the nook: each copy
keys on its own local face. The key clause is the ward's guard,
[`adata`](../reference/softcode.md#event-data-namespace)`('exit') is gap`,
which does two jobs. It restricts the ward to the crawlspace, so a room with a
second exit is not weight-gated on every departure. And because `gap` is
always the local face while the leaving action carries that same local face,
it makes each room gate only its own exit as you leave it, never double-gating
the far room as you arrive. The
[`has_atag`](../reference/softcode.md#event-data-namespace)`('movement')` clause
alongside it keeps the ward off non-movement traffic such as speech, which the
room also witnesses. This is the same two-sided idea as the
[lockable door](025_lockable_door.md): name your faces alike and your scripts
stop caring which side they are on.

### Why the refusal does arithmetic

[`block`](../reference/softcode.md#event-data-namespace)`()` text is the
player's only feedback, so the ward makes it arithmetic: "12 lbs of bulk
against a 5 lb squeeze" turns a refusal into a plan, since the player can read
off that they must shed 7 lbs. Vague failure text would be a bug in disguise.

## Build it

Dig the cellar, stand in it, then dig the nook off it with a single exit name
given twice so `@dig` pairs the two faces. Set the load limit on the near
face:

```text
@dig Dusty Cellar
@teleport me = Dusty Cellar
@dig Smugglers' Nook = narrow crawlspace, narrow crawlspace
@set narrow crawlspace/max_load = 5
```

Now the cellar-side ward. It weighs the walker, resolves the local face, and
blocks the crossing when the load exceeds the squeeze, quoting both numbers.
The `adata('exit') is gap` guard is what keeps the ward keyed to the
crawlspace rather than to every walk out of the room:

```text
@set here/on_check = '''
load = sum(int(get_attr(o, 'weight', 1)) for o in contents(actor))
gap = get('narrow crawlspace')
squeeze = int(get_attr(gap, 'max_load', 5))
# only real walks through THIS face, never other exits or speech
if has_atag('movement') and adata('exit') is gap and load > squeeze:
    block(f"You wedge fast: {load} lbs of bulk against a {squeeze} lb squeeze. Shed some kit.")
'''
```

Crawl through empty-handed (nothing weighs anything, so you fit) and give the
nook the same two lines. The nook's crawlspace face is a *separate object*
from the cellar's, so it needs its own `max_load`, and
`get('narrow crawlspace')` in the ward now resolves to this side's face:

```text
narrow crawlspace
@set narrow crawlspace/max_load = 5
@set here/on_check = '''
load = sum(int(get_attr(o, 'weight', 1)) for o in contents(actor))
gap = get('narrow crawlspace')
squeeze = int(get_attr(gap, 'max_load', 5))
if has_atag('movement') and adata('exit') is gap and load > squeeze:
    block(f"You wedge fast: {load} lbs of bulk against a {squeeze} lb squeeze. Shed some kit.")
'''
narrow crawlspace
```

That last `narrow crawlspace` walks you back to the cellar. Finally, stock the
nook with something worth the trouble, a strongbox too heavy to leave with.
[`create_obj`](../reference/softcode.md#fn-create_obj) stamps the `weight` on
at birth via its `attrs` argument, so one call mints the whole item into the
nook:

```text
@eval create_obj('strongbox', tags=['thing'], location=get("Smugglers' Nook"), attrs={'weight': 9})
```

## Try it

Carrying two 3-lb crates:

```text
> narrow crawlspace
You wedge fast: 6 lbs of bulk against a 5 lb squeeze. Shed some kit.
> drop crate
> narrow crawlspace
(3 lbs slides fine, and you crawl through into the nook)
> get strongbox
> narrow crawlspace
You wedge fast: 12 lbs of bulk against a 5 lb squeeze. Shed some kit.
```

That last refusal is the design. The way in is easy when you travel light, and
the 9-lb prize does not fit through a 5-lb hole. Smuggling becomes a logistics
problem: open the strongbox and ferry the contents, or find the *other*
entrance. The ward does not care; it just does the arithmetic, every crossing,
both directions.

## Going further

- **Small races fit better.** Add the body to the sum with
  `load + int(get_attr(actor, 'girth', 0))` and set `girth` in chargen. A
  halfling's 0 against an ogre's 6 makes the crawlspace a species filter with
  no extra machinery.
- **Grease the squeeze.** A `$grease crawlspace:` command that bumps `max_load`
  by 3 for a minute (a `set_attr` plus a [timed-door](029_timed_door.md)
  ticket to revert) pits consumables against geometry.
- **Escaping wriggle-check.** Replace the flat limit with a skill roll inside
  the ward, `skill_check(actor, 'escape_artist', 5 - load)`, since wards may
  roll dice. Margins make near-fits chancy instead of binary.
- **Weigh-station variant.** The same ward on a cargo gate, reading
  `credits(actor)` instead of weight, is an excise gate that taxes by the
  pound: this tutorial plus the [toll gate](030_toll_gate.md).
