# 145. Scheduled world events

> Checklist item 145 — [now] — *cron-like scheduling, ticker + schedule registry, the world tick*

**What you'll build:** A colony AI that runs a daily timetable — a dawn
klaxon at 06:00, midday rations at 12:00, dusk lighting at 18:00 —
broadcast to every room of the colony, each firing exactly once per game
day. A schedule registry you edit as data, on a cron-like ticker.

**Concepts:** REALM's real clocks (what the world tick actually is), a
`script_ticker` as the poll loop, a schedule as a **list attribute**
(cron rows, not hard-coded calls), and once-per-day **deduplication** so
a slow clock can't double-fire an event.

## How REALM's clocks work

This is the tutorial the rest of the category points at for the
machinery. REALM runs **two deliberate clocks** (full design in
`docs/design/time-and-beats.md`), and it helps to know which is which:

- **Real-time seconds — the world tick.** One drift-correcting heartbeat
  (`tick_interval`, default ~0.1s) drives *infrastructure*: `wait()`
  fuses, output flushing, and the **world behaviors** — spawners, decay,
  wander, zone-reset, and every `script_ticker`. Behaviors don't run at
  0.1s, though: each behavior's cadence is pinned to `WORLD_TICK` (the
  *world tempo*, config `world_beat`, default **4s**), so a
  `script_ticker` with `interval:N` fires every **N × 4 seconds** no
  matter how fine the underlying heartbeat runs. That decoupling (added
  with the global-tick rework) is why every tutorial can say "interval:15
  ≈ once a minute" and mean it.
- **Beats (integer rounds) — the turn clock.** Character effects (poison,
  buffs, regen) and combat maneuvers advance in *beats*, whose real
  length is contextual: the encounter's pace in combat, the ambient
  `world_beat` out of it. Slow a fight and the poison in it dilates too.
  Beats are **not** what you schedule world events on — a dawn klaxon is
  wall-clock infrastructure, so it belongs on the tick.
- **Housekeeping** (reaping expired objects, idle instances) runs on its
  **own** coarse task (`reap_interval`, ~5s), off the fast pulse.

The takeaway for scheduling: **a timetable is real-time world tempo, so
it lives on a `script_ticker`.** You poll a clock and act — the softcode
equivalent of cron's minute loop.

## How it works

**The clock and the schedule are separate.** A bare clock object
increments an `hour` (the [068](068_npc_schedule.md) minimal clock; swap
in [144](144_game_calendar.md)'s full chronometer for real dates). The
colony AI — a **zone master**, so it can broadcast to and be heard from
every colony room — carries the timetable.

**The schedule is data, not code.** `schedule` is a list of rows
`{"hour": H, "msg": "..."}`. Adding an event is `@set`-ing another row,
never touching the tick script — the registry pattern. Each tick the AI
reads the clock's hour and fires every row whose hour matches.

**Dedup is the cron subtlety.** If the clock is slower than the poll
(several AI ticks pass within one game-hour), a naive match fires the
06:00 klaxon on *every* tick of hour 6. So each row remembers the hour it
last fired at (`fired_<i>`), and a row fires only when the current hour
differs — "at most once per occurrence." One counter per row, and the
timetable stays honest at any clock/poll ratio.

## Build it

The colony — two rooms in one zone — and a bare hour-clock:

```text
@dig Command Deck = deck, out
deck
@zone here = colony
@dig Hydro Bay = hydro, deck
hydro
@zone here = colony
deck
@create colony clock
drop colony clock
@set colony clock/hour = 5
@set colony clock/on_tick = set_attr(me, 'hour', (V('hour', 0) + 1) % 24)
@behavior colony clock = script_ticker, interval:1
```

The colony AI: the zone master, the schedule registry, and the cron
tick. The comprehension fires each due, not-yet-fired-this-hour row and
stamps its `fired_<i>`:

```text
@create Colony AI
drop Colony AI
@zone/master Colony AI = colony
@set Colony AI/schedule = [{"hour": 6, "msg": "A dawn klaxon echoes through the colony. Day cycle begins."}, {"hour": 12, "msg": "Midday rations are served in the mess."}, {"hour": 18, "msg": "Dusk. The corridor lights fade to amber."}]
@set Colony AI/on_tick = h = get_attr('colony clock', 'hour', 0); [(act(me, e['msg'], targeting='zone'), set_attr(me, 'fired_' + str(i), h)) for i, e in enumerate(V('schedule', [])) if e['hour'] == h and V('fired_' + str(i), -1) != h]
@behavior Colony AI = script_ticker, interval:1
```

`act(me, ..., targeting='zone')` is the all-call: a real propagated
action reaching every colony room, the same zone broadcast the
self-destruct klaxon uses in [tutorial 056](056_self_destruct.md).

## Try it

Stand someone on the Command Deck and another in the Hydro Bay, then
walk the clock forward (`@tr` forces one tick without waiting):

```text
@tr colony clock/on_tick      hour 5 -> 6
@tr Colony AI/on_tick
   -> (both rooms) A dawn klaxon echoes through the colony. Day cycle begins.
@tr Colony AI/on_tick          same hour: silent (already fired at 6)
@tr colony clock/on_tick      hour 6 -> 7
@tr Colony AI/on_tick          nothing scheduled at 7
```

Advance to hour 12 and the mess call goes out; to 18, the lights fade.
Each fires once, in every colony room, and a friend outside the zone
hears none of it.

## Going further

- **Minute precision:** poll [144](144_game_calendar.md)'s chronometer
  and match on `(day, hour, minute)` — cron down to the game-minute.
- **One-shot events:** a row with a `once` flag that `del`s itself from
  the schedule after firing — a story beat, not a daily.
- **Weekly / seasonal:** match on `(m // 1200) % 7` for weekdays, or on
  the month for a seasonal festival, using the calendar's fields.
- **Payloads, not just messages:** let a row carry an attr name and
  `eval_attr(me, e['action'])` — spawn a merchant caravan at 09:00, close
  the gates at 22:00 (the behavior-swap idiom of
  [068](068_npc_schedule.md)).
- **A global timetable:** crown the master on a `zone:world` room and the
  same registry drives server-wide scheduled events.
