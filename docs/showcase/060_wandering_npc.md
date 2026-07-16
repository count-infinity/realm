# 060. Wandering NPC

> Checklist item 60 — [now] — *wandering behavior, zone confinement*

**What you'll build:** an NPC that ambles randomly through the town on
the server heartbeat, refusing to enter no-go rooms and never straying
out of its home zone.
**Concepts:** the built-in `wandering` behavior and its params, `zone:`
tags as a movement leash, `no_wander` room tags, live re-tuning with
`@behavior/set`.

## How it works

REALM ships a `wandering` behavior in the engine kit (`@behavior/list`
shows the whole kit). Attached to any object, it wakes on the world
tick and — every `pause` ticks, with probability `wander_chance` —
walks one random open exit. The walk goes through the *real* movement
pathway: locks, closed doors, and other NPCs' guard behaviors apply to
it exactly as they do to players.

Confinement costs nothing extra, because it's built from tags the
engine already respects:

- **`stay_in_zone`** (default on): the wanderer only takes exits whose
  destination shares a `zone:` tag with the room it's standing in. Tag
  your streets `zone:town` and the town *is* the leash — no
  coordinates, no room lists.
- **`avoid_tags`** (default `['no_wander']`): destinations carrying any
  of these tags are never entered. One `@tag here = no_wander` in the
  Back Alley keeps every wanderer out, forever, including ones you
  build next year.

All state (the tick countdown) lives in ordinary attributes on the NPC
(`@examine` shows it), so it survives restarts and there is nothing to
clean up.

## Build it

Dig the streets first. From your workroom:

```
@dig The Square = square, back
square
@zone here = town
```

`@zone here = town` is sugar for tagging the room `zone:town` — the
same tag the wanderer, and later the Town Watch (item 71), will read.
Two more streets and two deliberate traps for our wanderer — an
in-zone room we forbid, and an exit that leaves the zone entirely:

```
@dig Lamplight Lane = lane, square
@dig The Gates = gates, square
lane
@zone here = town
@dig Back Alley = alley, lane
alley
@zone here = town
@tag here = no_wander
```

The Back Alley is *in* the zone but flagged `no_wander`; The Gates room
got no `@zone` line at all, so to a zone-confined wanderer the world
simply ends there. Walk back and make the NPC:

```
lane
square
@create scamp
@desc scamp = A scruffy kid, all elbows and pockets.
@tag scamp = npc
drop scamp
@behavior scamp = wandering, pause:2, wander_chance:0.5
```

That last line attaches the brain and tunes it in one go: roll a move
every 3rd world tick (`pause:2`), and only half the time even then —
an amble, not a patrol.

## Try it

Stand in the Square and wait a few beats; the scamp will slouch off
toward Lamplight Lane and, eventually, back. He will never appear in
the Back Alley or by The Gates. Watching paint dry? Re-tune the
attached behavior live, without losing its state:

```
@behavior/set scamp = wandering, pause:0, wander_chance:1
@behavior scamp
```

Now he moves every tick and `@behavior scamp` shows the params you set.
However long you watch, he ping-pongs between the Square and the Lane:
the alley's `no_wander` tag and the unzoned Gates room fence him in.
To freeze him for maintenance: `@tag scamp = halt` (and `@untag` to
release), or `@behavior/remove scamp = wandering` to take the brain
back out.

## Going further

- **Several at once:** `@clone scamp` copies attributes, tags, *and
  behaviors* — three clones wander independently, no extra work.
- **Ambient flavor:** add a second brain on its own clock —
  `@behavior scamp = script_ticker, interval:10` and
  `@set scamp/on_tick = pose kicks a loose cobble.` A still NPC that
  mutters feels more alive than a silent one.
- **Night curfew:** combine with item 68's clock —
  gate the on_tick pose (or detach `wandering` entirely) by the hour,
  so the scamp only haunts the streets after dark.
- **Different leash:** `avoid_tags` takes any list —
  `@behavior/set scamp = wandering, avoid_tags:["no_wander", "indoors"]`
  keeps him outside without touching the zone.
