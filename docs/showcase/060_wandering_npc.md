# 060. Wandering NPC

> Checklist item 60 ([now]): *wandering behavior, zone confinement*

**What you'll build:** an NPC that ambles randomly through the town on
the world tick, refusing to enter no-go rooms and never straying out of
its home zone.
**Concepts:** the built-in `wandering` behavior and its parameters,
`zone:` tags as a movement leash, `no_wander` room tags, and live
re-tuning with `@behavior/set`. Its deterministic sibling, a fixed
route rather than a random walk, is the
[patrolling guard](061_patrolling_guard.md).

## How it works

The finished NPC has no script attributes at all: it is a plain object
with one behavior attached, and everything it does comes from that
behavior plus a handful of tags on the rooms. This section covers where
the behavior lives, how it chooses a step, and how two default
parameters turn ordinary tags into a leash.

REALM ships a `wandering` behavior in the engine kit, and
`@behavior/list` prints every registered behavior by name. Attached to
any object, it wakes on the world tick and, on a countdown set by its
`pause` parameter, rolls its `wander_chance` and, if the roll succeeds,
walks one random open exit. That walk goes through the real movement
pathway rather than teleporting the NPC, so a `closed` door is skipped
and the destination's ENTER and TELEPORT locks are checked exactly as
they are for a player. The behavior is engine-driven Python, not a
softcode reactive hook, so there is no event to guard and no
`target is me` check to write.

Confinement costs nothing extra, because it is built from tags the
engine already respects:

- **`stay_in_zone`** (default on): the wanderer only takes exits whose
  destination shares a `zone:` tag with the room it is standing in. Tag
  your streets `zone:town` and the town is the leash, with no
  coordinates and no room lists. A room carrying no `zone:` tag at all
  is therefore off the map to a zone-confined wanderer, since it shares
  no zone with anything.
- **`avoid_tags`** (default `['no_wander']`): destinations carrying any
  of these tags are never entered. One `@tag here = no_wander` in the
  Back Alley keeps every wanderer out, forever, including ones you build
  next year.

All state is the tick countdown, and it lives in an ordinary attribute
on the NPC (`@examine` shows `wander_wait`), so it survives restarts and
there is nothing to clean up.

## Build it

Dig the streets first. From your workroom, cut The Square and give it a
zone:

```text
@dig The Square = square, back
square
@zone here = town
```

`@zone here = town` is sugar for tagging the room `zone:town`, the same
tag the wanderer, and later the [Town Watch](071_guard_response.md)
(item 71), will read. Now add two more streets and two deliberate traps
for the wanderer, an in-zone room we forbid and an exit that leaves the
zone entirely:

```text
@dig Lamplight Lane = lane, square
@dig The Gates = gates, square
lane
@zone here = town
@dig Back Alley = alley, lane
alley
@zone here = town
@tag here = no_wander
```

The Back Alley is in the zone but flagged `no_wander`; The Gates room
got no `@zone` line at all, so to a zone-confined wanderer the world
simply ends there. Walk back to The Square and make the NPC:

```text
lane
square
@create scamp
@desc scamp = A scruffy kid, all elbows and pockets.
@tag scamp = npc
drop scamp
```

That last shell drops the scamp on the ground where he can move; an NPC
still in your inventory has no exits to take. One line attaches the
brain and tunes it in the same breath: `pause:2` rolls a move every
third world tick, and `wander_chance:0.5` takes the step only half the
time even then, which is an amble rather than a patrol:

```text
@behavior scamp = wandering, pause:2, wander_chance:0.5
```

## Try it

Stand in the Square and wait a few ticks; the scamp will slouch off
toward Lamplight Lane and, eventually, back. He will never appear in the
Back Alley or by The Gates. Watching paint dry? Re-tune the attached
behavior live, which keeps its countdown state rather than resetting it:

```text
> @behavior/set scamp = wandering, pause:0, wander_chance:1
Updated 'wandering' on scamp: {"pause": 0, "wander_chance": 1}.

> @behavior scamp
Behaviors on scamp:
  wandering  {"pause": 0, "wander_chance": 1}
```

Now he moves every tick, and `@behavior scamp` shows the parameters you
set. However long you watch, he ping-pongs among the zoned streets: the
alley's `no_wander` tag and the unzoned Gates room fence him in.

To take him out of the streets, detach the behavior:

```text
> @behavior/remove scamp = wandering
Removed behavior 'wandering' from scamp.
```

One caution on stopping him: `@tag scamp = halt` freezes an object's
softcode (its `$`-triggers, listen triggers, and any `script_ticker`
`on_tick`), but it does not stop an engine-driven behavior like
`wandering`, which keeps moving him regardless. Detaching the behavior,
as above, is the way to actually halt the walk.

## Going further

- **Several at once:** `@clone scamp` copies attributes, tags, and
  behaviors, so three clones wander independently with no extra work.
- **Ambient flavor:** add a second brain on its own clock with
  `@behavior scamp = script_ticker, interval:10` and
  `@set scamp/on_tick = pose kicks a loose cobble.` A wanderer that
  mutters feels more alive than a silent one. This `on_tick` runs as
  softcode, so unlike the walk it does answer to `@tag scamp = halt`.
- **Night curfew:** combine with the [town clock](068_npc_schedule.md)
  (item 68) and gate the `on_tick` pose, or detach `wandering`
  entirely, by the hour, so the scamp only haunts the streets after
  dark.
- **Different leash:** `avoid_tags` takes any list, so
  `@behavior/set scamp = wandering, avoid_tags:["no_wander", "indoors"]`
  keeps him outside without touching the zone.
