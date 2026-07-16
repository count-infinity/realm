# 041. Ambient room messages

> Checklist item 41 — [now] — *script_ticker + rand gates, spam discipline*

**What you'll build:** A gallery that occasionally mutters — a cold
draft, settling timbers, sifting dust — from an invisible emitter with
a tuned chance, a long interval, and the manners to stay quiet when
nobody's there.

**Concepts:** `script_ticker` + `on_tick`, `rand()` probability gates,
`remit()`, a player-presence gate, per-room tuning via plain
attributes, `invisible` props.

## How it works

Ambient flavor is the docs' own `script_ticker` hello-world (the parrot
that squawks on a cadence) — the craft is all in **spam discipline**,
because ambient text is the fastest way to teach players to skim past
*everything* your game prints. The emitter enforces three rules:

1. **A chance gate, not a metronome.** Each tick rolls
   `rand(1, 100) <= chance`; at `chance = 25` and `interval:8` (one
   roll per ~32s at the default 4-second tick), a line lands about
   every two minutes — *irregularly*, which is what makes it ambient
   rather than a cuckoo clock. Both knobs are plain attributes: tune a
   creaky attic loud and a mausoleum near-silent without touching the
   script.

2. **An audience gate.** The comprehension checks for player-tagged
   occupants and skips the remit into an empty room. Nobody's there to
   read it, so the room doesn't perform — and a hundred idle emitters
   cost the world nothing but their skipped rolls.

3. **One emitter per room, lines as data.** The lines live in a list
   attribute; `rand` picks one. Restock the atmosphere with a single
   `@set` — a builder pass over a whole zone is `@foreach` + new line
   lists, no logic edits.

The emitter is a real object dropped in the room, tagged `invisible`
at the end so it never shows up in `look` (build first, hide last —
`@find cold draft` recovers it for later edits). You could hang the
`on_tick` on the room itself instead ([tutorial 039](039_underwater_room.md)
does); a separate emitter keeps flavor separable from the room's own
machinery and `@clone`-able between rooms.

## Build it

```text
@dig The Long Gallery = gallery, back
gallery
@create cold draft
drop cold draft
@set cold draft/lines = ["A cold draft worries the candle flames.", "Somewhere above, timbers settle with a groan.", "Dust sifts down from the rafters."]
@set cold draft/chance = 25
@set cold draft/on_tick = lines = get_attr(me, 'lines', []); (remit(here, lines[rand(0, len(lines) - 1)]) if lines and [o for o in contents(here) if has_tag(o, 'player')] else None) if rand(1, 100) <= get_attr(me, 'chance', 25) else None
@behavior cold draft = script_ticker, interval:8
@tag cold draft = invisible
```

Read the `on_tick` inside-out: the *outer* condition is the chance
gate (cheap, rolls first); the inner parenthesis picks a line and
remits it only if the room holds a player. `lines and ...` also makes
an emptied line list fail safe.

## Try it

Stand in the gallery a few minutes:

```text
  Somewhere above, timbers settle with a groan.
  ...
  A cold draft worries the candle flames.
```

`look` shows no emitter — the draft is invisible. Impatient? Force a
roll with `@tr cold draft/on_tick`, crank `@set cold draft/chance =
100` while testing, then set it back down where it belongs. Step out
to the workroom and the gallery goes silent — no audience, no
performance.

## Going further

- **Context-aware ambience:** branch the line list on shared state —
  storm lines while `get_attr('Harbor Sky', 'weather') == 'storm'`
  ([tutorial 036](036_weather_system.md)), night lines after the town
  clock strikes 21 ([tutorial 037](037_day_night_descs.md)).
- **No repeats:** remember the last index in an attribute and re-roll
  once if it matches — the two-line fix for back-to-back groans.
- **Rare events among the flavor:** give one line a 1-in-100 outer
  roll of its own that also drops a real object — atmosphere that
  occasionally *matters* teaches players to read it.
- **Zone-wide atmosphere:** hang the same `on_tick` on a zone master
  and remit to a random room from `zone_rooms()` — one haunted-house
  brain instead of an emitter per room.
