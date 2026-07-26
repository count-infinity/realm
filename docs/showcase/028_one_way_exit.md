# 028. One-Way Exit

> Checklist item 28 ([now]): *single exits, ON_LEAVE/ON_ARRIVE message overrides*

**What you'll build:** A laundry chute. Step into it upstairs, land in the
laundry vault below, and find that the way you came down is not a way back up,
with a greased dead-end `up` exit standing ready to explain itself.

**Concepts:** exits as one-way edges (`@dig` with a single directionless name,
or `@open`), room [`ON_LEAVE`/`ON_ENTER`](../reference/softcode.md#lifecycle-hooks)
flavor triggers, a dead-end exit ([`create_obj`](../reference/softcode.md#fn-create_obj)
with no `destination`) and its `fail_msg`, and why a one-way room always needs
some way out.

## How it works

A one-way passage in REALM is not a special kind of exit; it is the ordinary
kind, dug once instead of twice. The laundry chute drops a player from the upper
landing into the vault, the vault has no matching way back up, and the only route
home is a service stair you cut by hand. The two rooms narrate the fall with their
own hooks, and a dead-end `up` exit waits in the vault for the player who tries to
climb out. This section answers four questions: why a single `@dig` makes a
one-way edge, where the movement flavor lives, how a room could tell which exit
carried the mover, and how to build an exit that leads nowhere on purpose.

### Why one `@dig` gives you a one-way edge

A REALM exit is just an object sitting in a room with an `exit` tag and a
`destination`, so a two-way door is two of those objects, one facing each way.
When you type `@dig The Garden = north`, the engine cuts the `north` exit and
then, because `north` has a compass opposite, also cuts the return `south` leg in
the new room and pairs the two (the [lockable door](025_lockable_door.md) is built
on that pairing). Name the exit something with no compass opposite, `laundry
chute`, and `@dig` has no return direction to infer, so it digs exactly one edge.
One-way is the default here; two-way is the case the compass table triggers.
(Naming a second exit yourself, `@dig The Cellar = trapdoor, hatch`, is the other
way to ask for a return leg.)

### Where the movement flavor lives

The engine narrates every walk with two fixed lines: the mover reads `You leave
laundry chute.` as they go, and the destination room reads `{actor} arrives.` once
they land. No per-exit attribute replaces those lines. What you can do is layer
your own text on top, because the rooms witness the movement. A move is two events
in sequence (see [action phases](../design/action-phases.md)):
[`ON_LEAVE`](../reference/softcode.md#lifecycle-hooks) fires on the room the mover
is leaving while they still stand in it, and `ON_ENTER` fires on the room they land
in after they have already arrived. So the landing's `ON_LEAVE` and the vault's
`ON_ENTER` bracket the stock lines with flavor. Each hook here calls
[`pemit`](../reference/softcode.md#fn-pemit) to speak to the mover alone, guarded
by [`has_tag`](../reference/softcode.md#fn-has_tag)`(enactor, 'player')` so that
only players get the flavor and passing objects or NPCs move silently.

### How a room could tell which exit carried the mover

A movement event carries the action's payload, so a room hook can ask which exit
fired it: [`adata`](../reference/softcode.md#event-data-namespace)`('exit')` is the
exit object, with `adata('direction')` alongside it (and `adata('destination')` on
the leave event). On a room with several exits, that is how you would keep the
chute's flavor off the front door: compare `adata('exit')` to the exit that
[`get`](../reference/softcode.md#fn-get) resolves by name, `... if adata('exit') is
get('laundry chute') else None`. This build never spends that clause, because the
geometry already decides. The landing's one
exit is the chute, and the vault can only be entered by falling down it, so the
guard could never be false. Let the shape of the map do the work when it can, and
reach for `adata('exit')` the moment it cannot.

### The dead end that answers back

Players in the vault will try `up`, so give them an exit that exists but leads
nowhere. An exit object with no `destination` is a dead end, and walking it shows
the exit's `fail_msg`. The engine fires
[`ON_FAIL`](../reference/softcode.md#lifecycle-hooks) first, so softcode that wants
to react to a thwarted move still can, just before the refusal line prints.
`@open` will not make such an exit because it demands a destination, so you build
the dead end directly with one `create_obj` call and set its `fail_msg` with
[`set_attr`](../reference/softcode.md#fn-set_attr). The
[portal pair](033_portal_pair.md) uses the same programmatic exit-building.

## Build it

Dig the landing and stand in it, then dig the vault below with a single,
directionless exit name so that no return leg is created:

```text
@dig Upper Landing
@teleport me = Upper Landing
@dig The Laundry Vault = laundry chute
@desc laundry chute = A brass flap in the wall, polished by ten thousand bundles.
```

Set the landing's `ON_LEAVE` so the chute snaps shut behind a departing player.
The `has_tag` guard keeps the line to players, and `pemit` sends it to the mover
alone:

```text
@set here/on_leave = pemit(enactor, 'The flap snaps shut over your head. Gravity does the rest.') if has_tag(enactor, 'player') else None  # only players get flavor; objects and NPCs move silently
```

Drop through the chute yourself to dress the far end. You now stand in the vault,
so `here` is the vault, and its `ON_ENTER` greets the arrival:

```text
laundry chute
@set here/on_enter = pemit(enactor, 'You shoot out of the ceiling into a mountain of linen.') if has_tag(enactor, 'player') else None
```

Build the dead-end `up` exit. Because `@open` demands a destination, create the
exit directly, tag it `exit`, and give it the refusal line as its `fail_msg`:

```text
@eval up = create_obj('up', tags=['exit'], location=here); set_attr(up, 'fail_msg', 'You scrabble two feet up the greased brass and slide right back into the linen.'); result = 'dead-end dug: ' + up.id[:8]  # no destination = dead end; walking it shows fail_msg
```

Finally, give the vault a real way out, because a one-way room with no exit
strands whoever falls in. `@open` cuts a single exit, the service stair back up to
the landing:

```text
@open service stair = Upper Landing
```

The map now has a clean shape. The landing's only exit is the chute going down,
and the vault's only real exit is the stair going up and out, so each room has
exactly one leave-path. That is what makes the room flavor safe to write without
checking which exit fired it.

## Try it

```text
laundry chute       -> The flap snaps shut over your head. Gravity does the rest.
                       You leave laundry chute.
                       You shoot out of the ceiling into a mountain of linen.
look                -> Exits: up, service stair
up                  -> You scrabble two feet up the greased brass and slide
                       right back into the linen.
service stair       -> The long way around, back up to the landing.
```

The `up` exit shows in the exits line, and that is deliberate. A chute you might
climb back up is a puzzle, and the refusal text is the answer.

## Engine gaps

- The stock movement lines cannot be replaced. `You leave laundry chute.` and
  `{actor} arrives.` are fixed, and there is no `leave_msg`/`arrive_msg` attribute
  pair to swap them out, so the checklist's "message overrides" are additive room
  flavor (`ON_LEAVE`/`ON_ENTER`) layered around the stock lines rather than a
  substitution of them.

## Going further

- **A mover-side hook.** [`ON_ARRIVE`](../reference/softcode.md#lifecycle-hooks) is
  the one movement trigger that fires on the traveler rather than a room. `@set
  me/on_arrive = pemit(me, 'You check your kit.')` gives a character a personal
  arrival line anywhere they go.
- **A drop that hurts.** Fold in the [climbing exit](034_climbing_exit.md) pattern:
  put `check_skill = acrobatics` on the chute and damage in its `ON_FAIL`, so a
  fumbled drop costs HP.
- **Trapdoor variant.** Tag the chute `closed` and hide the `open` under a `$pull
  lever:` trigger, so the drop is one-way and gated at once.
- **True oubliette.** Skip the service stair and the room becomes a prison, so
  someone then needs `@teleport` or a [toll gate](030_toll_gate.md) or
  [guarded exit](031_guarded_exit.md) to control the only door in. Strand people on
  purpose or not at all.
