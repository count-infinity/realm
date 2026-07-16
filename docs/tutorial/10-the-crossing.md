# Part 10 — The Crossing

Act III. The ferryman has his chart, which makes him the only man on
the coast with a reason to like you. Time to collect: passage to
**Saltmarsh**, the town across the water — and a lesson in making an
NPC *do* something long: a timed, stateful, cancellable **action
sequence**, built from three attributes.

## The far shore

```text
@dig Saltmarsh Quay
@teleport me = Saltmarsh Quay
@tag here = zone:saltmarsh
@desc here = Tarred pilings, herring barrels, and a customs bell green with weather. The Gullwing light is a spark on the horizon.
@eval result = here.id
```

Note that id — it's `HARBOR` below (the `zone:saltmarsh` tag pays off
in part 12). Give the quay its keeper while you're here:

```text
@create the harbormaster
@tag the harbormaster = npc
@set the harbormaster/description = He logs every keel that kisses this quay, and forgets none of them.
drop the harbormaster
```

Then open the sea to the town — the provider line from part 9, plus a
`harbor` exit at the far corner (one line; paste your ids over `JETTY`
and `HARBOR`):

```text
@set gullwater/cell_exits = result = ['north', 'south', 'east', 'west'] + ([{'name': 'jetty', 'destination': 'JETTY', 'aliases': ['out']}] if x == 0 and y == 0 else []) + ([{'name': 'wreck', 'attrs': {'dest_resolver': 'instance', 'instance_template': 'wreck', 'instance_mode': 'shared', 'instance_return': 'JETTY'}}] if x == 3 and y == 3 else []) + ([{'name': 'harbor', 'destination': 'HARBOR'}] if x == 0 and y == 6 else [])
```

## A hand on the tiller

You rowed yourself in part 7. Passengers pay someone else to. Back at
the Jetty (`@teleport me = The Jetty`), give the ferryman a route —
three attributes: a trigger to start, a stroke that repeats, a
landfall that ends:

```text
@set the ferryman/cmd_passage = $passage:(say('All aboard, then. Keep your hands inboard.'), force(me, 'board'), set_attr(me, 'legs', 0), set_attr(me, 'oar', wait(4, 'trigger stroke'))) if credits(me) >= 10 else say('Ten for the crossing. Pay first, ride after.')
@set the ferryman/stroke = n = get_attr(me, 'legs', 0); crew = [p for p in contents(loc(me)) if has_tag(p, 'player')]; (force(me, 'row sea' if n == 0 else 'row north'), set_attr(me, 'legs', n + 1), set_attr(me, 'oar', wait(4, 'trigger stroke' if n < 6 else 'trigger landfall'))) if crew or n > 0 else (say('When you are settled aboard, we go.'), set_attr(me, 'oar', wait(4, 'trigger stroke')))
@set the ferryman/landfall = force(me, 'row harbor'); say('Saltmarsh Quay. Mind the step.'); force(me, 'ashore'); set_attr(me, 'legs', 0)
```

Read `stroke` inside-out — it's the whole pattern:

- **`force(me, ...)`** runs a command *as the ferryman*, through the
  real dispatcher — so `row` is the ferry's own `$row` from part 7,
  found because he's aboard her. NPCs work the world with the same
  verbs players do.
- **`wait(4, 'trigger stroke')`** is the metronome: each step
  schedules the next by name. A sequence is just attributes wired
  with `wait` + `trigger` — no new machinery.
- **`legs`** is the sequence's memory: stroke 0 rows out the gate,
  1–6 row north, then landfall. State lives in ordinary attributes,
  where you can `@examine` it mid-voyage.
- The **crew check** makes step one patient: no passenger aboard yet,
  it reschedules itself and waits. Sequences can poll.

And because `wait()` returns a handle (he keeps it in `oar`), the
voyage is interruptible:

```text
@set the ferryman/cmd_belay = $belay:cancel_wait(get_attr(me, 'oar')); say('Belay that. We hold water.')
```

## Take passage

```text
pay 10 to the ferryman
passage
board
```

Then sit still. He boards, waits for you, pushes off, and rows the
Gullwater one cell at a time — the sea materializing under her bow,
the undertow never touching you — until the quay. `ashore` when he
calls it, and you're standing in Saltmarsh.

## Checkpoint

`passage` before paying gets you priced. `passage` then dawdling
ashore gets you waited on. `belay` mid-cross leaves you bobbing —
type `row north` yourself; the oars don't care whose hands they're in.

!!! info "Learn more"
    This shape — start trigger, self-scheduling step, terminator — is
    the general sequence pattern: patrol routes, ritual chants, alarm
    escalations, a fuse burning down. The ferryman checks his purse
    (`credits(me) >= 10`), not your receipt — one paid fare opens the
    boat to the village; per-passenger fares are part 4's caching
    trick (`'fare_' + enactor.id`) if you want them.
