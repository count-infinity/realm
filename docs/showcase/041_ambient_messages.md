# 041. Ambient room messages

> Checklist item 41 ([now]): *script_ticker + rand gates, spam discipline*

**What you'll build:** A gallery that occasionally mutters, a cold draft, settling
timbers, sifting dust, from an invisible emitter with a tuned chance, a long
interval, and the manners to stay quiet when nobody is there.

**Concepts:** `script_ticker` running
[`on_tick`](../reference/softcode.md#lifecycle-hooks), a
[`rand`](../reference/softcode.md#fn-rand) probability gate,
[`remit`](../reference/softcode.md#fn-remit), a player-presence gate,
per-room tuning through plain attributes, and `invisible` props.

## How it works

The finished shape is one small object dropped in the room whose `on_tick`
fires on a cadence, rolls the dice, and, when the roll lands and a player is
present, emits one line of atmosphere. The craft is not the ticker (that is the
same `script_ticker` behavior the [flashlight](006_flashlight.md) uses to drain
its battery); the craft is all in **spam discipline**, because ambient text is
the fastest way to teach players to skim past everything your game prints. This
emitter enforces three rules, and the rest of the section walks through each.

### Why a chance gate instead of a metronome

Each tick rolls `rand(1, 100) <= chance`. At `chance = 25` and `interval:8`,
which is one roll per about 32 seconds at the default 4 second world beat, a
line lands roughly every two minutes, and irregularly, which is what makes it
read as ambient rather than as a cuckoo clock. Both knobs are plain attributes,
so you can tune a creaky attic loud and a mausoleum near silent without ever
touching the script.

### Why an audience gate

Before it emits, the tick checks the room for a player-tagged occupant and skips
the [`remit`](../reference/softcode.md#fn-remit) into an empty room. Nobody is
there to read it, so the room does not perform, and a hundred idle emitters cost
the world nothing but their skipped rolls.

### Where the lines live

One emitter carries the lines as data in a list attribute, and `rand` picks the
index. Restocking the atmosphere is a single `@set`, and a builder pass over a
whole zone is `@foreach` plus new line lists, with no logic edits.

### The emitter runs its own tick, so no `target` guard

The emitter is a real object dropped in the room and tagged `invisible` last, so
it never shows up in `look` (build first, hide last, and `@find cold draft`
recovers it for later edits). Its `on_tick` runs on **its owner**, the draft
itself, once per due beat. That is the opposite of a reactive
`ON_<EVENT>` hook, which fires on every object in the room and therefore needs
an `if target is me:` guard so it only reacts to its own business (the
[slot machine](001_slot_machine.md) shows that pattern). A ticker has no
`target` and no other object triggers it, so there is nothing to guard against
here; do not copy a `target is me` line into an `on_tick`. You could hang the
`on_tick` on the room itself instead, which is what the
[underwater room](039_underwater_room.md) does; a separate emitter keeps flavor
separable from the room's own machinery and `@clone`-able between rooms.

## How the tick reads

Read the block as a chance gate wrapping an audience gate. The cheap
`rand(1, 100)` rolls first and short-circuits most ticks. Only when it passes
does the tick read the line list, look for a player, and, if both are there,
[`remit`](../reference/softcode.md#fn-remit) one random line to the room:

```text
if rand(1, 100) <= V('chance', 25):
    lines = V('lines', [])
    audience = [o for o in contents(here) if has_tag(o, 'player')]
    if lines and audience:
        remit(here, lines[rand(0, len(lines) - 1)])
```

[`V('chance', 25)`](../reference/softcode.md#fn-v) reads the emitter's own
`chance` with a default, [`contents(here)`](../reference/softcode.md#fn-contents)
lists what is in the room, and [`has_tag`](../reference/softcode.md#fn-has_tag)
keeps only the players. `here` inside the tick is the emitter's location, the
room, so `remit(here, ...)` reaches everyone standing in it.

## Build it

The `on_tick` is a `'''` multi-line block (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)):
open the `@set` line with a trailing `'''`, write the body as indented softcode,
and close with a line of just `'''`.

First the shell. Dig a gallery off your workroom, step into it, then create the
emitter and drop it so it lives in the room:

```text
@dig The Long Gallery = gallery, back
gallery
@create cold draft
drop cold draft
```

The atmosphere is data. `lines` is the pool the tick draws from, and `chance` is
the per-tick percentage, both plain single-value attributes you can retune with
one `@set`:

```text
@set cold draft/lines = ["A cold draft worries the candle flames.", "Somewhere above, timbers settle with a groan.", "Dust sifts down from the rafters."]
@set cold draft/chance = 25
```

Now the tick itself. The chance gate rolls first because it is cheap and skips
most beats, and the inner guard keeps a silent room silent:

```text
@set cold draft/on_tick = '''
if rand(1, 100) <= V('chance', 25):  # cheap chance gate rolls first, skips most beats
    lines = V('lines', [])
    audience = [o for o in contents(here) if has_tag(o, 'player')]
    if lines and audience:  # empty room, or emptied list, stays silent
        remit(here, lines[rand(0, len(lines) - 1)])
'''
```

Attach the ticker and set its cadence. `interval:8` runs `on_tick` every eight
world beats, about 32 seconds at the default four second beat:

```text
@behavior cold draft = script_ticker, interval:8
```

Finally hide the emitter, so `look` shows atmosphere but never the object making
it. `@tag` writes the same `invisible` tag the perception engine reads to drop
a thing from room displays:

```text
@tag cold draft = invisible
```

## Try it

Stand in the gallery a while and the room mutters on its own cadence:

```text
> look
The Long Gallery
(no cold draft in the listing: it is invisible)

  Somewhere above, timbers settle with a groan.
  ...
  A cold draft worries the candle flames.
```

Impatient? Force a beat with `@tr`, which runs the bare `on_tick` code directly
(it fires code attributes, not `$`-command triggers):

```text
> @set cold draft/chance = 100
> @tr cold draft/on_tick
Dust sifts down from the rafters.
```

Set `chance` back down where it belongs when you are done testing. Step out to
the workroom with `back` and the gallery goes quiet: with no audience, the
emitter rolls and skips, so it performs to nobody.

## Going further

- **Context-aware ambience:** branch the line pool on shared state, storm lines
  while `get_attr('Harbor Sky', 'weather') is 'storm'`
  ([weather system](036_weather_system.md)), night lines after the town clock
  strikes 21 ([day/night descs](037_day_night_descs.md)).
- **No repeats:** remember the last index in an attribute and re-roll once if it
  matches, the two-line fix for back-to-back groans.
- **Rare events among the flavor:** give one line a 1-in-100 inner roll of its
  own that also drops a real object, atmosphere that occasionally matters and so
  teaches players to read it.
- **Zone-wide atmosphere:** hang the same `on_tick` on a zone master and
  [`remit`](../reference/softcode.md#fn-remit) to a random room from
  [`zone_rooms()`](../reference/softcode.md#fn-zone_rooms), one haunted-house
  brain instead of an emitter per room.
