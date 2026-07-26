# 033. Portal Pair

> Checklist item 33 ([now]): *programmatic exit creation: create_obj + exit tag + db.destination*

**What you'll build:** A pair of linked wormholes. Step into the shimmering
portal in the Observatory and you are standing in the Shattered Crater, and
step in again to come straight back: a two-way link between two rooms that
share no wall. Two minutes later the pair collapses on a timer and the map
heals itself.

**Concepts:** exits as plain data (the `exit` tag plus a `destination` room
id), building them from softcode with
[`create_obj`](../reference/softcode.md#fn-create_obj) in one `@eval` (what
`@open` does, twice, without the walking),
[`expire`](../reference/softcode.md#fn-expire) on exits (they are ordinary
objects), [`ON_EXPIRE`](../reference/softcode.md#lifecycle-hooks) narration,
and room [`ON_ENTER`](../reference/softcode.md#lifecycle-hooks) arrival effects.

## How it works

The finished shape is two exit objects, one in each room, each pointing at the
other's room, both stamped with the same two-minute lease. Nothing here is
special exit machinery: an exit is just a tagged object with a destination, so
a script that can create objects can build doors, time them, and narrate their
end. This section answers what an exit actually is, why we build the pair in
softcode instead of with `@open`, how the collapse removes both ends cleanly,
and where the arrival flavor lives.

### What an exit actually is

An exit is an object sitting in a room's contents, tagged `exit`, carrying a
`destination` attribute that holds the far room's id. That is the whole
definition, and it is exactly what `@open` writes: it
[`create_obj`](../reference/softcode.md#fn-create_obj)s the object with
`tags=['exit']`, then [`set_attr`](../reference/softcode.md#fn-set_attr)s its
`destination` to the target room's id. (The engine also honors an in-memory
`destination_obj` reference, but world-building code stores the id string,
because only the string survives a save and reload.) A "portal pair" is then
just two such exits, one in each room, each `destination` naming the other's
room. "Linked" is geometry, not machinery: because they are ordinary exits,
walking them gets the full standard treatment, so locks, wards, and the
destination room's `on_enter` all apply.

### Why softcode instead of `@open`

`@open` builds one exit, in the room you are standing in, facing the room you
name. A wormhole wants both ends born together, ideally from a device, a spell,
or a wand pointed at a distant room. One `@eval` (or the body of any
`$`-command) does the whole job: resolve the far room by name with
[`get`](../reference/softcode.md#fn-get), create both exit objects with a
`location=`, then cross-write the two `destination`s so each points at the
other's room. These are two independent exits rather than the linked faces
`@dig` produces for a [lockable door](025_lockable_door.md), so they carry no
`partner` reference, which is why the collapse below has to lease each end on
its own.

### How the pair collapses cleanly

Because exits are ordinary objects,
[`expire`](../reference/softcode.md#fn-expire)`(o, 120)` works on them: it
stamps an `expires_at` timestamp two minutes out, and the world tick fires each
portal's [`ON_EXPIRE`](../reference/softcode.md#lifecycle-hooks) hook and then
destroys it. Each hook is a farewell
[`remit`](../reference/softcode.md#fn-remit) to the room the portal stands in.
Nobody triggers this collapse (the object expires on its own, so the hook's
`enactor` is empty), which is why it announces to
[`loc`](../reference/softcode.md#fn-loc)`(me)`, the portal's own room, rather
than to `loc(enactor)`, which would be nothing. Both ends carry the same lease,
so both die on the same tick and the map heals itself: no cleanup script, and
no orphaned half-link left pointing at a room you can no longer leave.

### Where the arrival flavor lives

Each room's [`ON_ENTER`](../reference/softcode.md#lifecycle-hooks) narrates the
tumble-out with a private [`pemit`](../reference/softcode.md#fn-pemit) to the
arriver. The room is the target of its own `on_enter`, so the hook needs no
`target is me` guard; the only filter is on the enactor,
[`has_tag`](../reference/softcode.md#fn-has_tag)`(enactor, 'player')`, so an
arriving NPC or object gets no flavor line. In these two rooms every arrival is
a portal arrival, so no finer test is needed. On a room with several exits you
would want the wormhole line only for people who came through the portal, and
the payload is right there:
[`adata`](../reference/softcode.md#event-data-namespace)`('exit')` names the
exit that delivered the mover (see the [one-way exit](028_one_way_exit.md)).
Comparing that exit's [`name`](../reference/softcode.md#fn-name) then keeps the
flavor targeted, as in
`pemit(...) if name(adata('exit')) == 'shimmering portal' else None`, so anyone
who walked in through an ordinary door arrives without it.

## Build it

Start with the shell: dig the two rooms and stand in the first. `@dig <name>`
with no exit list makes a room with no way in or out yet, which is what we
want, since the wormhole will be the only link between them.

```text
@dig The Observatory
@dig The Shattered Crater
@teleport me = The Observatory
```

Now the wormhole, in one `@eval` written as a multi-line block. It resolves the
far room by name, mints both exit faces (each born with its description through
`create_obj`'s `description=`), cross-writes the two destinations so each points
at the other's room, then loops over both faces to lease them for 120 seconds
and hang the collapse line on each. The `on_expire` value is itself a script
stored as a string, so it uses double quotes and its own single-quoted message
stays intact:

```text
@eval '''
far = get('The Shattered Crater')
blurb = 'A lens of folded starlight. Things on the far side swim in it.'
a = create_obj('shimmering portal', tags=['exit'], location=here, description=blurb)
b = create_obj('shimmering portal', tags=['exit'], location=far, description=blurb)
set_attr(a, 'destination', far.id)   # a points at the far room...
set_attr(b, 'destination', here.id)  # ...b points back; the crossed ids are the whole link
for o in (a, b):
    expire(o, 120)  # same 120s lease on both faces, so no half-link outlives the other
    set_attr(o, 'on_expire', "remit(loc(me), 'The wormhole snaps shut with a thunderclap.')")
result = f'wormhole open: {a.id[:8]} <-> {b.id[:8]}'
'''
```

Then the arrival flavor, one line per room. Set the near room's `on_enter`,
walk the portal you just opened to reach the far room, set its `on_enter`, and
walk back. `@set here/...` always means the room you are standing in, so the
same line configures whichever side you are on:

```text
@set here/on_enter = pemit(enactor, 'You tumble out of the wormhole, ears popping.') if has_tag(enactor, 'player') else None  # only players get the flavor; NPCs and objects arrive silently
shimmering portal
@set here/on_enter = pemit(enactor, 'You tumble out of the wormhole, ears popping.') if has_tag(enactor, 'player') else None  # only players get the flavor; NPCs and objects arrive silently
shimmering portal
```

That walk in the middle is the point: the portal was traversable the instant
the `@eval` finished, in both directions, so you reach the far room simply by
using the exit you just built. The second walk leaves you back in the
Observatory where you started.

## Try it

Walk the loop and watch each room's arrival line fire:

```text
look                -> Exits: shimmering portal      (a real exit in the room's contents)
shimmering portal   -> "You leave shimmering portal." then The Shattered Crater,
                       "You tumble out of the wormhole, ears popping."
shimmering portal   -> and straight back to the Observatory, ears popping again
```

Two minutes later, wherever you are standing:

```text
                    -> The wormhole snaps shut with a thunderclap.
look                -> Exits: None
```

Both ends die on the same world tick, so no one-way stub survives to strand
anyone in a room with no exit.

## Going further

- **A wand of wormholes.** Move the `@eval` body into a `$zap *:` command on a
  wand, with `far = get(arg0)` so the wand names its target room. Any room the
  wand's owner controls becomes a valid far end, because
  [`create_obj`](../reference/softcode.md#fn-create_obj) only seeds objects
  into rooms whose authority the owner reaches, so the owner rule polices the
  border for you.
- **Silent transit.** For a portal that should not print `You leave shimmering
  portal.`, use a dead-end exit (one with no `destination`) whose
  [`ON_FAIL`](../reference/softcode.md#lifecycle-hooks) runs
  [`move_to`](../reference/softcode.md#fn-move_to)`(enactor, far)` plus your own
  narration. A walked-into exit's `ON_FAIL` is the one case where the engine
  lets the exit relocate the walker (the walker consented by stepping in), so
  `move_to` moves them and the "leads nowhere" line is suppressed. This is the
  sanctioned portal pattern. Use `move_to`, not
  [`teleport_obj`](../reference/softcode.md#fn-teleport_obj): the forced
  teleport needs control of the player, which the exit does not have, so it
  refuses and the walker stays put.
- **Keyed wormholes.** The portals are exits, so everything in this chapter
  stacks on them: a [keycard ward](026_keycard_door.md) on the crater, a
  [toll](030_toll_gate.md) on the lens, or a `closed` tag the portal only drops
  at night.
- **One-way rift.** Create only `a`. Half a wormhole is a
  [one-way exit](028_one_way_exit.md) with better scenery.
