# 213. Power routing puzzle

> Checklist item 213 ([now]): *graph state in attributes, $route toggles, eval_attr win checks*

**What you'll build:** A reactor console whose three relays each feed either the
**main** or the **backup** power bus. A blown conduit leaves the obvious
straight-through routing dead, so you reroute around it exactly as the wall
schematic says, the grid comes online, and a blast shield retracts. Reroute
wrongly and the shield drops again.

**Concepts:** puzzle state held as a small graph of attributes, a `$route` verb
that moves one relay per command, and a win condition written **once** as an
attribute that [`eval_attr`](../reference/softcode.md#fn-eval_attr) runs for both
the router and a `$grid` status readout.

## How it works

Finished, the puzzle is a single console carrying five data attributes and three
scripts. `j1`, `j2`, and `j3` record which bus each relay feeds, `solution`
records the arrangement that lights the grid, and a `$route` verb rewrites
exactly one of those relays at a time. Two further attributes hold logic instead
of data, since `check` answers "is the grid solved?" and `sync` makes the blast
shield agree with that answer. The rest of this section works through where the
board lives, how one command moves one relay, why the win test is an attribute
of its own, and how the shield follows the grid in both directions.

### Where does the puzzle keep its board?

On the console, as three ordinary attributes. `j1`, `j2`, and `j3` each hold `a`
(main bus) or `b` (backup bus), and those three letters are the entire mutable
state, which makes this a combination lock whose digits happen to be
*connections*. A fourth attribute, `solution`, stores the target arrangement
`b a b` so the win test has something fixed to compare against.

Keeping the board on the console rather than on the player matters twice over.
Attributes are serialized into the database along with the rest of the object,
so a half-solved grid survives a restart, and because the console is a room
fixture, anyone who walks in picks up where the last person left off.

### How does one command move exactly one relay?

The router is a `$`-command, `$route * to *`, whose two wildcards arrive in the
script as `arg0` and `arg1`. [`trim`](../reference/softcode.md#fn-trim) tidies
each capture, and [`switch`](../reference/softcode.md#fn-switch) maps the
player-facing word onto the stored letter: `main` becomes `a`, `backup` becomes
`b`, and its trailing argument is the default, so any other word yields `''`.
That single empty-string outcome lets one `if` reject a bad bus name and a bad
junction number together, after which
[`set_attr`](../reference/softcode.md#fn-set_attr) writes the one relay that
changed. Moving one relay per command is deliberate, because reasoning about a
single connection at a time is what separates a puzzle from a guessing game.

Both verbs use free words on purpose. Builtins are dispatched *before*
`$`-triggers, so a `$`-command can never shadow `say`, `who`, or `open`, and a
verb named after something the engine already owns would simply never reach the
console.

A `$`-command also needs no [`target` guard](../reference/softcode.md#guard-on-target).
An [`ON_<EVENT>` hook](../reference/softcode.md#lifecycle-hooks) fires on *every*
object in the room and must open with `if target is me:` to react only to its
own business, but a typed command is matched against the room's objects in order
and only the **first** object whose pattern matches ever runs. Drop a second
console beside this one and give it its own `$grid`, and it stays silent while
the original answers, so the risk with duplicate patterns is one object
shadowing another rather than several misfiring at once.

### Why is the win test an attribute of its own?

Because two separate scripts need the same answer, and a rule written twice is a
rule that eventually disagrees with itself. `check` compares the three junctions
against `solution` and assigns the verdict to `result`, which is the value
[`eval_attr`](../reference/softcode.md#fn-eval_attr) hands back to its caller.
The router's `sync` and the player-facing `$grid` both evaluate
`eval_attr(me, 'check')`, so the status line and the shield can never tell
different stories.

`eval_attr` resembles PennMUSH's `u()` and deliberately departs from it. Penn
swaps the executor to the object holding the attribute, whereas REALM runs the
routine with the **caller's** authority and leaves the executor alone, which
means it cannot escalate. The practical consequence is that inside `check`, `me`
is the caller rather than the attribute's owner. That is harmless here, since
both callers are the console's own scripts and `me` is the console either way,
but a routine invoked from a *different* object would read that other object's
attributes. Use [`call`](../reference/softcode.md#fn-call) when you want the
routine to run as the object that owns it.

One property to know before you lean on a shared routine: `eval_attr` swallows
script errors and returns `None`. A typo inside `check` therefore reads as a
falsy verdict and the readout reports FAULT instead of surfacing the mistake, so
exercise a new routine on its own once before wiring the door to it.

### How does the shield follow the grid in both directions?

`sync` recomputes from scratch. Like the [weight plates](212_weight_plate.md),
it never tracks *what* changed; it asks `check` for the current truth, compares
that against the shield's current tag, and acts only on a transition. Calling it
after every reroute is therefore safe and produces exactly one announcement per
real change, which is what makes the puzzle fully reversible.

The blast shield is the `closed`+`locked` exit from
[item 209](209_lever_combination.md). The `closed` tag is what blocks the walk,
while `locked` makes the built-in `open` command refuse with your `locked_msg`,
so `open blast shield` answers "The blast shield is sealed. Route the grid to
full power first." and the only thing that ever moves the shield is `sync`'s raw
[`add_tag`](../reference/softcode.md#fn-add_tag) and
[`remove_tag`](../reference/softcode.md#fn-remove_tag). Note that `sync` toggles
`closed` alone and leaves `locked` set permanently, which is precisely what keeps
the manual `open` shortcut sealed off even while the grid is online. Walking into
the shield while the grid is faulted reports "The blast shield is closed.", the
default refusal for a closed exit.

The answer is never hidden, only deducible: it is written on the schematic
hanging on the wall, because a routing puzzle should reward reading the room.
For the propagation model these events ride on, see
[the event architecture](../architecture/events.md) and the guided tour in
[245_event_bus_tour.md](245_event_bus_tour.md).

## Build it

Dig the reactor room and the sealed bay behind the shield, then seal the shield
with the two tags that guard different doors, `closed` against the walk and
`locked` against the `open` verb:

```text
@dig Reactor Control = reactor, out
reactor
@dig The Core Bay = blast shield, reactor
@desc The Core Bay = The reactor core throbs behind shielded glass. The prize: an intact power cell.
@tag blast shield = closed
@tag blast shield = locked
@set blast shield/locked_msg = The blast shield is sealed. Route the grid to full power first.
```

Hang the wall schematic, which is the clue that makes the puzzle solvable rather
than a three-way guess:

```text
@create wall schematic
drop wall schematic
@desc wall schematic = A grease-penciled diagram. Junction 2's main line is slashed out and marked FAULT. Scrawled beside it: "Send 1 and 3 to BACKUP, keep 2 on MAIN, and she'll light."
```

Now the console and its starting board. Every relay begins on `a`, the dead
straight-through routing, and `solution` encodes backup, main, backup. These are
plain data, so each one is a single-line `@set`:

```text
@create power console
drop power console
@desc power console = A panel of three relay switches feeding the main and backup buses. ROUTE <1-3> TO <MAIN|BACKUP>, or GRID for status.
@set power console/j1 = a
@set power console/j2 = a
@set power console/j3 = a
@set power console/solution = b a b
```

The win test is one comparison, so it stays a one-liner. It joins the three
junctions into a single string and matches that against `solution`, assigning
the verdict to `result` for `eval_attr` to return:

```text
@set power console/check = result = f"{V('j1')} {V('j2')} {V('j3')}" == V('solution')
```

`sync` is the piece that drives the door. It reads the verdict, then compares it
with the shield's current tag so that an already-open shield stays quiet and an
already-closed one does too, announcing to the whole room with
[`remit`](../reference/softcode.md#fn-remit) only on a real transition:

```text
@set power console/sync = '''
live = eval_attr(me, 'check')
shield = get('blast shield')
if live and has_tag(shield, 'closed'):
    remove_tag(shield, 'closed')
    remit(loc(me), 'The grid hums up to full power. The blast shield retracts.')
elif not live and not has_tag(shield, 'closed'):
    add_tag(shield, 'closed')
    remit(loc(me), 'Power gutters out. The blast shield drops.')
'''
```

The router validates both captures, writes the single relay that moved, tells
the room, and hands off to `sync`:

```text
@set power console/cmd_route = '''
$route * to *:
n = trim(arg0)
bus = trim(arg1).lower()
code = switch(bus, 'main', 'a', 'backup', 'b', '')  # trailing arg is the default: '' for any other word
if n not in ('1', '2', '3') or not code:
    pemit(enactor, 'Try ROUTE <1-3> TO <MAIN or BACKUP>.')
else:
    set_attr(me, 'j' + n, code)
    remit(loc(me), f'Relay {n} swings to the {bus} bus.')
    eval_attr(me, 'sync')
'''
```

Finally the readout, which walks the three junctions through the same `switch`
table in reverse, reports each line privately with
[`pemit`](../reference/softcode.md#fn-pemit), and closes with the verdict from
the one shared `check`:

```text
@set power console/cmd_grid = '''
$grid:
for n in ('1', '2', '3'):
    pemit(enactor, f'Junction {n}: ' + switch(V('j' + n), 'a', 'MAIN bus', 'b', 'BACKUP bus', 'UNROUTED'))
pemit(enactor, 'GRID STATUS: ' + ('ONLINE' if eval_attr(me, 'check') else 'FAULT'))
'''
```

## Try it

Read the schematic, then check the board and confirm the shield really is shut
against both approaches:

```text
> grid
Junction 1: MAIN bus
Junction 2: MAIN bus
Junction 3: MAIN bus
GRID STATUS: FAULT

> blast shield
The blast shield is closed.

> open blast shield
The blast shield is sealed. Route the grid to full power first.
```

Bad input is refused by the same line, whichever half is wrong:

```text
> route 9 to backup
Try ROUTE <1-3> TO <MAIN or BACKUP>.

> route 1 to plaid
Try ROUTE <1-3> TO <MAIN or BACKUP>.
```

Now route as the schematic instructs. Junction 2 already sits on MAIN, so two
reroutes finish the path, and the second one trips `sync`:

```text
> route 1 to backup
Relay 1 swings to the backup bus.

> route 3 to backup
Relay 3 swings to the backup bus.
The grid hums up to full power. The blast shield retracts.

> blast shield
The Core Bay
The reactor core throbs behind shielded glass. The prize: an intact power cell.
```

The result worth confirming deliberately is the reverse. Walk back and break the
routing, and the shield answers on the same recompute:

```text
> route 2 to backup
Relay 2 swings to the backup bus.
Power gutters out. The blast shield drops.

> grid
Junction 1: BACKUP bus
Junction 2: BACKUP bus
Junction 3: BACKUP bus
GRID STATUS: FAULT
```

Nothing here depends on a die roll, so every line above is reproducible exactly.

## Going further

- **A real path search.** Grow the board into a directed graph and rewrite
  `check` to walk it breadth-first from `reactor` to `shield` over the enabled
  edges, turning a graph traversal into a win condition. The sandbox supports
  `while`, `list.append`, and `list.pop`, so the walk fits in one attribute. Two
  storage details matter: `@set` parses a value as JSON first, so write the map
  with double quotes (`@set power console/edges = {"reactor": ["j1"], "j1": []}`)
  to get a real dict back, since single quotes fail the JSON parse and leave you
  a plain string; and keep the map on one `@set` line, because a `'''` block
  stores its body as a raw string and `.get()` on that would fail.
- **Overload penalties.** If two relays feed the same bus, have `sync`
  [`damage`](../reference/softcode.md#fn-damage) a random occupant and trip a
  breaker that flips a junction back. `damage` reaches only things in the
  executor's room that carry an `hp` attribute, and the delayed breaker wants an
  `on_tick` script driven by the `script_ticker` behavior, which the
  [jukebox](003_jukebox.md) sets up.
- **Locked relays.** Locks apply to an object rather than to one verb, so give
  the restricted relay its own switch object with its own `$route` and gate it
  with `@lock/use <switch> = caller.has_tag('keycard')`, which is the lock type
  the engine consults before firing an object's `$`-commands. (The `command`
  lock type gates `@tr` and the `trigger` command, not typed verbs.) The puzzle
  then needs a teammate.
- **Reset.** See [item 218](218_puzzle_reset.md) for restoring the all-main
  starting grid and re-sealing the bay between attempts.
