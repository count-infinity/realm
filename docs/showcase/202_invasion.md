# 202. World event: invasion

> Checklist item 202 — [now] — *zone-master phases, spawner waves, ON_RESET cleanup*

**What you'll build:** a raider invasion that sweeps a whole zone in
staged phases — a warhorn warning, a first wave that spawns a raider in
every room, reinforcements, then a repel that cleans up after itself — all
orchestrated by one ticking zone master, with an `ON_RESET` scrub for when
things get stuck.

**Concepts:** the **zone master as an event orchestrator**; a **phase
counter** advanced by `script_ticker`/`on_tick`; **spawner waves** with
`create_obj` into `zone_rooms()`; zone-wide narration with `remit`;
**cleanup** with `destroy_obj` + `search_world`; an `ON_RESET` safety net.

## How it works

A world event is *zone state that changes on a clock*, so it lives where
zone state belongs — on the zone master (the same brain that drives the
[weather](036_weather_system.md) and the [self-destruct](056_self_destruct.md)).
The master carries a `phase` integer; each `on_tick` advances it and does
that phase's job:

1. **Phase 1 — warning.** `remit` a warhorn line to every room in the zone
   (`zone_rooms('citadel')`). No spawns yet: tension first.
2. **Phase 2 — first wave.** `create_obj('a raider', ...)` into *each* zone
   room — one raider per room — and announce the breach. Spawning into
   rooms the master's owner controls is legal (the self-destruct seeds fire
   the same way).
3. **Phase 3 — reinforcements.** Another raider per room; the pressure
   escalates.
4. **Phase 4 — repel & cleanup.** `destroy_obj` every `raider` in the world
   (`search_world(tag='raider')`), announce the hold, and reset `phase` to
   0 so the event can run again.

The phases are a single `on_tick` that branches on the new phase number —
each branch a guarded comprehension (`[... for r in zone_rooms('citadel')
if p == N]`), the spam-discipline idiom where nothing happens on the wrong
phase. Because it's ticker-driven, the whole event is one object with one
heartbeat; there's no fragile web of timers to chase.

**`ON_RESET` is the janitor.** A zone reset (empty + due) fires the
master's `on_reset` — here, "scrub every raider and zero the phase" — so an
invasion interrupted by a reboot or a stuck phase never leaves orphaned
mobs wandering the citadel. Cleanup is idempotent and lives in exactly one
place.

## Build it

Name your starting room the gate and tag it into the zone, then add a
second room so waves have somewhere to land:

```text
@name here = The Citadel Gate
@zone here = citadel
@dig The Keep = keep, gate
keep
@zone here = citadel
gate
```

Raise the War Drum as the zone master and start it at phase 0:

```text
@create War Drum
drop War Drum
@zone/master War Drum = citadel
@set War Drum/phase = 0
```

The orchestrator — one `on_tick`, four phases, warning → wave →
reinforce → repel-and-reset:

```text
@set War Drum/on_tick = p = incr('phase'); [remit(r, 'Warhorns! Raiders mass beyond the walls.') for r in zone_rooms('citadel') if p == 1]; [(create_obj('a raider', ['npc', 'raider'], location=r), remit(r, 'Raiders pour through the gate!')) for r in zone_rooms('citadel') if p == 2]; [create_obj('a raider', ['npc', 'raider'], location=r) for r in zone_rooms('citadel') if p == 3]; [destroy_obj(o) for o in search_world(tag='raider') if p == 4]; [remit(r, 'The last raider falls. The citadel holds.') for r in zone_rooms('citadel') if p == 4]; set_attr(me, 'phase', 0) if p >= 4 else None
```

The reset janitor, and the heartbeat that drives the phases (~once a
minute at the default tick):

```text
@set War Drum/on_reset = [destroy_obj(o) for o in search_world(tag='raider')]; set_attr(me, 'phase', 0)
@behavior War Drum = script_ticker, interval:20
```

## Try it

Stand in the gate (or the keep) and watch it unfold — force the beats with
`@tr War Drum/on_tick` rather than waiting on the clock:

```text
@tr War Drum/on_tick     -> Warhorns! Raiders mass beyond the walls.        (0 raiders)
@tr War Drum/on_tick     -> Raiders pour through the gate!                  (2 raiders: one per room)
@tr War Drum/on_tick     -> (reinforcements)                               (4 raiders)
@tr War Drum/on_tick     -> The last raider falls. The citadel holds.       (0 raiders; phase resets)
```

At any point, `@tr War Drum/on_reset` wipes every raider and zeroes the
phase — the same scrub a live zone reset triggers. Every raider is a real
NPC: give them an `AggressiveBehavior` and the waves fight; leave them
inert and they're a stage-dressing siege.

## Going further

- **Real defenders and combat.** Spawn the raiders with
  `['npc', 'raider', 'hostile']` and an aggressive prototype so they engage
  whoever's in the room — the invasion becomes a defense event. The
  [guard response](071_guard_response.md) master can dispatch the watch to
  meet them.
- **Escalating messaging.** Switch the `remit` text on `p` to add
  `ansi('rh', ...)` red alerts as the waves grow, or count survivors and
  announce "the walls are breached" if raiders outnumber defenders.
- **Loot the fallen.** Give raiders an `ON_DEATH` that drops salvage —
  pair with [collection counters](200_collection_counters.md) so repelling
  the invasion *is* a collection quest. The hook fires however the raider
  died (a blade, a trap, a scripted `damage()`), and `actor` is whoever
  landed the blow, so you can credit the kill as well as drop the loot.
- **Boss finale.** Make phase 3 spawn a single `raider warlord` with
  `ON_HITPRCNT` reinforcement calls instead of a second wave — the event
  peaks on a named fight.
- **Trigger, don't schedule.** Detach the ticker and fire `on_tick` from a
  war-drum lever or a story beat, so staff (or a quest) start the invasion
  on cue.
