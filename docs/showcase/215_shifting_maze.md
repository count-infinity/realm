# 215. Shifting maze

> Checklist item 215 — now — *on_tick exit relinking, programmatic exits, anti-frustration design*

**What you'll build:** A maze whose walls move. One archway in the
entrance hall leads to a different chamber every few beats, cycling
through the maze until — reliably, never by luck — it swings open on the
way out. The tutorial is as much about **fairness** as about the trick:
a maze that shifts randomly and silently is misery, so we build in three
guarantees that keep it fun.

**Concepts:** relinking an exit's `destination` on a timer with
`script_ticker` + `on_tick`, exits as plain data (the
[portal pair](033_portal_pair.md)'s lesson), and the design discipline of
**anti-frustration guarantees**: solvable, escapable, telegraphed.

## How it works

An exit is just an object tagged `exit` with a `destination` attribute
([item 33](033_portal_pair.md)). Nothing stops you from *rewriting* that
attribute — so a maze is one archway whose destination a heartbeat keeps
changing:

1. **A warden holds the cycle.** A `maze warden` object carries a `pool`
   of room ids and runs `on_tick` via the `script_ticker` behavior. Each
   tick it advances the `shifting arch`'s `destination` to the next room
   in the pool. The arch is unchanged as an object — same name, same
   room — only where it *leads* moves.

2. **Guarantee 1 — always solvable.** The exit room (`The Way Out`) is
   *in the pool*. Because the cycle is a rotation, the arch points at the
   exit once every full loop — so a player who simply waits and watches
   will always get out. A maze you can't escape by persistence isn't a
   puzzle, it's a bug.

3. **Guarantee 2 — no dead ends.** Every chamber has a fixed `back` exit
   to the entrance hall (a normal `@open`, never touched by the warden).
   A wrong turn costs a few seconds, not the run — the player is never
   stranded somewhere the shifting can't reach them.

4. **Guarantee 3 — telegraphed.** The warden `remit`s a grinding-walls
   line to the hall each time it shifts, so the map never changes under a
   player in silence. They *see* it move and can re-read the arch.

Driving the relink from `on_tick` means the logic is one `@set`-able
attribute and the scheduling rides the server's single heartbeat — no
per-exit timers to leak.

## Build it

The entrance hall, three chambers, and the way out. Dig the chambers
*unlinked* — only the shifting arch (and the fixed `back` exits) will
reach them, so there's no bypass:

```text
@dig Maze Entrance = enter maze, out
enter maze
@dig Chamber of Echoes
@dig Chamber of Dust
@dig The Way Out
```

Give each chamber a fixed way back, and the exit room a door to freedom
(guarantee 2):

```text
@teleport me = Chamber of Echoes
@open back = Maze Entrance
@teleport me = Chamber of Dust
@open back = Maze Entrance
@teleport me = The Way Out
@desc The Way Out = Blessed daylight -- the maze spits you out at last.
@open leave = Limbo
@teleport me = Maze Entrance
```

The warden, wired with the cycle pool and the arch's starting
destination in one `@eval` (resolving rooms by name, storing `#id`
strings the tick can rotate):

```text
@create maze warden
drop maze warden
@desc maze warden = A slab of clockwork gears set into the wall, forever turning.
@eval e = get('Chamber of Echoes'); d = get('Chamber of Dust'); w = get('The Way Out'); set_attr(get('maze warden'), 'pool', ['#' + e.id, '#' + d.id, '#' + w.id]); result = 'pool wired'
```

The shifting arch — a real exit in the hall — pointed at the first pool
room to start:

```text
@create shifting arch
@tag shifting arch = exit
drop shifting arch
@desc shifting arch = A stone archway whose far side shimmers like heat-haze; you can never quite tell where it opens.
@eval set_attr(get('shifting arch'), 'destination', get_attr(get('maze warden'), 'pool')[0][1:]); result = 'arch aimed'
```

The heartbeat — rotate the destination and announce it (guarantees 1 and
3):

```text
@set maze warden/on_tick = pool = get_attr(me, 'pool'); arch = get('shifting arch'); cur = '#' + str(get_attr(arch, 'destination')); nxt = pool[(pool.index(cur) + 1) % len(pool)] if cur in pool else pool[0]; set_attr(arch, 'destination', nxt[1:]); remit(loc(arch), 'The walls grind and the shifting arch swings toward a new chamber.')
@behavior maze warden = script_ticker, interval:15
```

## Try it

Stand in the Maze Entrance and walk the arch — you land in whatever
chamber it currently leads to:

```text
shifting arch        -> the Chamber of Echoes
back                 -> the Maze Entrance          (no dead ends)
```

Every fifteen seconds the walls grind and the arch re-aims. Watch it
cycle Echoes → Dust → The Way Out → Echoes… and step through when it
points at daylight:

```text
                     -> The walls grind and the shifting arch swings toward a new chamber.
shifting arch        -> The Way Out
leave                -> out of the maze
```

Because the exit room is always in the rotation, patience alone wins —
the maze delays you, it never defeats you.

## Going further

- **A hint token** — a `worn compass` whose `$read compass` `pemit`s the
  arch's current destination name; now the maze rewards *timing* your
  step, not blind luck.
- **Bigger mazes** — give several rooms their own shifting exits and one
  warden that reshuffles all of them each tick, keeping the goal in every
  room's pool so the whole graph stays connected (the fairness invariant
  scales).
- **Shift on entry, not on a clock** — move the relink into the hall's
  `ON_ENTER` so the maze rearranges each time someone arrives, making it
  reactive rather than timed.
- **Randomize** — swap the rotation for `pool[rand(0, len(pool) - 1)]`,
  but *keep* the goal in the pool so guarantee 1 holds — the difference
  between a hard maze and an unfair one.
- **Reset** — [item 218](218_puzzle_reset.md) re-aims the arch to its
  start and stops the churn while the maze is being re-set.
