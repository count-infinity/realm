# 147. Zone repop

> Checklist item 147 — [now] — *native zone_reset behavior, presence-gated repop, ON_RESET, reset_spec*

**What you'll build:** A derelict bridge that repopulates itself — its
maintenance drones respawn and its systems relight on a timer, but
**only while no player is aboard**. You'll drive REALM's shipped
`zone_reset` behavior and add an owner's `$repop` override on top.

**Concepts:** the native `zone_reset` behavior (SMAUG/tbaMUD area reset,
[shipped](../guides/world-management.md#area-reset-repop)), the
**presence gate** as the player-aware core, the declarative `reset_spec`,
and `ON_RESET` for everything the spec can't express.

## How it works

Repop is **not a kernel sweep** — it's a behavior you attach to the zone
master, so it composes onto the area's brain the way weather
([036](036_weather_system.md)) and schedules
([145](145_scheduled_events.md)) do. Attach it, configure two
attributes, done.

**The presence gate is the player-aware layer, built in.** Each tick the
behavior checks whether the reset is due (`reset_interval` seconds since
the last one) *and* whether any room of the zone holds a `player`. If a
player is present it **defers** — leaves `last_reset` untouched so the
timer keeps counting — and repops the instant the zone empties. The area
never snaps back to canonical while someone is watching, by design. You
don't write this; it's the behavior's contract. (Contrast a per-room
[spawner](../guides/world-management.md), which tops up *while* you stand
there — repop is the whole-area, nobody-looking reset.)

**`reset_spec` is declarative.** A list of `{"prototype": {...}, "room":
<id-or-tag>, "count": N}` rows. On each reset the master **clears its own
prior spawns and reloads the spec fresh** — so a killed drone is back,
mobs from a since-deleted row vanish, and nothing accumulates. `room` is
an object id or a plain room tag (we tag the bridge `dronebay` and target
that).

**`ON_RESET` covers the rest.** The spec repops mobs; everything else —
re-locking doors, clearing litter, reseeding randomness — goes in the
master's `ON_RESET`, which fires first on every reset. Ours bumps a
`cycles` counter (so you can see it ran) and relights the consoles.

## Build it

A derelict zone of one room, tagged both into the zone and with a plain
`dronebay` locator the spec can aim at:

```text
@dig Derelict Bridge = bridge, out
bridge
@zone here = derelict
@tag here = dronebay
```

The master, its repop config, and the behavior. `reset_interval` is
seconds; `reset_spec` uses the spawner's prototype vocabulary:

```text
@create Bridge Systems
drop Bridge Systems
@zone/master Bridge Systems = derelict
@set Bridge Systems/reset_interval = 300
@set Bridge Systems/reset_spec = [{"prototype": {"name": "a maintenance drone", "tags": ["npc"]}, "room": "dronebay", "count": 2}]
@set Bridge Systems/on_reset = set_attr(me, 'cycles', get_attr(me, 'cycles', 0) + 1); remit('Derelict Bridge', 'Dormant systems cycle: consoles relight, the drone bay reseeds.')
@behavior Bridge Systems = zone_reset
```

Now the player-aware override — an owner-only `$repop` that queues a
reset *now*. It doesn't force a pop on top of anyone; it just zeroes the
timer, so the behavior fires it the moment the zone is clear — the gate
still holds:

```text
@set Bridge Systems/cmd_repop = $repop: pemit(enactor, 'Command authority required.') if enactor != owner(me) else (set_attr(me, 'last_reset', 0), pemit(enactor, 'Reset queued -- it fires the instant the bridge is clear.'))
```

## Try it

With the bridge empty, force the timer due and let one reset tick run
(on a live server the behavior does this on the world tick every
`reset_interval`; here `@tr`-style forcing keeps it instant):

```text
repop                 -> Reset queued -- it fires the instant the bridge is clear.
(next reset tick, zone empty)
   -> Dormant systems cycle: consoles relight, the drone bay reseeds.
```

Two maintenance drones now stand on the bridge, and `@examine Bridge
Systems` shows `cycles` at 1. Kill a drone, `repop`, and the pair is
whole again. But step *into* the bridge first and queue it: nothing
happens — the reset waits, patient, until you leave, then catches up. An
occupied area never repops under your feet.

## Going further

- **Re-lock on reset:** point `ON_RESET` at a `trigger me/reseal`
  attribute that `add_tag`s the vault door `closed` and re-locks it —
  the derelict seals itself back up between visitors.
- **Multi-room zones:** add rooms with `@zone here = derelict` and more
  `reset_spec` rows (each with its own `room`); the whole area resets as
  a unit.
- **Instances instead:** for a dungeon that should be *fresh per group*
  rather than reset-when-empty, use `enter_instance()` — a private copy
  per party, torn down on exit (tutorial 216's escape room).
- **Reset as a puzzle button:** puzzle rooms restore their state the same
  way — tutorial 218 uses `ON_RESET`-driven re-arming to reset a
  mechanism between attempts.
