# 061. Patrolling guard

> Checklist item 61 — [now] — *patrol behavior, waypoint routes, ON_OPEN/ON_ARRIVE reactions*

**What you'll build:** Sergeant Yara, who walks a fixed round —
gatehouse, wall, battlements and back — pausing at each post. Open the
armory door in front of her and she challenges you on the spot; leave
it open behind her back and she pulls it shut, muttering, on her next
round.
**Concepts:** the built-in `patrol` behavior (`route` + `pause`
params), doors as `closed`-tagged paired exits, `ON_OPEN` as a
witnessed reaction, `ON_ARRIVE` as the mover's own arrival hook, a
`now()` cooldown attr.

## How it works

Where item 60's `wandering` rolls dice, **`patrol` follows orders**: a
`route` param lists exit *names*, and the behavior walks them in order,
looping forever, waiting `pause` ticks at each stop. Two properties do
the heavy lifting:

- **The route is topology, not coordinates.** Each step goes through
  the *real* movement pathway (`move_through_exit`), so locks, wards,
  and closed doors stop the guard exactly as they'd stop you. A blocked
  step isn't skipped — she stands and retries after the pause, which
  reads as a guard waiting at an obstacle. Close a door on her route
  and you have literally stalled the patrol.
- **State is two attributes** (`patrol_index`, `patrol_wait`) on the
  guard — `@examine` shows them, restarts don't lose them.

The door reactions are two `ON_<EVENT>` attributes on Yara herself:

- **`ON_OPEN`** fires on every *witness* of an open — the room, its
  contents, the door. If Yara is standing there when you open a door,
  her hook runs with you as `enactor`. A `now()` cooldown attr keeps
  her from barking once per hinge-creak.
- **`ON_ARRIVE`** is the mover's own hook — it fires on *her* each time
  she enters a room. Hers sweeps the room for door-flagged exits that
  lost their `closed` tag and shuts them with a scripted
  `cmd('close ...')` — which routes through the same close verb players
  use, so the whole room hears her do it and the door's own `ON_CLOSE`
  mirrors (item 25) still fire.

We flag which exits count as "doors she cares about" with a plain
`door` attribute — the sweep reads it, nothing else does. Convention as
data.

## Build it

The round: three rooms off your workroom, plus the armory behind a
paired-exit door (both faces named `armory door`, item 25's pattern):

```
@dig The Gatehouse = gatehouse, back
gatehouse
@dig The North Wall = wall, gatehouse
wall
@dig The Battlements = battlements, wall
@dig The Armory = armory door, armory door
```

Mark both faces of the door, then shut it (doors dig open):

```
@set armory door/door = 1
armory door
@set armory door/door = 1
armory door
close armory door
```

The sergeant, her round, and her two reactions — built standing on the
North Wall:

```
@create Sergeant Yara
@tag Sergeant Yara = npc
drop Sergeant Yara
@desc Sergeant Yara = Boots you could shave in. She walks the same round she has walked for nine years.
@set Sergeant Yara/on_open = (say('Who goes into the armory? State your business.'), set_attr(me, 'challenged', now())) if now() - get_attr(me, 'challenged', 0) > 20 else None
@set Sergeant Yara/on_arrive = left_open = [o for o in contents(here) if has_tag(o, 'exit') and get_attr(o, 'door', 0) and not has_tag(o, 'closed')]; [(pose('mutters about lax discipline.'), cmd('close ' + name(o))) for o in left_open]
@behavior Sergeant Yara = patrol, route:["battlements", "wall", "gatehouse", "wall"], pause:2
```

Read the route from where she stands (the North Wall): battlements,
back to the wall, down to the gatehouse, back to the wall, loop. The
armory door is *not* on her route — it's the thing she guards, not the
way she walks.

## Try it

Stand on the North Wall and let a few ticks pass: she strides off to
the battlements, waits a beat, comes back through, heads for the
gatehouse. The round never varies (`@examine Sergeant Yara` —
`patrol_index` is her place in it).

Open the door while she's present:

```
open armory door        → Sergeant Yara says, "Who goes into the armory? State your business."
open armory door        (again, within ~20s)  → silence — the cooldown attr holds
```

Now the crime she can't see: wait until she's away, open the armory
door, and stand back. On her next pass through the North Wall:

```
Sergeant Yara mutters about lax discipline.
Sergeant Yara closes the armory door.
```

And the patrol *is* physical: `close armory door` ahead of her only if
it's on a route — here it isn't, so instead try standing a second
guard or a locked door on her path and watch her wait at it, retrying
each pause, until it opens.

## Going further

- **Waypoint speeches:** add an `ON_ARRIVE` branch keyed on
  `name(here)` — a word at the gatehouse, a long stare from the
  battlements. One attr, a `switch()` on the room.
- **Shift changes:** wrap `attach_behavior`/`detach_behavior` in item
  68's clock states and Yara patrols only at night, sleeping in the
  gatehouse by day.
- **Alarm integration:** her `ON_OPEN` could `act()` a custom event to
  a zone master (item 71's watch) instead of just speaking — a patrol
  that summons the cavalry.
- **Keyed patrols:** give her the armory key (`unlocks`) and an
  `ON_ARRIVE` that `cmd('unlock ...')`/`cmd('lock ...')` — a guard who
  locks up properly behind herself, using the same key items players
  do (item 25).
