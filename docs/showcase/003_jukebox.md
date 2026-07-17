# 003. Jukebox

> Checklist item 3 — [now] — *prompt() menus, wait() chains, remit, script_ticker*

**What you'll build:** A neon jukebox. `play` offers a numbered track
menu (a `prompt()` wizard), your answer drops the arm, and the lyrics
roll out to the whole room one line at a time on a heartbeat — with a
window card that always shows what's spinning.

**Concepts:** `prompt()` as a menu (softcode wizards), function
attributes via `eval_attr()` (softcode's subroutine), the
`script_ticker` behavior + `on_tick` for anything periodic, `remit()`
room-wide ambience, tracks as pure data, a `[[...]]` now-playing
readout.

Builds on the [magic 8-ball](005_magic_8ball.md) (triggers, data
attributes). The [music box](009_music_box.md) is this gadget's
sibling built on `wait()` chains instead of a ticker — read both and
you own softcode timing.

## How it works

**A menu is just a prompt.** `prompt(enactor, text, 'on_pick')` prints
a question and captures the player's *next line* into the `on_pick`
attribute, answer bound as `arg0` (see the
[wizards guide](../guides/wizards.md)). There's no menu widget — the
"menu" is a string listing numbered choices, and `on_pick` validates
the number. Anything that isn't a valid number is politely spat back
out; `help`, `quit`, and `exit` always bypass a prompt, so no jukebox
can trap anyone.

**Lyrics need a clock, and there are two.** A `wait()` chain (each
line schedules the next) is exact but in-memory — a reboot mid-song
loses the rest of the record. The `script_ticker` behavior instead
runs the object's `on_tick` attribute on the server's one heartbeat:
attach it once with `@behavior`, and state (`spinning`, `cursor`)
lives in plain attributes, so a reboot resumes the song where it
stopped. Ambient furniture wants the ticker; fuses want `wait()` (the
[gas bomb](048_gas_bomb.md) makes the same choice the other way).

**One tick, one line.** `on_tick` reads which track is `spinning` and
a `cursor` into its lyric list, `remit()`s the next line to the room,
and advances. Past the last line it clears `spinning` and lifts the
arm — the classic run-out groove. No track selected, the tick does
nothing: an idle jukebox costs one attribute read per beat.

**Tracks are data.** A list of `{"title": ..., "lines": [...]}` dicts
in one attribute. Retheme the jukebox — swap the whole record library —
with a single `@set`, never touching a script. The menu itself is
built by a *function attribute* (`menu`), called with
`eval_attr(me, 'menu')` wherever it's needed.

## Build it

The cabinet, with a living window card — `spinning` is a track index,
or absent for silence:

```text
@create jukebox
drop jukebox
@desc jukebox = A chrome-and-neon jukebox from a more optimistic century. [[t = V('tracks', []); n = V('spinning', None); result = f"The window card reads: {t[n]['title'] if n is not None and n < len(t) else 'SILENCE'}."]]
```

The record library — pure data (`@set` parses JSON):

```text
@set jukebox/tracks = [{"title": "Stardust Rag", "lines": ["the void don't care, but baby I do", "every orbit brings me back to you"]}, {"title": "Vacuum Blues", "lines": ["got a hull full of nothing and nowhere to be"]}]
```

The menu renderer, as a function attribute — one place builds the
numbered listing from whatever the library holds:

```text
@set jukebox/menu = t = V('tracks', []); result = 'Pick a track: ' + ' '.join(f"[{i + 1}] {tr['title']}" for i, tr in enumerate(t)) + ' -- or anything else to walk away.'
```

`play` asks; `on_pick` answers. The callback validates (`isdigit`,
range), then either starts the record — index and cursor in attributes,
arm-drop announced to the room — or refuses:

```text
@set jukebox/cmd_play = $play: prompt(enactor, eval_attr(me, 'menu'), 'on_pick')
@set jukebox/on_pick = t = V('tracks', []); w = trim(arg0); n = int(w) if w.isdigit() else 0; ok = 1 <= n <= len(t); (set_attr(me, 'spinning', n - 1), set_attr(me, 'cursor', 0), remit(here, f"The jukebox whirs, and the arm drops on {t[n - 1]['title']}.")) if ok else pemit(enactor, 'The jukebox clunks and returns your choice unplayed.')
```

The heartbeat. `interval:4` is ticks between runs, so at the default
4-second tick one lyric line lands roughly every 16 seconds — retune
freely, it's data:

```text
@behavior jukebox = script_ticker, interval:4
@set jukebox/on_tick = n = V('spinning', None); t = V('tracks', []); i = V('cursor', 0); lines = t[n]['lines'] if n is not None and n < len(t) else []; (remit(here, f'~ {lines[i]} ~'), incr('cursor')) if n is not None and i < len(lines) else None; (del_attr(me, 'spinning'), remit(here, 'The record hisses into the run-out groove, and the arm lifts.')) if n is not None and i >= len(lines) else None
```

## Try it

```text
look jukebox
play
1
```

`look` reads `The window card reads: SILENCE.`; `play` prints
`Pick a track: [1] Stardust Rag [2] Vacuum Blues -- or anything else
to walk away.`; answering `1` shows everyone `The jukebox whirs, and
the arm drops on Stardust Rag.` — and `look jukebox` now reads the
title on the window card. Then wait (or force beats with
`@tr jukebox/on_tick`): each beat is one room-wide `~ lyric ~` line,
and after the last, `The record hisses into the run-out groove, and
the arm lifts.` Answer `9` (or `banana`) to a fresh `play` and the
jukebox clunks and returns your choice unplayed.

## Going further

- **Coin-op:** put the menu behind money — `ON_PAYMENT` plus the
  ledger idiom from the [slot machine](001_slot_machine.md), arming a
  `paid_<player>` credit that `play` checks and consumes.
- **A whole-club sound system:** `@zone` the venue's rooms together
  and swap `remit(here, ...)` for `act(here, ..., targeting='zone')` —
  every dance floor hears the same record.
- **Skip button:** `$skip` just `del_attr(me, 'spinning')` and remits
  the needle-scratch. State-in-attributes means every control is one
  line.
- **Request the B-side:** store `lines` per mood and pick the list by
  `tag_value(here, 'zone')` — the same record plays differently in the
  chapel and the cantina.
