# 003. Jukebox

> Checklist item 3 ([now]): *prompt() menus, wait() chains, remit, script_ticker*

**What you'll build:** A neon jukebox. `play` offers a numbered track menu (a
[`prompt()`](../reference/softcode.md#fn-prompt) wizard), your answer drops the
arm, and the lyrics roll out to the whole room one line at a time on a
heartbeat, with a window card that always shows what is spinning.

**Concepts:** [`prompt()`](../reference/softcode.md#fn-prompt) as a menu
(softcode wizards), function attributes via
[`eval_attr()`](../reference/softcode.md#fn-eval_attr) (softcode's subroutine),
a `script_ticker` running [`on_tick`](../reference/softcode.md#lifecycle-hooks),
attached and detached on demand with
[`attach_behavior`](../reference/softcode.md#fn-attach_behavior) and
[`detach_behavior`](../reference/softcode.md#fn-detach_behavior),
[`remit()`](../reference/softcode.md#fn-remit) room-wide ambience, tracks as
pure data, and a `[[...]]` now-playing readout.

It builds on the [magic 8-ball](005_magic_8ball.md) for triggers and data
attributes. The [music box](009_music_box.md) is this gadget's sibling built on
`wait()` chains instead of a ticker, so reading both leaves you owning softcode
timing.

## How it works

A jukebox is one object that turns a `play` command into a menu, records your
pick in a pair of attributes, then feeds the chosen track's lyrics to the room
one line per heartbeat. This section covers where the menu comes from, the two
ways to keep time, what a single tick does, and why the track library is data.

### How a menu works without a menu widget

[`prompt(enactor, text, 'on_pick')`](../reference/softcode.md#fn-prompt) prints a
question and captures the player's *next line* into the `on_pick` attribute,
with the answer bound as `arg0` (see the [wizards guide](../guides/wizards.md)).
There is no menu widget: the "menu" is a string listing numbered choices, and
`on_pick` validates the number. Anything that is not a valid number is politely
returned, and `help`, `quit`, and `exit` always bypass a prompt, so no jukebox
can trap anyone.

### Which clock drives the lyrics

Lyrics need a clock, and REALM gives you two. A `wait()` chain, where each line
schedules the next, is exact but in-memory, so a reboot mid-song loses the rest
of the record. The `script_ticker` behavior instead runs the object's `on_tick`
attribute on the **world beat** (`WORLD_TICK`, roughly four seconds and
configurable, which is the ambient tempo, not the much faster scheduler pulse),
and because the state (`spinning`, `cursor`) lives in plain attributes a reboot
resumes the song where it stopped. Rather than run a permanent clock, this
jukebox attaches the ticker with
[`attach_behavior`](../reference/softcode.md#fn-attach_behavior) the moment a
record starts and drops it with
[`detach_behavior`](../reference/softcode.md#fn-detach_behavior) at the run-out,
so a silent jukebox runs no clock at all. Furniture that is always active can
keep a permanent ticker, whereas an on-demand gadget like this one wants the
attach and detach pair (a fuse instead wants `wait()`, and the
[gas bomb](048_gas_bomb.md) makes that choice the other way).

### What one tick does

`on_tick` reads which track is `spinning` and a `cursor` into its lyric list,
[`remit()`](../reference/softcode.md#fn-remit)s the next line to the room, and
advances. Past the last line it clears `spinning`, detaches its own ticker, and
lifts the arm, which is the classic run-out groove. Because that detach is the
last thing a finished record does, an idle jukebox carries no clock at all: the
ticker exists only while a record is playing.

### Why the track library is data

The library is a list of `{"title": ..., "lines": [...]}` dicts in one
attribute. Retheme the jukebox by swapping the whole record library with a
single `@set`, never touching a script. The menu itself is built by a *function
attribute* (`menu`), called with
[`eval_attr(me, 'menu')`](../reference/softcode.md#fn-eval_attr) wherever it is
needed.

## Build it

The scripts here are `'''` multi-line blocks (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs));
the track library is plain data.

The cabinet carries a living window card, where `spinning` is a track index or
is absent for silence:

```text
@create jukebox
drop jukebox
@desc jukebox = A chrome-and-neon jukebox from a more optimistic century. [[t = V('tracks', []); n = V('spinning', None); result = f"The window card reads: {t[n]['title'] if n is not None and n < len(t) else 'SILENCE'}."]]
```

The record library is pure data (`@set` parses JSON):

```text
@set jukebox/tracks = [{"title": "Stardust Rag", "lines": ["the void don't care, but baby I do", "every orbit brings me back to you"]}, {"title": "Vacuum Blues", "lines": ["got a hull full of nothing and nowhere to be"]}]
```

The menu renderer is a function attribute, so one place builds the numbered
listing from whatever the library holds. It is called with
[`eval_attr(me, 'menu')`](../reference/softcode.md#fn-eval_attr), which returns
whatever the script assigns to `result`:

```text
@set jukebox/menu = '''
t = V('tracks', [])
labels = [f"[{i + 1}] {tr['title']}" for i, tr in enumerate(t)]
result = 'Pick a track: ' + ' '.join(labels) + ' -- or anything else to walk away.'
'''
```

`play` asks and `on_pick` answers. The callback validates (`isdigit`, range),
then either starts the record or refuses. Starting a record writes the index and
cursor with [`set_attr`](../reference/softcode.md#fn-set_attr), attaches the
clock with [`attach_behavior`](../reference/softcode.md#fn-attach_behavior), and
announces the arm-drop to the room; a bad choice is a single
[`pemit`](../reference/softcode.md#fn-pemit). It detaches any running ticker
first, so re-selecting mid-song restarts the clock cleanly instead of stacking a
second one:

```text
@set jukebox/cmd_play = $play: prompt(enactor, eval_attr(me, 'menu'), 'on_pick')
@set jukebox/on_pick = '''
t = V('tracks', [])
w = trim(arg0)
n = int(w) if w.isdigit() else 0
if 1 <= n <= len(t):
    detach_behavior(me, 'script_ticker')  # drop any running clock first, so re-picking restarts it cleanly
    set_attr(me, 'spinning', n - 1)
    set_attr(me, 'cursor', 0)
    attach_behavior(me, 'script_ticker', interval=1)  # attach the clock on demand, only while a record plays
    remit(here, f"The jukebox whirs, and the arm drops on {t[n - 1]['title']}.")
else:
    pemit(enactor, 'The jukebox clunks and returns your choice unplayed.')
'''
```

Finally the `on_tick` script, which the attached ticker runs once per world beat
while a record spins (`interval=1` above is one beat; use a larger interval to
space the lyrics further). Each beat advances the `cursor` with
[`incr`](../reference/softcode.md#fn-incr) and remits the next line, and the
run-out clears `spinning` with
[`del_attr`](../reference/softcode.md#fn-del_attr) and detaches the ticker so the
jukebox falls silent and idle:

```text
@set jukebox/on_tick = '''
n = V('spinning', None)
t = V('tracks', [])
i = V('cursor', 0)
lines = t[n]['lines'] if n is not None and n < len(t) else []
if n is not None and i < len(lines):
    remit(here, f'~ {lines[i]} ~')
    incr('cursor')
elif n is not None:
    del_attr(me, 'spinning')  # run-out: clear state and detach the clock, so an idle jukebox runs nothing
    detach_behavior(me, 'script_ticker')
    remit(here, 'The record hisses into the run-out groove, and the arm lifts.')
'''
```

## Try it

```text
look jukebox
play
1
```

`look` reads `The window card reads: SILENCE.`, and `play` prints `Pick a track:
[1] Stardust Rag [2] Vacuum Blues -- or anything else to walk away.`. Answering
`1` shows everyone `The jukebox whirs, and the arm drops on Stardust Rag.`, and
`look jukebox` now reads the title on the window card. Then wait, or force beats
with `@tr jukebox/on_tick`: each beat is one room-wide `~ lyric ~` line, and
after the last comes `The record hisses into the run-out groove, and the arm
lifts.`. Answer `9` (or `banana`) to a fresh `play` and the jukebox clunks and
returns your choice unplayed.

## Going further

- **Coin-op:** put the menu behind money with an `ON_PAYMENT` that reads
  [`adata('amount')`](../reference/softcode.md#event-data-namespace) (the
  [fortune teller](013_fortune_teller.md) does exactly this) and banks a
  `paid_<player>` credit that `play` checks and consumes.
- **A whole-club sound system:** `@zone` the venue's rooms together and swap
  `remit(here, ...)` for
  [`act(here, ..., targeting='zone')`](../reference/softcode.md#fn-act), so every
  dance floor hears the same record.
- **Skip button:** a `$skip` command runs `del_attr(me, 'spinning')` and remits
  the needle-scratch, because keeping state in attributes makes every control
  one line.
- **Request the B-side:** store `lines` per mood and pick the list by
  [`tag_value(here, 'zone')`](../reference/softcode.md#fn-tag_value), so the same
  record plays differently in the chapel and the cantina.
