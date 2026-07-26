# 036. Weather system

> Checklist item 36 ([now]): *zone masters, on_tick, remit to zone_rooms()*

**What you'll build:** A harbor zone whose sky drifts between clear,
overcast, rain, and storm on its own. Every room in the zone hears the
change, and every room's description reports the current weather when
you look.

**Concepts:** the zone master as an area's brain,
`script_ticker` plus [`on_tick`](../reference/softcode.md#lifecycle-hooks)
for a world heartbeat, a state table in plain attributes,
[`zone_rooms()`](../reference/softcode.md#fn-zone_rooms) plus
[`remit()`](../reference/softcode.md#fn-remit) for zone-wide broadcast,
and a `[[...]]` desc reading shared state.

## How it works

Weather is *zone state*, so it lives where zone state belongs: on the
**zone master**, one object tagged into the zone with `@zone/master`.
Rooms join the zone with `@zone here = harbor`, and the master carries a
single `weather` attribute plus the tables that describe each state.
Attribute reads are open to every script, so one attribute drives the
whole area, the same one-clock-many-readers pattern as the day/night
clock in [tutorial 037](037_day_night_descs.md). Any hazard tick or NPC
script can ask the sky what it is doing.

Three pieces:

1. **Drift is a random walk on a list.** Each tick the master looks up
   where the current state sits in `wx_states`, steps `-1/0/+1`
   (clamped at the ends), and only announces when the state actually
   changed. So weather never jumps from clear to storm; it worsens
   through overcast and rain, like real weather.

2. **Broadcast is [`remit()`](../reference/softcode.md#fn-remit) to
   [`zone_rooms()`](../reference/softcode.md#fn-zone_rooms).**
   `zone_rooms('harbor')` returns every room tagged `zone:harbor`, and a
   list comprehension remits the transition line to each. Rooms added to
   the zone later get weather for free, because membership is the tag,
   not a wiring step.

3. **Descriptions are stamped, not fetched.** When the state changes,
   the master also writes the matching standing line from `wx_descs`
   onto each zone room as a `wx_line` attribute, and every room desc then
   carries a `[[...]]` block that just reads `V('wx_line', '')`.
   Push-on-change beats pull-per-look: the remote table lookup happens
   once per transition, on the ticker (which runs on its own worker
   stack), while the block that runs on every look, per viewer, on the
   look's own call stack stays a single cheap local read. Keep
   render-time blocks local and shallow as a habit, because deep chains
   of remote reads
   ([`get_attr`](../reference/softcode.md#fn-get_attr)`('<name>', ...)`
   inside `.get(...)`) at render time are where inline blocks hit the
   sandbox's limits.

The tick cadence is one number on the behavior: `interval:15` runs the
drift roughly once a minute at the default 4-second world tick. Turn it
up for languid weather, down for a squall-prone coast.

## Build it

Dig two harbor rooms and tag them into the zone with `@zone`:

```text
@dig Harbor Quay = quay, back
quay
@zone here = harbor
@dig Fishmarket Row = row, quay
row
@zone here = harbor
quay
```

Create the sky, tag it as the zone's master with `@zone/master`, and
drop it so it stands in the world:

```text
@create Harbor Sky
@zone/master Harbor Sky = harbor
drop Harbor Sky
```

Give it a starting state, the ordered list of states, and two lookup
tables: the transition *announcements* the rooms hear, and the standing
*description* lines they show:

```text
@set Harbor Sky/weather = clear
@set Harbor Sky/wx_states = ["clear", "overcast", "rain", "storm"]
@set Harbor Sky/wx_msgs = {"clear": "The cloud breaks; pale sun lights the water.", "overcast": "A grey ceiling slides in off the sea.", "rain": "Rain sets in, beading on rope and rail.", "storm": "The wind climbs to a howl; rain comes in sideways."}
@set Harbor Sky/wx_descs = {"clear": "Sunlight hammers the tin roofs.", "overcast": "The light sits flat under a grey lid of cloud.", "rain": "Rain hisses on the harbor water.", "storm": "Spray and rain scour the planking."}
```

The drift itself runs on the master's
[`on_tick`](../reference/softcode.md#lifecycle-hooks). It finds where the
current state sits with [`member`](../reference/softcode.md#fn-member)
(1-indexed, so subtract one), takes a `-1/0/+1` step with
[`rand`](../reference/softcode.md#fn-rand) and pins it to the table with
[`clamp`](../reference/softcode.md#fn-clamp), and does nothing at all on
a no-change tick. On a real change it writes the new state, then for
each zone room stamps the standing line with
[`set_attr`](../reference/softcode.md#fn-set_attr) and announces the
transition with [`remit`](../reference/softcode.md#fn-remit):

```text
@set Harbor Sky/on_tick = '''
states = V('wx_states', [])
i = member(V('weather', 'clear'), states) - 1  # member is 1-indexed; -1 makes a list index, or -1 if the state is unknown
j = clamp(i + rand(0, 2) - 1, 0, len(states) - 1)  # step one place, clamped to the table ends
if i >= 0 and j != i:  # a no-change tick stays silent: no jump clear-to-storm, no spam
    state = states[j]
    set_attr(me, 'weather', state)
    for r in zone_rooms('harbor'):  # master and rooms share an owner, so set_attr on them is allowed
        set_attr(r, 'wx_line', V('wx_descs', {}).get(state, ''))  # stamp each room's standing line
        remit(r, V('wx_msgs', {}).get(state, ''))                 # announce the transition
'''
```

Attach the ticker. `interval:15` is fifteen world beats between rolls,
about a minute at the default four-second beat:

```text
@behavior Harbor Sky = script_ticker, interval:15
```

Finally, seed the quay's standing line so the room reads right before
the first transition (stamps arrive only with the *next* change), and
give the description a `[[...]]` block that reads that one local
attribute:

```text
@set here/wx_line = Sunlight hammers the tin roofs.
@desc here = Tarred pilings, drying nets, gulls arguing over fish heads. [[result = V('wx_line', '')]]
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
state in plain attributes, and `@set Harbor Sky/weather = storm` is a GM
override: the rooms re-stamp and announce at the next real transition
(nudge one with `@tr Harbor Sky/on_tick`).

## Going further

- **Mechanical weather:** storms can be more than flavor. A hazard-room
  tick ([tutorial 043](043_hazard_room.md)) can read the same attribute
  and roll checks only while `weather == 'storm'`, and a `perception`
  penalty can key off rain via a zone policy attribute on the master.
- **Seasonal tables:** keep `wx_msgs_winter` alongside `wx_msgs` and
  have `on_tick` pick the table by the calendar (a softcode clock,
  [tutorial 037](037_day_night_descs.md)).
- **Sheltered rooms:** skip rooms tagged `indoors` in the remit
  comprehension with
  [`if not has_tag(r, 'indoors')`](../reference/softcode.md#fn-has_tag),
  so taprooms only hear the storm as muffled flavor you author
  separately.
- **Weather over the wilderness:** procedural cells are tagged
  `zone:wilderness:<region>` ([tutorial 045](045_procedural_wilderness.md)),
  so the same master pattern can rain on a 21x21 frontier.
</content>
</invoke>
