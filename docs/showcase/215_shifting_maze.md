# 215. Shifting maze

> Checklist item 215 ([now]): *on_tick exit relinking, mutable topology*

**What you'll build:** A maze whose walls move. One archway in the entrance
hall leads to a different chamber every few world beats, cycling through the
maze until it swings open on the way out, reliably rather than by luck. The
tutorial is as much about fairness as about the trick, because a maze that
shifts randomly and silently is misery, so three guarantees are built in to
keep it fun: solvable, escapable, telegraphed.

**Concepts:** rewriting an exit's `destination` on a timer with the
`script_ticker` behavior and an `on_tick` script, exits as plain data (the
lesson of the [portal pair](033_portal_pair.md)), a JSON list attribute used as
a rotation pool, and [`remit`](../reference/softcode.md#fn-remit) as the
telegraph that keeps a moving map fair.

## How it works

The finished shape is three objects doing one job between them. A room holds an
exit called the `shifting arch`, a `maze warden` standing in the same room holds
a list of chamber names, and once every few world beats the warden overwrites
the arch's `destination` with the id of the next room in that list. Nothing
about the arch changes except where it leads. This section answers what actually moves, why the
cycle lives on the warden rather than on the arch, how each of the three
fairness guarantees is enforced by a specific line of the build, and how fast
`interval:4` really is.

### What actually changes when the walls move?

An exit is an ordinary object sitting in a room's contents, tagged `exit`,
carrying a `destination` attribute that holds the far room's id
([item 33](033_portal_pair.md) builds a pair of them from scratch). That is the
entire definition, and `@open`, `@link`, and
[`set_attr`](../reference/softcode.md#fn-set_attr) all write the same one
attribute. So "the maze shifts" means exactly one string is rewritten: the arch
keeps its name, its description, and its place in the hall, and only the room id
in `destination` moves. Every movement path resolves that id through the same
lookup, so a walker who steps through a second after the rewrite lands in the
new chamber with no special handling anywhere.

### Why does the warden hold the cycle instead of the arch?

The `script_ticker` behavior runs an object's `on_tick` attribute on a cadence,
and any object may carry it, so the arch could in principle tick itself. Putting
it on a separate `maze warden` keeps the two roles apart: the arch is the thing
being edited and the warden is the thing doing the editing, which means you can
halt, re-tune, or destroy the clockwork without touching the door. The warden
also owns the `pool`, the ordered list of chamber names the rotation walks, so
the whole cycle is readable in one `@examine`.

The pool is a plain data attribute rather than a script, so it is set with a
one-line `@set` whose value is JSON. Write the room names in double quotes:
`@set` tries `json.loads` first and falls back to storing the raw text, so
single quotes would leave you with one long string instead of a list, and
`len(pool)` would count characters.

Because the warden and the arch share a room,
[`get`](../reference/softcode.md#fn-get)`('shifting arch')` inside the tick
resolves cheaply: name lookup searches the executor's own room and inventory
first, then the world, and takes the first match.

### How does a patient player always get out?

`The Way Out` is *in the pool*, and the rotation is a plain modular step through
the list, so the arch points at the exit room exactly once every full loop. A
player who does nothing but wait in the hall and read the arch will always get
out, which is the difference between a puzzle and a trap. The tick derives its
next position from the arch's *current* destination rather than from a counter
on the warden, so re-aiming the arch by hand with `@link` just moves the cycle
to that point and the guarantee still holds. If the arch is aimed at some room
outside the pool, the tick restarts the loop at the first chamber, so it heals
itself rather than stalling.

### What stops a wrong turn from stranding anyone?

Both maze chambers get a fixed `back` exit to the entrance hall, made with an
ordinary `@open`, which the warden never touches. Only the arch shifts. A wrong
turn therefore costs a few seconds rather than the run, because the chambers are
never cut off from the hall, and `The Way Out` has its own `leave` exit to the
world beyond the maze. Note also that the chambers are dug *unlinked*, so the
arch and those fixed `back` exits are the only ways in and out and there is no
accidental bypass.

### How does the player know the map moved?

Every shift ends with a [`remit`](../reference/softcode.md#fn-remit) of a
grinding-walls line to [`loc`](../reference/softcode.md#fn-loc)`(arch)`, the hall
the arch stands in, so the geography never changes under someone in silence.
They see it move, know to look again, and can time their step. This is the
cheapest of the three guarantees and the one players notice most.

### How fast is `interval:4`?

`script_ticker`'s `interval` counts **world beats, not seconds**. A beat is
`WORLD_TICK`, four seconds by default, so `interval:4` fires roughly every
sixteen seconds and `interval:15` would be a full minute between shifts. The
countdown persists in `db.script_tick_wait`, and every ticking behavior in the
game is driven from the server's one heartbeat loop, so adding shifting exits
adds no timers of their own to leak. For a longer worked example of the same
cadence, see the [weather system](036_weather_system.md).

## Build it

Start with the shell. Dig the entrance hall off Limbo and step into it, then dig
the three rooms beyond it with no exit list at all, which leaves them unlinked
until the arch and the `back` exits connect them:

```text
@dig Maze Entrance = enter maze, out
enter maze
@dig Chamber of Echoes
@dig Chamber of Dust
@dig The Way Out
```

Now give each chamber its fixed way home and the goal room its door to the world
outside, which is guarantee 2. Walk to each room to build in it, since `@open`
always makes the exit in the room you are standing in, and finish back in the
hall:

```text
@teleport me = Chamber of Echoes
@open back = Maze Entrance
@teleport me = Chamber of Dust
@open back = Maze Entrance
@teleport me = The Way Out
@desc The Way Out = Blessed daylight: the maze spits you out at last.
@open leave = Limbo
@teleport me = Maze Entrance
```

Next the warden, standing in the hall where the players can see the mechanism
they are up against:

```text
@create maze warden
drop maze warden
@desc maze warden = A slab of clockwork gears set into the wall, forever turning.
```

Its `pool` is the rotation, in order, and it is data rather than code, so it
stays a one-line `@set` with a JSON list. `The Way Out` sits in the pool
alongside the two dead-end chambers, and that single fact is guarantee 1:

```text
@set maze warden/pool = ["Chamber of Echoes", "Chamber of Dust", "The Way Out"]
```

The arch is built by hand rather than with `@open`, to show that an exit is only
an object with the `exit` tag: create it, tag it, drop it in the hall, describe
it, and aim it at the first room in the pool. `@link` writes the same
`destination` attribute the tick will rewrite from now on:

```text
@create shifting arch
@tag shifting arch = exit
drop shifting arch
@desc shifting arch = A stone archway whose far side shimmers like heat-haze, so you never quite tell where it opens.
@link shifting arch = Chamber of Echoes
```

The heartbeat is the one script here, and it runs four steps in order: read the
pool off the warden with [`V`](../reference/softcode.md#fn-v) and find the arch,
turn the pool's room names into room ids, read the arch's current
[`destination`](../reference/softcode.md#fn-get_attr) to work out which pool slot
it is aimed at and step one place along, then write the new id and announce the
grind. Written as a multi-line block it reads as the rotation it is:

```text
@set maze warden/on_tick = '''
pool = V('pool')
arch = get('shifting arch')
# get() checks the warden's own room first, so this is the arch standing beside it
ids = [get(room_name).id for room_name in pool]
current = get_attr(arch, 'destination')
if current in ids:
    step = (ids.index(current) + 1) % len(ids)
else:
    # the arch was re-aimed outside the pool, so restart the rotation
    step = 0
set_attr(arch, 'destination', ids[step])
remit(loc(arch), 'The walls grind, and the shifting arch swings toward a new chamber.')
'''
```

Finally, start the clockwork. `interval:4` is four world beats, so the maze
rearranges about every sixteen seconds:

```text
@behavior maze warden = script_ticker, interval:4
```

## Try it

Stand in the Maze Entrance. The arch is listed with the ordinary exits, because
it is one, and walking it takes you wherever it currently points:

```text
> look
Maze Entrance
-------------
You see:
  a maze warden
Exits: out, shifting arch

> shifting arch
You leave shifting arch.

Chamber of Echoes
-----------------
Exits: back

> back
You leave back.

Maze Entrance
-------------
Exits: out, shifting arch
```

The `back` exit is fixed, so that round trip works from either chamber no matter
what the arch is doing. Now wait in the hall and watch the warden work. Each
shift announces itself, and after two of them the arch is pointing at daylight:

```text
The walls grind, and the shifting arch swings toward a new chamber.
The walls grind, and the shifting arch swings toward a new chamber.

> shifting arch
You leave shifting arch.

The Way Out
-----------
Blessed daylight: the maze spits you out at last.
Exits: leave

> leave
You leave leave.

Limbo
-----
Exits: enter maze
```

Two results are worth confirming deliberately. The arch reaches `The Way Out` on
its own within one full loop of the pool, so waiting is always enough. And
`@examine shifting arch` between two grinds shows a single `destination`
attribute changing value while the object's name, description, and location
stay exactly where they were.

## Going further

- **A hint token.** Give the player a `worn compass` that reports where the arch
  currently opens, which turns the maze into a test of timing rather than of
  luck:

    ```text
    @set worn compass/cmd_compass = $compass: pemit(enactor, 'The needle swings toward ' + name(get('#' + get_attr(get('shifting arch'), 'destination'))) + '.')
    ```

    Two details matter. `destination` stores a bare id, so the `#` prefix is what
    makes [`get`](../reference/softcode.md#fn-get) do an exact id lookup instead
    of a name match. And the trigger word has to be one the engine does not
    already own, because builtins dispatch before `$`-commands: `$read compass`
    is swallowed by the builtin `ready`, while `$compass` reaches the script.
- **Bigger mazes.** Give several rooms their own shifting exit and let one warden
  re-aim all of them each tick by looping over a list of exit names. Keep the goal
  room in every pool and the fairness guarantee scales with the graph.
- **Shift on entry instead of on a clock.** Move the rotation into the hall's
  [`ON_ENTER`](../reference/softcode.md#lifecycle-hooks) so the maze rearranges
  whenever someone arrives. Put it on the room, not on the warden and not on the
  arch: the room is the *target* of an enter event, so a `target is me` guard on
  an object standing in that room is false every single time and the hook would
  never run, while an exit hears the `ON_LEAVE` of the room it stands in and
  never the `ON_ENTER` of the room it leads to, so the arch would see nothing at
  all. The room's own hook needs no `target is me` guard
  ([Guard on `target`](../reference/softcode.md#guard-on-target)); filter on the
  arriver instead, wrapping the body in an
  [`has_tag`](../reference/softcode.md#fn-has_tag)`(enactor, 'player')` test, so
  an NPC wandering through leaves the map alone.
- **Randomize.** Swap the modular step for
  `step = rand(0, len(ids) - 1)` using [`rand`](../reference/softcode.md#fn-rand).
  Keep the goal in the pool so guarantee 1 survives, which is the whole
  difference between a hard maze and an unfair one.
- **Reset.** [Item 218](218_puzzle_reset.md) re-aims the arch to its starting
  chamber and stops the churn while the maze is being put back in order.
