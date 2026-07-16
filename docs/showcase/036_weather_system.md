# 036. Weather system

> Checklist item 36 — [now] — *zone masters, on_tick, remit to zone_rooms()*

**What you'll build:** A harbor zone whose sky drifts between clear,
overcast, rain, and storm on its own — every room in the zone hears the
change, and every room's description reports the current weather when
you look.

**Concepts:** the zone master as an area's brain, `script_ticker` +
`on_tick` for a world heartbeat, a state table in plain attributes,
`zone_rooms()` + `remit()` for zone-wide broadcast, `[[...]]` descs
reading shared state.

## How it works

Weather is *zone state*, so it lives where zone state belongs: on the
**zone master** — one object tagged into the zone with `@zone/master`.
Rooms join the zone with `@zone here = harbor`; the master carries a
single `weather` attribute plus the tables that describe each state.
Attribute reads are open to every script and every `[[...]]` block, so
one attribute drives the whole area — the same one-clock-many-readers
move as the town clock in [tutorial 068](068_npc_schedule.md).

Three pieces:

1. **Drift is a random walk on a list.** Each tick the master looks up
   where the current state sits in `wx_states`, steps `-1/0/+1`
   (clamped at the ends), and only announces when the state actually
   changed. So weather never jumps from clear to storm — it worsens
   through overcast and rain, like weather.

2. **Broadcast is `remit()` to `zone_rooms()`.** `zone_rooms('harbor')`
   returns every room tagged `zone:harbor`; a list comprehension remits
   the transition line to each. Rooms added to the zone later get
   weather for free — membership is the tag, not a wiring step.

3. **Descriptions are stamped, not fetched.** When the state changes,
   the master also writes the matching standing line from `wx_descs`
   onto each zone room as a `wx_line` attribute; every room desc then
   carries a `[[...]]` block that just reads `get_attr(me, 'wx_line',
   '')`. Push-on-change beats pull-per-look: the remote table lookup
   happens **once per transition, on the ticker** (which runs on its
   own worker stack), while the block that runs on *every look, per
   viewer, on the look's own call stack* stays a single cheap local
   read. Keep render-time blocks local and shallow as a habit — deep
   chains of remote reads (`get_attr('<name>', ...)` inside `.get(...)`)
   at render time are where inline blocks hit the sandbox's limits.

The tick cadence is one number on the behavior: `interval:15` runs the
drift roughly once a minute at the default 4-second world tick. Turn it
up for languid weather, down for a squall-prone coast.

## Build it

Dig two harbor rooms and tag them into the zone:

```text
@dig Harbor Quay = quay, back
quay
@zone here = harbor
@dig Fishmarket Row = row, quay
row
@zone here = harbor
quay
```

The sky itself — the zone master, its state, and its two tables (the
transition *announcements* and the standing *description* lines):

```text
@create Harbor Sky
@zone/master Harbor Sky = harbor
drop Harbor Sky
@set Harbor Sky/weather = clear
@set Harbor Sky/wx_states = ["clear", "overcast", "rain", "storm"]
@set Harbor Sky/wx_msgs = {"clear": "The cloud breaks; pale sun lights the water.", "overcast": "A grey ceiling slides in off the sea.", "rain": "Rain sets in, beading on rope and rail.", "storm": "The wind climbs to a howl; rain comes in sideways."}
@set Harbor Sky/wx_descs = {"clear": "Sunlight hammers the tin roofs.", "overcast": "The light sits flat under a grey lid of cloud.", "rain": "Rain hisses on the harbor water.", "storm": "Spray and rain scour the planking."}
```

The drift itself. `member()` finds the current state's position
(1-indexed, so `- 1`), `rand(0, 2) - 1` is the step, `clamp` pins it to
the table, and nothing at all happens on a no-change tick — that's the
spam discipline half of a weather system. On a real change, each zone
room gets the transition *announced* (`remit`) and its standing line
*stamped* (`set_attr` — the master controls the rooms by owner
delegation):

```text
@set Harbor Sky/on_tick = states = get_attr(me, 'wx_states', []); i = member(get_attr(me, 'weather', 'clear'), states) - 1; j = clamp(i + rand(0, 2) - 1, 0, len(states) - 1); (set_attr(me, 'weather', states[j]), [(set_attr(r, 'wx_line', get_attr(me, 'wx_descs', {}).get(states[j], '')), remit(r, get_attr(me, 'wx_msgs', {}).get(states[j], ''))) for r in zone_rooms('harbor')]) if i >= 0 and j != i else None
@behavior Harbor Sky = script_ticker, interval:15
```

Finally, seed the quay's standing line (stamps arrive with the *next*
transition; the seed covers the weather it was built under) and make
the description read it — one local attribute, nothing else:

```text
@set here/wx_line = Sunlight hammers the tin roofs.
@desc here = Tarred pilings, drying nets, gulls arguing over fish heads. [[result = get_attr(me, 'wx_line', '')]]
```

## Try it

```text
look
  Harbor Quay
  Tarred pilings, drying nets, gulls arguing over fish heads. Sunlight hammers the tin roofs.
```

Wait a minute or so (or `@tr Harbor Sky/on_tick` to force a drift roll):

```text
  A grey ceiling slides in off the sea.       <- heard on the quay AND in Fishmarket Row
look
  ... The light sits flat under a grey lid of cloud.
```

A friend standing in Fishmarket Row hears every transition; someone
outside the zone hears nothing. `@examine Harbor Sky` shows the current
state in plain attributes — and `@set Harbor Sky/weather = storm` is a
GM override: the rooms re-stamp and announce at the next real
transition (nudge one with `@tr Harbor Sky/on_tick`).

## Going further

- **Mechanical weather:** storms are more than flavor — a hazard-room
  tick ([tutorial 043](043_hazard_room.md)) can read the same attribute
  and roll checks only while `weather == 'storm'`, and a `perception`
  penalty can key off rain via a zone policy attribute on the master.
- **Seasonal tables:** keep `wx_msgs_winter` alongside `wx_msgs` and
  have `on_tick` pick the table by the calendar (a softcode clock,
  [tutorial 037](037_day_night_descs.md)).
- **Sheltered rooms:** skip rooms tagged `indoors` in the remit
  comprehension — `if not has_tag(r, 'indoors')` — so taprooms only
  hear the storm as muffled flavor you author separately.
- **Weather over the wilderness:** procedural cells are tagged
  `zone:wilderness:<region>` ([tutorial 045](045_procedural_wilderness.md)),
  so the same master pattern can rain on a 21x21 frontier.
