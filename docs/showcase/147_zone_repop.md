# 147. Zone repop

> Checklist item 147 ([now]): *zone_reset behavior, reset_spec, ON_RESET, presence-gated repop*

**What you'll build:** A derelict bridge that repopulates itself. Its
maintenance drones respawn and its systems relight on a timer, but only
while no player is aboard. You will drive REALM's shipped `zone_reset`
behavior and add an owner's `$repop` override on top.

**Concepts:** the native `zone_reset` behavior (SMAUG/tbaMUD area reset,
[shipped](../guides/world-management.md#area-reset-repop)), the presence
gate as the player-aware core, the declarative `reset_spec`, and
`ON_RESET` for everything the spec leaves out.

## How it works

The finished area is a zone with one master object carrying three things:
a timer, a list of what should be present, and a hook for the rest. On a
cycle the master checks the clock, confirms nobody is watching, wipes its
old spawns, and reloads the list. This section answers where that timer
lives, how the master avoids repopping under a player's feet, what the
spec can declare, and what the hook adds.

**Why repop is a behavior, not a kernel sweep.** You attach it to the
zone master, so it composes onto the area's brain the way weather
([036](036_weather_system.md)) and schedules
([145](145_scheduled_events.md)) do. Attach it, configure two attributes,
and you are done. The master is the area's owner object, which is why
every other REALM behavior (a spawner, a decay sweeper) rides on it the
same way.

**How the area avoids repopping while you watch.** Each tick the behavior
checks whether the reset is due (`reset_interval` seconds since the last
one) and whether any room of the zone holds a `player`. If a player is
present it defers: it leaves `last_reset` untouched so the timer keeps
counting, and it repops as soon as the zone is clear on a later tick. The
area never snaps back to canonical while someone is watching, by design.
You do not author this logic; it is the behavior's contract. Contrast a
per-room [spawner](../guides/world-management.md), which tops up *while*
you stand there. Repop is the whole-area, nobody-looking reset.

**What `reset_spec` declares.** It is a list of `{"prototype": {...},
"room": <id-or-tag>, "count": N}` rows. On each reset the master clears
its own prior spawns and reloads the spec fresh, so a killed drone is
back, mobs from a since-deleted row vanish, and nothing accumulates. The
`room` value is an object id or a plain room tag (we tag the bridge
`dronebay` and target that).

**What `ON_RESET` adds.** The spec repops mobs; everything else, such as
re-locking doors, clearing litter, or reseeding randomness, goes in the
master's [`ON_RESET`](../reference/softcode.md#lifecycle-hooks), which
fires on the master before the mob wipe and reload. The reset names the
master as its target, but propagation still visits every object in the
master's room, so the hook opens with the
[`target` guard](../reference/softcode.md#guard-on-target) that keeps a
second master's reset from running this one's cleanup. Ours
[`incr`](../reference/softcode.md#fn-incr)s a `cycles` counter (so you can
see it ran) and [`remit`](../reference/softcode.md#fn-remit)s a relight
line to the room.

## Build it

A derelict zone of one room, tagged both into the zone and with a plain
`dronebay` locator the spec can aim at:

```text
@dig Derelict Bridge = bridge, out
bridge
@zone here = derelict
@tag here = dronebay
```

The master, its repop config, and the behavior attach. `reset_interval`
is seconds, and `reset_spec` uses the spawner's prototype vocabulary:

```text
@create Bridge Systems
drop Bridge Systems
@zone/master Bridge Systems = derelict
@set Bridge Systems/reset_interval = 300
@set Bridge Systems/reset_spec = [{"prototype": {"name": "a maintenance drone", "tags": ["npc"]}, "room": "dronebay", "count": 2}]
@behavior Bridge Systems = zone_reset
```

The `ON_RESET` hook runs on the master before the canonical mobs reload.
Write it as a `'''` block, opening with `if target is me:` so that a
second zone master resetting in this room runs its own cleanup and not
this one's:

```text
@set Bridge Systems/on_reset = '''
if target is me:
    # every object in the room hears the reset, so claim only our own
    incr('cycles')
    remit('Derelict Bridge', 'Dormant systems cycle: consoles relight, the drone bay reseeds.')
'''
```

Now the owner-only `$repop` override, which queues a reset now. It does
not force a pop on top of anyone. It compares the enactor against
[`owner(me)`](../reference/softcode.md#fn-owner), and for the owner it
[`set_attr`](../reference/softcode.md#fn-set_attr)s the timer to zero so
the behavior fires the moment the zone is clear (the presence gate still
holds), while a non-owner just gets a
[`pemit`](../reference/softcode.md#fn-pemit) refusal. A `$`-command like
this needs no `target` guard. Written as a `'''` block so the authority
check reads as a plain `if`/`else`:

```text
@set Bridge Systems/cmd_repop = '''
$repop:
if enactor != owner(me):
    pemit(enactor, 'Command authority required.')
else:
    # zero the timer; the gate still holds, so it fires once the bridge clears
    set_attr(me, 'last_reset', 0)
    pemit(enactor, 'Reset queued -- it fires the instant the bridge is clear.')
'''
```

## Try it

With the bridge empty, force the timer due and let one reset tick run. On
a live server the behavior does this on the world tick every
`reset_interval`; here we zero the timer and pump one tick so it is
instant:

```text
> repop
Reset queued -- it fires the instant the bridge is clear.

(next reset tick, zone empty)
Dormant systems cycle: consoles relight, the drone bay reseeds.
```

Two maintenance drones now stand on the bridge, and `@examine Bridge
Systems` shows `cycles` at 1. Kill a drone, type `repop`, and the pair is
whole again. But step into the bridge first and queue it: nothing pops.
The reset waits until you leave, then catches up on the next tick. An
occupied area never repops under your feet.

## Going further

- **Re-lock on reset:** point `ON_RESET` at a `trigger me/reseal`
  attribute that [`add_tag`](../reference/softcode.md#fn-add_tag)s the
  vault door `closed` and re-locks it, so the derelict seals itself back
  up between visitors.
- **Multi-room zones:** add rooms with `@zone here = derelict` and more
  `reset_spec` rows (each with its own `room`); the whole area resets as
  a unit.
- **Instances instead:** for a dungeon that should be *fresh per group*
  rather than reset-when-empty, use
  [`enter_instance()`](../reference/softcode.md#fn-enter_instance), a
  private copy per party torn down on exit (tutorial
  [216](216_escape_room.md)).
- **Reset as a puzzle button:** puzzle rooms restore their state the same
  way; tutorial [218](218_puzzle_reset.md) uses `ON_RESET`-driven
  re-arming to reset a mechanism between attempts.
