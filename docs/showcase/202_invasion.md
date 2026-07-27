# 202. World event: invasion

> Checklist item 202 ([now]): *zone-master phases, spawner waves, ON_RESET cleanup*

**What you'll build:** a raider invasion that sweeps a whole zone in staged
phases, from a warhorn warning through a first wave that spawns a raider in
every room, then reinforcements, then a repel that clears the field, all
orchestrated by one ticking zone master with an `ON_RESET` scrub for a run
that gets interrupted.

**Concepts:** the zone master as an event orchestrator; a phase counter
advanced by `script_ticker`/`on_tick`; spawner waves with
[`create_obj`](../reference/softcode.md#fn-create_obj) into
[`zone_rooms()`](../reference/softcode.md#fn-zone_rooms); zone-wide narration
with [`remit`](../reference/softcode.md#fn-remit); cleanup with
[`destroy_obj`](../reference/softcode.md#fn-destroy_obj) plus
[`search_world`](../reference/softcode.md#fn-search_world); an
[`ON_RESET`](../reference/softcode.md#lifecycle-hooks) safety net.

## How it works

The finished invasion is one object with one heartbeat. A drum sits in the
citadel, wearing the zone-master tag, and every time its ticker fires it bumps
a number stored on itself and does whatever that number's phase calls for:
warn, breach, reinforce, repel. Four questions follow, namely where that state
belongs, how one attribute keeps four phases straight, how a wave reaches rooms
the drum is not standing in, and what tidies up a run that never finishes.

### Where does zone-wide state live?

A world event is zone state that changes on a clock, so it lives on the
**zone master**: one object tagged into the zone with `@zone/master`, which is
the same brain that drives the [weather](036_weather_system.md) and the
[station self-destruct](056_self_destruct.md). `@zone/master` puts two tags on
the object at once, `zone_master` plus `zone:<name>`, which is what makes the
engine treat it as the area's brain. The master is a plain thing rather than a
room, so it never turns up in `zone_rooms()` and never receives one of its own
raiders.

### How one attribute keeps four phases straight

The master carries a `phase` integer and the whole schedule is one `on_tick`
script. [`incr('phase')`](../reference/softcode.md#fn-incr) bumps the counter
on `me` and hands back the **new** value, so the first tick after a reset sees
`p == 1`. The body is then an ordinary `if`/`elif` chain over `p`: phase 1
sounds the warhorn with no spawns, phase 2 breaches the gate, phase 3 sends
reinforcements, and phase 4 clears the field and puts `phase` back to 0 so the
whole event may run again. Because one branch runs per tick, the pacing is
simply the ticker's interval, and there is no second timer to keep in sync.

### How a wave reaches rooms the drum is not standing in

`zone_rooms('citadel')` returns every room tagged `zone:citadel`, and both
`create_obj` and `remit` accept that room as their target, so a single `for`
loop covers the whole area from one script.

Spawning across rooms is authority-gated:
[`create_obj`](../reference/softcode.md#fn-create_obj) with a `location=`
other than the executor's own room succeeds only when the executor's owner
controls that room, and returns `None` otherwise. Here the builder owns the
drum and both rooms, so every seat is legal. This is the same rule the
[self-destruct](056_self_destruct.md) relies on when it seeds a sheet of flame
into each station room. Name the spawn `raider` rather than `a raider`, because
a lowercase name is treated as a bare noun and the renderer supplies the
article itself, so `look` reads "a raider" either way and a leading article in
the stored name would be doubled.

For narration, `remit` simply delivers text to everyone in a room, which is all
a warhorn needs. When you want the announcement itself to be an event that
other objects may react to or veto, reach for
[`act(..., targeting='zone')`](../reference/softcode.md#fn-act) instead, since
that runs the two-pass propagation engine across the zone rather than printing
a line.

### What cleans up a run that never finishes

Cleanup is one idempotent script in exactly one place, the master's
`on_reset`: destroy every object tagged `raider`, then zero the phase. Two
things reach it. A builder types `@tr War Drum/on_reset` to scrub on demand,
and the `zone_reset` behavior fires
[`ON_RESET`](../reference/softcode.md#lifecycle-hooks) on the master when the
zone's `reset_interval` comes due **and no player is standing in the zone**.
An occupied zone defers and resets the moment it empties, which is deliberate:
an area never snaps back to its authored state while somebody watches. Attach
that behavior and give it an interval, otherwise `ON_RESET` has nothing to
fire it.

Note that `search_world(tag='raider')` is world-wide and returns at most 100
matches unless you pass a larger `limit=`, so a very large invasion, or a
second event elsewhere using the same tag, wants an event-specific tag such as
`citadel_raider`.

Because `on_reset` targets the master itself, it takes **no**
[`target` guard](../reference/softcode.md#guard-on-target): it is the subject
of its own event, and `@tr` leaves `target` bound to `None`, so a
`if target is me:` wrapper would skip the body exactly when a builder ran it by
hand. Reactive hooks that answer something done *to* one object among many, such
as the per-raider `ON_DEATH` in "Going further", do need that guard.

## Build it

Name your starting room the gate and tag it into the zone, then add a second
room so the waves have somewhere to land:

```text
@name here = The Citadel Gate
@zone here = citadel
@dig The Keep = keep, gate
keep
@zone here = citadel
gate
```

Raise the War Drum and crown it the zone's master:

```text
@create War Drum
drop War Drum
@zone/master War Drum = citadel
```

The phase counter is plain data, so it stays a one-line `@set`:

```text
@set War Drum/phase = 0
```

Now the orchestrator. One `on_tick` reads the new phase number and runs that
phase's branch, warning first, then the breach, then reinforcements, then the
repel that clears the field and rolls the counter back to zero:

```text
@set War Drum/on_tick = '''
# incr returns the NEW value, so the first tick after a reset is phase 1.
p = incr('phase')
rooms = zone_rooms('citadel')
if p == 1:
    for r in rooms:
        remit(r, 'Warhorns! Raiders mass beyond the walls.')
elif p == 2:
    for r in rooms:
        create_obj('raider', ['npc', 'raider'], location=r)
        remit(r, 'Raiders pour through the gate!')
elif p == 3:
    for r in rooms:
        create_obj('raider', ['npc', 'raider'], location=r)
        remit(r, 'More raiders scale the walls!')
else:
    for o in search_world(tag='raider'):
        destroy_obj(o)
    for r in rooms:
        remit(r, 'The last raider falls. The citadel holds.')
    set_attr(me, 'phase', 0)
'''
```

The cleanup script scrubs the field and zeroes the counter. It carries no
`target` guard on purpose, because the master is the subject of its own reset
and `@tr` leaves `target` unset:

```text
@set War Drum/on_reset = '''
# No target guard: this master is the subject of its own reset, and @tr
# leaves target unset, so a guard would skip a hand-run scrub.
for o in search_world(tag='raider'):
    destroy_obj(o)
set_attr(me, 'phase', 0)
'''
```

Finally the two behaviors: `script_ticker` is the heartbeat that advances the
phases, and `zone_reset` is what actually fires `ON_RESET` once the interval is
due and the zone has emptied. At the default four-second world beat,
`interval:20` fires `on_tick` roughly every eighty seconds:

```text
@behavior War Drum = script_ticker, interval:20
@behavior War Drum = zone_reset
@set War Drum/reset_interval = 600
```

## Try it

Stand in the gate (or the keep) and drive the phases by hand with `@tr` rather
than waiting on the clock:

```text
> @tr War Drum/on_tick
Warhorns! Raiders mass beyond the walls.
Triggered War Drum/on_tick.

> @tr War Drum/on_tick
Raiders pour through the gate!
Triggered War Drum/on_tick.

> look
The Citadel Gate
----------------

You see:
  War Drum
  a raider

Exits: keep

> @tr War Drum/on_tick
More raiders scale the walls!
Triggered War Drum/on_tick.

> @tr War Drum/on_tick
The last raider falls. The citadel holds.
Triggered War Drum/on_tick.
```

The two lines worth confirming deliberately are the counts and the rollover.
After the second tick the zone holds two raiders (one per room) and after the
third it holds four, so a walk through `keep` finds the second room garrisoned
as well. After the fourth, `@examine War Drum` reports `phase` back at 0, so the
very next tick sounds the warhorn again.

Interrupting mid-event works the same way from either end:

```text
> @tr War Drum/on_reset
Triggered War Drum/on_reset.
```

Every raider is gone and `phase` is 0. A live zone reset runs that identical
script once `reset_interval` elapses with nobody inside the citadel.

Every raider is a real NPC, so giving them combat behaviors turns the waves
into a fight, while leaving them inert makes the invasion stage dressing.

## Going further

- **Real defenders and combat.** Spawn the raiders with
  `['npc', 'raider', 'hostile']` and attach the `aggressive` behavior to each
  fresh one with
  [`attach_behavior(o, 'aggressive')`](../reference/softcode.md#fn-attach_behavior),
  so they engage whoever is in the room and the invasion becomes a defense
  event. The [guard response](071_guard_response.md) master can dispatch the
  watch to meet them.
- **Escalating messaging.** Switch the `remit` text on `p` to add
  [`ansi('rh', ...)`](../reference/softcode.md#fn-ansi) red alerts as the waves
  grow, or count survivors and announce that the walls are breached when
  raiders outnumber defenders.
- **Loot the fallen.** Give raiders an
  [`ON_DEATH`](../reference/softcode.md#lifecycle-hooks) that drops salvage,
  and pair it with [collection counters](200_collection_counters.md) so
  repelling the invasion *is* a collection quest. Guard it, because `ON_DEATH`
  reaches every witness in the room, which means an unguarded hook makes the
  raider standing next to the corpse drop loot too:

  ```text
  @set raider/on_death = '''
  if target is me:
      create_obj('notched warpick', ['loot'])
  '''
  ```

  The hook fires however the raider died, whether by a blade, a trap, or a
  scripted [`damage()`](../reference/softcode.md#fn-damage), and `actor` is
  whoever landed the blow (`adata('killer')` carries the same thing as a plain
  name), so you can credit the kill as well as drop the loot.
- **Count the fallen on the master.** Zone masters witness events in every
  member room, so a `War Drum/on_death` that filters with
  `if has_tag(target, 'raider'):` and calls `incr('slain')` tallies the whole
  invasion from one attribute. A global witness like that takes a tag filter
  rather than a `target is me` guard, since it is deliberately watching
  everyone. See [Guard on `target`](../reference/softcode.md#guard-on-target)
  and the [event bus tour](245_event_bus_tour.md).
- **Boss finale.** Make phase 3 spawn a single raider warlord with
  [`ON_HITPRCNT`](../reference/softcode.md#lifecycle-hooks) reinforcement calls
  instead of a second rank, so the event peaks on a named fight.
- **Trigger rather than schedule.** Detach the ticker and fire `on_tick` from a
  war-drum lever or a story moment, so staff (or a quest) start the invasion on
  cue.
