# 214. Simon sequence

> Checklist item 214 — now — *wait()-chained signal flashes, prompt() echo-back, growing pattern*

**What you'll build:** A memory panel. Press START and it flashes a
colour; repeat it and it flashes two; then three — a sequence that grows
by one each round until you either recite the whole thing or fumble and
watch it go dark. Complete it and a vault hatch clicks open.

**Concepts:** a **`wait()` chain that paces the signal** (one flash per
beat, on the server clock, not all at once), `prompt()` to capture the
player's echo-back, and a growing pattern that lives in one attribute
while a cursor walks it — the [self-destruct countdown](056_self_destruct.md)'s
re-arming `wait()` chain turned into a light show.

## How it works

Simon is two timed phases sharing one piece of state:

1. **The show is a `wait()` chain.** `$play simon` doesn't dump the
   sequence in one line — that would defeat the memory test. It sets a
   `flash_i` cursor to 0 and schedules `signal` a beat later. Each
   `signal` run flashes `seq[flash_i]`, bumps the cursor, and — because it
   runs *as the panel* — schedules the next `signal` with `wait(beat,
   'trigger me/signal')`. This is the item-56 countdown pattern: one wait
   pending at a time, each stage re-arming the next. When the cursor
   passes the end of the current sequence, `signal` stops flashing and
   `prompt()`s the player instead.

2. **The echo is a `prompt()`.** `prompt(player, ..., 'judge')` captures
   the player's whole next line into `judge`, which normalizes it (the
   [riddle door](211_riddle_door.md)'s lowercase-and-collapse) and
   compares against the first `level` colours of the pattern.

3. **The pattern grows in place.** `pattern` is the full sequence;
   `level` is how much of it is live this round. A correct echo bumps
   `level` with `incr('level', default=1)` and restarts the show
   (`flash_i = 0`, another `signal` chain); a wrong one clears `busy` and
   the panel dies. Reach `level == len(pattern)` and the hatch opens.

   The `default=1` matters: `level` counts *from one* (round one shows one
   colour), so an unset `level` must read as 1 and bump to 2. A bare
   `incr('level')` would read the unset attribute as 0 and produce 1 —
   silently replaying round one forever. Pass `incr` the same default the
   read would have used, and it stays a one-liner instead of a
   read-add-write.

A `busy` latch keeps two players from driving the panel into each other,
the same guard the [self-destruct](056_self_destruct.md) uses against
double-arming. Because the show runs on `wait()` (in-memory), a reboot
mid-sequence just quietly abandons the round — the correct failure mode
for a light that no one is watching.

## Build it

The chamber and the sealed cache behind the hatch:

```text
@dig The Signal Chamber = signal room, out
signal room
@dig The Sealed Cache = vault hatch, chamber
@desc The Sealed Cache = A dry vault. On a shelf: a data core worth the trouble.
@tag vault hatch = closed
@tag vault hatch = locked
@set vault hatch/locked_msg = The vault hatch is smooth steel. The panel must be satisfied.
```

The panel and its data — the full `pattern` and the beat between flashes:

```text
@create simon panel
drop simon panel
@desc simon panel = A grid of four coloured pads -- red, green, blue, amber -- over a single START key. PLAY SIMON to begin.
@set simon panel/pattern = red green blue amber
@set simon panel/beat = 2
```

`play simon` — latch, reset the round, and kick the first flash a beat
out:

```text
@set simon panel/cmd_play = $play simon: (pemit(enactor, 'The panel is busy with someone else.') if V('busy') else (set_attr(me, 'busy', 1), set_attr(me, 'level', 1), set_attr(me, 'player', '#' + enactor.id), set_attr(me, 'flash_i', 0), remit(loc(me), name(enactor) + ' presses START -- the panel powers up. Watch the lights!'), set_attr(me, 'pending', wait(V('beat', 1), 'trigger me/signal'))))
```

`signal` — flash one pad, advance the cursor, re-arm; or, at the end of
the sequence, hand off to a `prompt()`:

```text
@set simon panel/signal = seq = str(V('pattern')).split()[0:V('level', 1)]; i = V('flash_i', 0); (prompt(get(V('player')), 'Repeat the sequence (e.g. RED GREEN):', 'judge') if i >= len(seq) else (remit(loc(me), 'The panel flashes ' + seq[i].upper() + '.'), incr('flash_i'), set_attr(me, 'pending', wait(V('beat', 1), 'trigger me/signal'))))
```

`judge` — normalize the echo, then buzz, advance-and-reflash, or win:

```text
@set simon panel/judge = want = ' '.join(str(V('pattern')).split()[0:V('level', 1)]); got = ' '.join(trim(arg0).lower().split()); full = len(str(V('pattern')).split()); (set_attr(me, 'busy', 0), remit(loc(me), 'BUZZ -- the pattern was wrong. The panel goes dark.')) if got != want else ((set_attr(me, 'busy', 0), remove_tag(get('vault hatch'), 'closed'), remit(loc(me), 'A rising chime -- the full sequence! The vault hatch clicks open.')) if V('level', 1) >= full else (incr('level', default=1), set_attr(me, 'flash_i', 0), remit(loc(me), 'Correct! The sequence grows longer. Watch again.'), set_attr(me, 'pending', wait(V('beat', 1), 'trigger me/signal'))))
```

## Try it

Press START; a beat later the show begins, one pad at a time:

```text
play simon           -> ...presses START -- the panel powers up. Watch the lights!
                        The panel flashes RED.
                        Repeat the sequence (e.g. RED GREEN):
red                  -> Correct! The sequence grows longer. Watch again.
                        The panel flashes RED.
                        The panel flashes GREEN.
                        Repeat the sequence (e.g. RED GREEN):
red green            -> Correct! ...
```

Recite all four — `red green blue amber` — and the hatch opens:

```text
red green blue amber -> A rising chime -- the full sequence! The vault hatch clicks open.
vault hatch          -> the Sealed Cache
```

One wrong colour ends the run — `green` when it wanted `red` prints
`BUZZ -- the pattern was wrong. The panel goes dark.` and clears the
panel for the next player.

## Going further

- **A real timing window** — after the `prompt()`, arm a
  `wait(window, 'trigger me/timeout')`; `timeout` fails the round if the
  answer never came, and `judge` cancels it on arrival (the
  [self-destruct abort](056_self_destruct.md)'s `cancel_wait`). Now
  hesitation loses.
- **Speed up as it grows** — shrink `beat` as `level` climbs, so the
  show gets faster and harder round on round.
- **Randomize the pattern** — build `pattern` with `rand()` in `cmd_play`
  instead of hard-coding it, so every attempt is fresh (and unguessable
  from a walkthrough).
- **GMCP light cues** — alongside each flash, `oob(player, 'Panel.Flash',
  {'pad': seq[i]})` so a custom client can light real buttons (item 193).
- **Reset** — the `busy` latch and `level` already self-clear; see
  [item 218](218_puzzle_reset.md) for re-sealing the hatch between groups.
