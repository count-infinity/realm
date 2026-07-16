# Time, Ticks & Beats

**Status:** SHIPPED (2026-07-16) — both work items (A real-time substrate, B
beat clock) are built; see [As built](#as-built) at the end for the code/test
map. Captures the target model for REALM's timing after three observations:
(1) the coarse 4s heartbeat quantizes everything to tick boundaries and makes
simultaneous effects fire in lockstep; (2) we want character effects to run on
**combat beats** so a slowed fight dilates uniformly ("bullet-time"); (3) an
open question — is a shared real-time heartbeat even the right substrate, or
should everything be individual async tasks?

## The problem

Today one ~4s heartbeat (`GameServer._tick_loop`) drives *everything*
periodic: behavior ticks (poison/decay/regen/wander/spawner/zone-reset),
one-shot `wait()`s, the reapers (idle instances / wilderness / expired), and
the session-output flush. Three consequences:

1. **Quantization.** `wait(1.5)` fires on the next 4s boundary, not at 1.5s.
   Everything scheduled inside a 4s window lands on the *same* pulse.
2. **Lockstep.** Effects count *pulses*, not seconds, and start with the same
   phase, so five poisons applied together tick together forever — robotic.
3. **No time-dilation.** Combat has an adjustable per-encounter beat for
   *actions*, but effects tick on the wall clock, so slowing a fight to 30s
   beats does **not** slow the poison. The two clocks are independent.

## What exists today

- **Heartbeat:** `_tick_loop`, `tick_interval` (config, default 4s). Iterates
  `behavior_owners()` (a `WeakSet` — only objects with behaviors), calling
  `tick(obj, delta)` when a behavior's `tick_interval` (seconds) has elapsed.
  `delta` is real seconds since that behavior last ticked.
- **Combat beat:** each encounter runs its **own** async loop
  (`encounter._run`) with `beat_seconds`, derived from the **slowest**
  participant's `db.combat_beat` (`max()`), clamped to `[beat_min, beat_max]`
  (4s–2min), recomputed on join/leave — adjustable mid-fight via `pace`.
- **DB flush:** its **own** separate async task (`_flush_loop`), NOT on the
  heartbeat — precedent that a subsystem can own its cadence.
- **Effect durations are in *pulses*** (`TimedEffectBehavior` decrements a
  counter each heartbeat), so they're coupled to the heartbeat rate.

## The core model: two clocks

REALM should have **two deliberate time units**, not one:

| Clock | Unit | Drives | Dilates with combat? |
|---|---|---|---|
| **Real-time** | seconds | `wait()` fuses, reapers/GC, output flush, idle timeouts, **the ambient beat generator**, ambient world behaviors (spawners, wander, decay, zone-reset) | **No** — a 30s bomb fuse is 30s in or out of a fight |
| **Beat** | beats (= rounds) | character effects (poison/bleed/buff/regen) **and** combat maneuvers | **Yes** — the bullet-time layer |

The crucial trick: **a beat's real-time length is contextual.**

- **In combat** → the encounter's adjustable `beat_seconds` (the existing knob).
- **Out of combat** → an **ambient world beat** (a config tempo, e.g. 4s),
  generated on the real-time heartbeat.

### The split rule (seconds vs beats)

> **Beats** = "the character advancing through the fight" (effects, maneuvers).
> **Seconds** = "wall-clock world events" (fuses, spawns, decay, GC, idle).

So poison is authored as **"N beats" = "N rounds"** — which is *also* the
natural GURPS/tabletop unit ("1 damage/round for 5 rounds"). A `wait(30)`
bomb stays 30 real seconds, because it's infrastructure, not a character
effect. That single boundary is the most important decision in this doc.

*(Correction to an earlier note that said "all durations in seconds": only
*infrastructure* durations are seconds; *character effects* are beats.)*

### Bullet-time falls out for free

Because everything beat-based shares the one contextual beat, slowing the
encounter dilates it all uniformly:

- 5-round poison, ambient beat 4s → ticks ~every 4s out of combat;
- in combat at 4s beats → same;
- slowed to 30s beats → ticks every 30s, lasts 5×30s — **the whole fight,
  poison included, stretches together.** Set `pace` low again and it snaps
  back. Adjustable any time (the next beat uses the new rate), like the
  existing action pacing.

## The open question: shared heartbeat vs. individual async tasks

*Raised directly: "is there even an advantage to the real-time heartbeat?
Surely it's easier to have individual asyncs and let reaping/GC occur on its
own? Practically nothing would subscribe only to the real-time clock."*

Worth taking seriously — and half-right. But let's test the premise.

**What actually still needs a real-time cadence, after effects move to beats?**
The ambient-beat generator (something must convert seconds→beats out of
combat), `wait()` firing, the output flush, **and the ambient world behaviors
that are genuinely real-time** — spawners (respawn every ~10min), wander/
patrol, corpse decay, zone reset. That's not "practically nothing"; a living
world is full of ambient real-time recurrence. So a periodic real-time pulse
does not disappear — at minimum the **ambient beat generator is one**.

**The genuine trade, weighed honestly:**

| Concern | Shared pulse (scan a registry each tick) | Individual async tasks (one `sleep` per timer) |
|---|---|---|
| **Durability across reboot** | State lives in `db`; the loop re-reads it each pulse — **nothing to re-arm**. | `db` holds `next_fire_at`, but the in-memory `sleep` is lost on reboot, so boot must **scan every pending timer and re-`create_task`** — i.e. a startup sweep anyway. |
| **Precision** | grid-quantized (fixed by a fast heartbeat). | **exact** (`sleep(1.5)` is 1.5s). |
| **Footprint at scale** | one loop, O(active behaviors), tiny per-item. | O(timers) Task objects + scheduler entries — fine at hundreds, heavy at 10k–100k. |
| **Testability / determinism** | **drive `tick()`/`tick_waits()` synchronously** — REALM's ~47 test call sites depend on exactly this. | needs wall-clock or heavy time-mocking; thousands of real-time tasks interleave nondeterministically. |
| **Batching** | one pulse → do work → flush output once. | each task emits at its own time → many small flushes. |
| **Lifecycle / leaks** | attach/remove a behavior; the loop handles the rest. | create/cancel/track a task per timer; destroyed objects must cancel theirs. |

**Verdict: hybrid — which REALM already is, and should lean into.**

- **Shared pulse is the substrate** for the *many, durable, low-precision,
  recurring* things (ambient beat, spawners, wander, decay, zone-reset), for
  three reasons that dominate at REALM's scale and values: reboot-safety with
  no re-arm logic, bounded footprint, and — decisively — **testability**
  (the whole suite drives ticks deterministically; thousands of real-time
  tasks would make the game nearly untestable).
- **Individual async tasks are the escape hatch** for the *few,
  precision-critical, short-lived* things — and REALM already uses exactly
  this for **combat encounters**. `wait()` is the natural next candidate:
  it's one-shot and already non-durable, so per-`wait` tasks would give exact
  timing with no reboot cost. A dramatic 1.5s fuse wants its own task.
- **You cannot eliminate the shared periodic pulse** (the ambient beat *is*
  one), but you *can* — and should — push precision/one-shot work off it.

So the answer to "practically nothing subscribes to real-time" is: character
effects and combat correctly leave for the beat clock, but **ambient world
behavior and the beat generator itself stay real-time** — and a shared,
deterministically-drivable pulse remains the right home for them.

## GC / reaping is its own coarse task

The reapers (idle instances, wilderness, expired objects, zone resets) are
*housekeeping* — running them at a fast heartbeat means full-cache scans
10×/second for no benefit. They should be their **own coarse periodic task**
(every ~5s), decoupled from the fast pulse — exactly like `_flush_loop`
already is. This is the "let GC occur on its own" instinct, and it's right.

## How effects attach to a beat source (no double-tick)

An effect must advance **once per beat from exactly one source**:

- If the object is in a **combat encounter**, the encounter's beat advances
  its participants' beat-effects (one beat per beat).
- Otherwise, the **ambient beat** (heartbeat-driven) advances them.
- The two must not both fire: the ambient driver **skips objects currently in
  an encounter** (a cheap `in_combat` check). On leaving combat, the object
  rejoins the ambient beat mid-phase (its remaining beats are preserved).

Effects therefore store **remaining beats** (not seconds, not pulses); the
beat source decrements by one each beat and expires at 0.

## The real-time substrate, done right

Independently of the beats work, the real-time loop should get:

1. **A faster, configurable heartbeat** (`tick_interval` already config; lower
   the default, e.g. 0.1–0.25s) → sub-100ms `wait()`, near-real-time output.
2. **Drift-correcting sleep** — sleep until `last_target + interval`, not
   `sleep(interval)` after the work, so a heavy pulse self-corrects instead of
   accumulating lag (matters at a fast beat).
3. **Second-based ambient behaviors** — spawners/decay/etc. already use
   `tick_interval` (seconds) + `delta`; the pulse-counting stragglers convert
   to decrement `remaining -= delta`, so the heartbeat rate never changes
   pacing.
4. **Start-phase jitter** — seed each recurring timer's phase with a random
   offset in `[0, interval)` so siblings don't lockstep (once, at start; it
   persists).
5. **Reapers off the fast pulse** onto their own ~5s task (above).

## Migration

- `TimedEffectBehavior` / `DecayBehavior` and any pulse-counters →
  seconds-or-beats (decrement by `delta` / by beat), not pulse counts.
- Effect params reinterpreted: character-effect durations become **beats**;
  infrastructure durations stay **seconds**. Update the example content/packs.
- Combat's beat loop gains a "advance participants' effects one beat" step;
  the ambient beat driver is new (small).
- No player-visible change except: effects now dilate with combat pacing, and
  timings are smoother/staggered.

## Config surface

- `tick_interval` (real-time heartbeat, seconds) — shipped, default lowered to 0.1s.
- `world_beat` (ambient out-of-combat beat length, seconds) — shipped, default 4s (wired to `set_world_tick` at boot).
- `combat_beat_min/max/default` — exist (the encounter clamp).
- `reap_interval` (GC coarse cadence) — shipped, default 5s (drives `_reap_loop`).

## Decisions (signed off 2026-07-16)

1. **Default heartbeat = 0.1s.** Low cost, and the real-time-output win is
   worth it. Configurable via `tick_interval`.
2. **`wait()` is exact** — its own async task per wait (one-shot, already
   non-durable, so no reboot cost). Off the shared pulse.
3. **Ambient world behaviors stay on real-time seconds** (spawners, wander,
   decay, zone-reset). Only **creatures'** effects/actions live on beats and
   dilate — world housekeeping doesn't. This also settled the "is real-time
   worth it?" question: yes, leaner — real-time is the **world tempo +
   housekeeping** substrate (ambient-beat generator + ambient behaviors),
   kept shared for testability/footprint/reboot-safety even in a world with
   time-magic.
4. **Beats are integer (= rounds).** "3 attacks per 2 rounds", haste, slow,
   and a Time-Lord "slow time" are **not** sub-beat timing — they are an
   **action economy** (a per-creature fractional actions-per-round rate,
   accumulated) plus a **per-creature beat multiplier** (haste ×2, slow ×0.5),
   both living in the **combat ruleset / game system**, not the kernel. The
   kernel hands out integer beats; the ruleset decides how many actions a
   creature spends per beat and at what relative rate it experiences them.

### The three layers (final shape)

```
real-time (seconds, 0.1s pulse)   world tempo: ambient-beat gen, spawners,
                                  decay, wander, zone-reset; + wait() (own
                                  async), GC/reapers (own coarse task)
        │  mints beats at the ambient rate (out of combat)
        ▼
beats (integer rounds)            character effects + combat maneuvers.
                                  Length is CONTEXTUAL (encounter beat in
                                  combat, ambient beat out); PER-CREATURE
                                  MULTIPLIER enables haste/slow/slow-time.
        │
        ▼
action economy (game system)      fractional actions-per-round, accumulated
                                  (3 attacks / 2 rounds); GURPS Basic Speed,
                                  Rapid Strike, etc. Ruleset, not kernel.
```

Slow-time (Time Lord) = a per-creature beat multiplier on the beat layer; it
needs nothing from real-time. Action frequency = the game system's economy on
top of integer beats. The kernel stays simple.

## Recommended plan

Two loosely-coupled work items, buildable in either order:

- **A — Real-time substrate** (independent, lower-risk): fast configurable
  heartbeat + drift-correction + reapers-to-own-task + seconds-based ambient
  behaviors + jitter. Delivers precision, low-latency output, staggering.
- **B — Beat clock** (the bullet-time): effects in beats, encounter advances
  participants' effects, ambient beat driver, double-tick guard. Delivers
  time-dilation and the GURPS "N rounds" idiom.

Both touch the server core, so each should ship with tests and a vision-keeper
audit. *No decisions are locked by this doc — it's the map for sign-off.*

## As built

Both items shipped together (2026-07-16). Where each piece lives:

**Beat clock (B).** `realm/core/beats.py` is the new beat abstraction:
`BeatBehavior` (a `Behavior` whose `should_tick` is always False and that
exposes `on_beat`), `deliver_beat(obj)` (advances every `BeatBehavior` on the
object by its multiplied beat count), the per-creature multiplier with
fractional carry (`db.beat_multiplier` + `db.beat_acc` — haste 2.0, slow 0.5,
Time-Lord 0.25 → 1,2,1,2 for 1.5), `has_beat_behavior`, and
`ambient_beat_targets` (the double-tick guard: skip anything tagged
`in_combat`). Effects (`realm/behaviors/effects.py`) are now `BeatBehavior`s —
`TimedEffectBehavior.on_beat` replaces the old `tick(obj, delta)`; interval and
duration are counted in **beats**. Combat drives its participants:
`encounter.resolve_round` calls `deliver_beat` on each after the round
advances. Multi-beat effects seed a random initial phase (`jitter`, opt-out)
so a roomful of poisons don't pulse in unison; per-beat (interval 1, the combat
default) effects get no jitter and thus exact, unchanged pulse counts.

**Real-time substrate (A).** `Behavior.tick_interval` now defaults to
`WORLD_TICK` (in `realm/core/behaviors.py`) instead of 0, so pulse-counting
world behaviors keep their pacing no matter how fine the heartbeat runs;
`set_world_tick` is called at boot from the `world_beat` config (default 4s).
`GameServer._tick_loop` is drift-correcting (aims at a fixed grid, resyncs when
late), seeds start-phase jitter for new behaviors, and mints the ambient beat
every `world_beat` via `ambient_beat_targets` + `deliver_beat`. Reaping runs on
its OWN coarse task (`_reap_loop`, cadence `reap_interval`, default 5s) so a
slow sweep never stalls the heartbeat. Config surface: `tick_interval`
(heartbeat, default **0.1s**), `world_beat` (ambient beat, 4s), `reap_interval`
(5s) — all in `Settings`/`GameServer`.

**Post-audit hardening.** An adversarial architecture audit surfaced and this
now fixes: haste (`beat_multiplier > 1`) could re-arm an effect expiring on an
earlier beat of the same delivery — `deliver_beat` re-reads the live behavior
list each beat and skips detached ones; `beat_multiplier == 0` now means true
stasis (0 beats) instead of silently reading as 1; the multiplier is clamped to
`[0, MAX_BEAT_MULTIPLIER]` so softcode can't spin the loop; a persisted
`in_combat` tag is scrubbed on load (`_scrub_stale_combat_state`) so a
mid-fight-saved creature rejoins the ambient beat instead of freezing forever;
effect jitter seeds once (persists across reboot); stale `beat_acc` carry is
cleared when a multiplier returns to 1.

**Exact `wait()` (A, decision 2).** `ScriptEngine.schedule_wait` spawns one
asyncio timer per wait (`_wait_timer` → `_deliver_wait`, atomically claimed so
a wait can't double-fire); `cancel_wait` cancels the task; `shutdown_waits`
cancels all on stop/reboot (wired into `GameServer.stop` and
`Simulator.close`). The Simulator sets `engine.defer_waits = True` — a
virtual-clock mode where waits fire only on an explicit `tick_waits()` pump, so
tests stay deterministic while production uses real timers.

**Tests.** `tests/test_beats.py` (deliver/multiplier/bullet-time/double-tick
guard/heartbeat default); real-timer + cancel coverage in
`tests/test_softcode_builders.py::TestWaits`; effect tests drive `on_beat`.
