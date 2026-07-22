# 213. Power routing puzzle

> Checklist item 213 — now — *graph state in attributes, $route toggles, eval_attr() win-check*

**What you'll build:** A reactor console whose three relays each feed
either the **main** or the **backup** power bus. A blown conduit means the
obvious straight-through routing is dead; reroute around it — as the wall
schematic tells you — and the grid comes online, retracting a blast
shield. Reroute wrongly and it drops again.

**Concepts:** puzzle state held as a little **graph in attributes**, a
`$route` verb that toggles one edge at a time, and the win condition
written **once** as an `eval_attr()` function that both the router and a
`$grid` status readout call.

## How it works

A routing puzzle is a combination lock whose digits are *connections*:

1. **The graph is three attributes.** `j1`, `j2`, `j3` each hold `a`
   (main bus) or `b` (backup bus). That's the entire mutable state — the
   console is the controller, so it survives reboots and any player can
   walk up and change one relay.

2. **`route <n> to <bus>` flips one edge.** `$route * to *` validates the
   junction number and bus letter, sets that one attribute, narrates it,
   and calls `sync`. Toggling is deliberately atomic — you reason about
   one relay at a time, which is what makes it a *puzzle* and not a
   guessing game.

3. **The win-check lives in one function.** `check` compares the three
   junctions against the stored `solution` and hands back a bool through
   `result` — the variable `eval_attr()` returns (an `eval_attr`'d
   function reports its answer by assigning `result`, like Penn's `u()`).
   Writing it once as an attribute means the router (`sync`) and the
   player-facing readout (`$grid`) evaluate the *same* rule with
   `eval_attr(me, 'check')` — no chance of the status line and the door
   disagreeing. (For a larger board this same function would walk the
   graph looking for a source-to-sink path; here the solution is a fixed
   target, so it's a direct compare.)

4. **`sync` drives the door both ways.** Like the [weight
   plates](212_weight_plate.md), it recomputes from scratch and sets the
   `closed`+`locked` blast-shield exit to match — online retracts it,
   fault drops it — so the puzzle is fully reversible.

The answer isn't hidden: it's *deducible* from the schematic on the wall.
A good routing puzzle rewards reading, not brute force.

## Build it

The reactor room and the sealed bay behind the shield:

```text
@dig Reactor Control = reactor, out
reactor
@dig The Core Bay = blast shield, reactor
@desc The Core Bay = The reactor core throbs behind shielded glass. The prize: an intact power cell.
@tag blast shield = closed
@tag blast shield = locked
@set blast shield/locked_msg = The blast shield is sealed. Route the grid to full power first.
```

The wall schematic — this is the clue that makes the puzzle solvable:

```text
@create wall schematic
drop wall schematic
@desc wall schematic = A grease-penciled diagram. Junction 2's main line is slashed out and marked FAULT. Scrawled beside it: "Send 1 and 3 to BACKUP, keep 2 on MAIN, and she'll light."
```

The console. It starts all-main (the dead straight-through routing);
`solution` encodes "backup, main, backup":

```text
@create power console
drop power console
@desc power console = A panel of three relay switches feeding the main and backup buses. ROUTE <1-3> TO <MAIN|BACKUP>, or GRID for status.
@set power console/j1 = a
@set power console/j2 = a
@set power console/j3 = a
@set power console/solution = b a b
```

The win-check, written once:

```text
@set power console/check = result = (V('j1') + ' ' + V('j2') + ' ' + V('j3') == str(V('solution')))
```

`sync` — retract or drop the shield to match the grid:

```text
@set power console/sync = live = eval_attr(me, 'check'); g = get('blast shield'); (remove_tag(g, 'closed'), remit(loc(me), 'The grid hums up to full power -- the blast shield retracts.')) if live and has_tag(g, 'closed') else ((add_tag(g, 'closed'), remit(loc(me), 'Power gutters out. The blast shield drops.')) if not live and not has_tag(g, 'closed') else None)
```

The router and the status readout — both letters map through one
`switch`, both call the one `check`:

```text
@set power console/cmd_route = $route * to *: n = trim(arg0); v = switch(trim(arg1).lower(), 'main', 'a', 'backup', 'b', ''); (pemit(enactor, 'Try ROUTE <1-3> TO <MAIN or BACKUP>.') if n not in ('1', '2', '3') or not v else (set_attr(me, 'j' + n, v), remit(loc(me), 'Relay ' + n + ' swings to the ' + trim(arg1).lower() + ' bus.'), eval_attr(me, 'sync')))
@set power console/cmd_grid = $grid: [pemit(enactor, f'Junction {n}: ' + switch(V('j' + str(n)), 'a', 'MAIN bus', 'b', 'BACKUP bus')) for n in (1, 2, 3)]; pemit(enactor, 'GRID STATUS: ' + ('ONLINE' if eval_attr(me, 'check') else 'FAULT'))
```

## Try it

Read the schematic, check the board, then route as instructed:

```text
grid                 -> Junction 1: MAIN bus / 2: MAIN / 3: MAIN / GRID STATUS: FAULT
route 1 to backup    -> Relay 1 swings to the backup bus.
route 3 to backup    -> Relay 3 swings to the backup bus.
                        The grid hums up to full power -- the blast shield retracts.
blast shield         -> the Core Bay
```

Junction 2 was already on MAIN, so two reroutes finished the path. Break
it again and the shield answers:

```text
route 2 to backup    -> Power gutters out. The blast shield drops.
grid                 -> ... GRID STATUS: FAULT
```

## Going further

- **A real path search** — grow the board to a proper directed graph
  (edges in a dict attribute) and rewrite `check` to breadth-first search
  from `reactor` to `shield` over the enabled edges — a graph walk
  repurposed as a win condition.
- **Overload penalties** — if two relays feed the same bus, `damage` a
  random occupant and trip a breaker (an `on_tick` that flips a junction
  back), so sloppy routing bites.
- **Locked relays** — pre-set one junction and `@lock` its `$route` so
  only a keycard-holder can move it — the puzzle now needs a teammate.
- **Reset** — see [item 218](218_puzzle_reset.md) to restore the
  all-main starting grid and re-seal the bay between attempts.
