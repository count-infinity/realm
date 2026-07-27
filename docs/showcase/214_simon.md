# 214. Simon sequence

> Checklist item 214 ([now]): *wait()-chained signal flashes, prompt() echo-back, growing pattern*

**What you'll build:** A memory panel. Press START and it flashes one colour;
repeat that and it flashes two, then three, a sequence growing by one colour
each round until you either recite the whole thing or fumble and watch the
panel go dark. Finish it and a vault hatch clicks open.

**Concepts:** a [`wait()`](../reference/softcode.md#fn-wait) chain that paces
the show at one flash per beat on the server clock instead of dumping it all at
once, [`prompt()`](../reference/softcode.md#fn-prompt) to capture the player's
echo back, and a pattern that lives in one attribute while a cursor walks it.
It is the [self-destruct countdown](056_self_destruct.md)'s re-arming `wait()`
chain turned into a light show.

## How it works

The finished panel runs two phases over one small pile of attributes. In the
show, it flashes the first `level` colours of its `pattern` a beat apart; in
the echo, the player types those colours back and the panel judges the line. A
correct echo raises `level` by one and starts the show again, a wrong one ends
the run, and a complete one opens the hatch. This section answers how the show
paces itself, how the answer finds its way back to the panel, how the pattern
grows, and what keeps two players out of each other's round.

### How the panel flashes one pad at a time

Printing the whole sequence in a single line would spoil the memory test, so
the `$play simon` [command trigger](../reference/softcode.md#triggers-attributes-on-objects)
announces the START and nothing else. It sets a `flash_i` cursor to 0 and
schedules the panel's `signal` attribute a beat later with
[`wait(beat, 'trigger me/signal')`](../reference/softcode.md#fn-wait).

Each `signal` run flashes `seq[flash_i]` to the room with
[`remit`](../reference/softcode.md#fn-remit), bumps the cursor with
[`incr`](../reference/softcode.md#fn-incr), and schedules the *next* `signal`
itself, so exactly one wait is ever in flight and the show paces itself without
a ticker. That scheduled command runs the plain `signal` attribute as the panel
(the executor of a wait is the object that scheduled it), which is why the
script may write the panel's own attributes; it is not a `$`-command, so no
player input is involved. When the cursor reaches the end of the live part of
the pattern, `signal` stops flashing and hands over to `prompt()` instead.

### How the answer gets back to the panel

The show runs later, on its own timer, so the panel has to remember who pressed
START. `cmd_play` writes `'#' + enactor.id` into a `player` attribute and
`signal` turns that back into an object with
[`get`](../reference/softcode.md#fn-get), which is an exact id lookup rather
than a name match. [`prompt(who, text, 'judge')`](../reference/softcode.md#fn-prompt)
then captures that player's whole next line and runs the `judge` attribute with
the line bound as `arg0`. The callback runs as the panel, so `judge` can read
`pattern` and clear `busy` on its own object.

The two audiences differ on purpose: the flashes go out with `remit`, so
everyone standing in the chamber watches the light show, while the prompt and
its question reach only the player who pressed START.

`judge` normalizes the answer the way the [riddle door](211_riddle_door.md)
begins, with [`trim`](../reference/softcode.md#fn-trim), `.lower()`, and a
`split()`/`join()` round trip, so `  Red   GREEN ` compares equal to
`red green`. Simon wants exact colours in exact order, so it stops there
instead of going on to strip punctuation and articles as the sphinx does.

None of these three scripts is a reactive `ON_<EVENT>` hook, so none of them
needs the `if target is me:`
[guard](../reference/softcode.md#guard-on-target) that a room-wide
[lifecycle hook](../reference/softcode.md#lifecycle-hooks) requires. A
`$`-command fires only on the object whose attribute matched, a wait fires only
on the object that scheduled it, and a prompt callback fires only on the object
that asked the question.

### How the pattern grows

`pattern` holds the full sequence as a plain space-separated string and `level`
says how much of it is live this round, so the slice
`str(V('pattern')).split()[0:V('level', 1)]` gives this round's colours to both
the show and the judge. A correct echo that is shorter than the full pattern
bumps `level` with `incr('level', default=1)`, resets `flash_i` to 0, and
starts another chain; an echo that matches the whole pattern pulls the `closed`
tag off the hatch with [`remove_tag`](../reference/softcode.md#fn-remove_tag).

The `default=1` is the same default every *read* of `level` uses
([`V('level', 1)`](../reference/softcode.md#fn-v)), which is the rule to follow
with
[`incr`](../reference/softcode.md#fn-incr): pass it the default the read would
have used, and the counter stays right whichever runs first. Here `cmd_play`
writes `level = 1` before any judging happens, so the first bump lands on 2
regardless, but matching the read costs nothing and survives a rearrangement of
the script order.

### What keeps two players out of one round

`busy` is a plain latch. `cmd_play` refuses while it is set, and both endings,
the buzz and the chime, clear it, which is the refuse-while-running guard the
[self-destruct](056_self_destruct.md) applies when it checks for a pending
countdown before arming a second one. A second player pressing START mid-show
gets `The panel is busy with someone else.` and the round in progress is
undisturbed.

`wait()` lives in memory, so a reboot part-way through a show drops the flash
that was pending. The attributes persist, `busy` among them, so an interrupted
panel comes back latched and answers everyone with that same busy line until
someone clears it with `@set simon panel/busy = 0`. That is precisely the stuck
state [item 218](218_puzzle_reset.md) turns into a proper restore routine, and
it is worth wiring before players meet the puzzle. Where a timer has to outlive
a reboot, [`expire()`](../reference/softcode.md#fn-expire) is the persistent
one; a light show is happy to be forgotten.

## Build it

Dig the chamber and the sealed cache behind it. The hatch carries two tags that
do different jobs: `closed` stops movement, and `locked` stops `open` and
prints `locked_msg` instead, so the panel is the only thing that can let anyone
through:

```text
@dig The Signal Chamber = signal room, out
signal room
@dig The Sealed Cache = vault hatch, chamber
@desc The Sealed Cache = A dry vault. On a shelf: a data core worth the trouble.
@tag vault hatch = closed
@tag vault hatch = locked
@set vault hatch/locked_msg = The vault hatch is smooth steel. The panel must be satisfied.
```

Now the panel and its two data attributes, the full pattern and the seconds
between flashes. Both are plain values rather than code, so both stay
single-line `@set`s:

```text
@create simon panel
drop simon panel
@desc simon panel = A grid of four coloured pads (red, green, blue, amber) over a single START key. PLAY SIMON to begin.
@set simon panel/pattern = red green blue amber
@set simon panel/beat = 2
```

Each script below is a `'''` block: end the `@set` line with `'''`, write the
body as ordinary indented softcode, and close with a line of just `'''` (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)).

`play simon` is the one thing a player types at the panel. It turns a busy
panel away with a private [`pemit`](../reference/softcode.md#fn-pemit);
otherwise it [`set_attr`](../reference/softcode.md#fn-set_attr)s the round into
place (the `busy` latch, one live colour, the cursor at the start, and who is
playing), announces the START to the room, and lights the first flash a beat
out:

```text
@set simon panel/cmd_play = '''
$play simon:
if V('busy'):
    pemit(enactor, 'The panel is busy with someone else.')
else:
    set_attr(me, 'busy', 1)
    set_attr(me, 'level', 1)
    set_attr(me, 'flash_i', 0)
    set_attr(me, 'player', '#' + enactor.id)  # the show runs later and must know who to ask
    remit(loc(me), f'{name(enactor)} presses START. The panel powers up: watch the lights!')
    wait(V('beat', 1), 'trigger me/signal')
'''
```

`signal` is the show, and it runs once per flash. It slices this round's
colours out of the pattern, and then either flashes the pad under the cursor,
advances, and schedules its own next run, or, once the cursor has passed the
last live colour, asks the player to repeat what they saw:

```text
@set simon panel/signal = '''
seq = str(V('pattern')).split()[0:V('level', 1)]
i = V('flash_i', 0)
if i >= len(seq):
    prompt(get(V('player')), 'Repeat the sequence (e.g. RED GREEN):', 'judge')
else:
    remit(loc(me), f'The panel flashes {seq[i].upper()}.')
    incr('flash_i')
    wait(V('beat', 1), 'trigger me/signal')  # schedule the next flash: one wait in flight at a time
'''
```

`judge` receives the echoed line and has three answers to give. A mismatch
buzzes and releases the panel, a match on the whole pattern opens the hatch,
and a match on part of it grows the round by one colour and restarts the show:

```text
@set simon panel/judge = '''
pads = str(V('pattern')).split()
want = ' '.join(pads[0:V('level', 1)])
got = ' '.join(trim(arg0).lower().split())  # arg0 is the whole line the player typed
if got != want:
    set_attr(me, 'busy', 0)
    remit(loc(me), 'BUZZ. The pattern was wrong, and the panel goes dark.')
elif V('level', 1) >= len(pads):
    set_attr(me, 'busy', 0)
    remove_tag(get('vault hatch'), 'closed')
    remit(loc(me), 'A rising chime: the full sequence! The vault hatch clicks open.')
else:
    incr('level', default=1)
    set_attr(me, 'flash_i', 0)
    remit(loc(me), 'Correct! The sequence grows longer. Watch again.')
    wait(V('beat', 1), 'trigger me/signal')
'''
```

## Try it

Try the hatch by hand first, because once a prompt is pending every line you
type is your answer. Then press START, and a beat later the show begins one pad
at a time:

```text
> open vault hatch
The vault hatch is smooth steel. The panel must be satisfied.

> play simon
Zeke presses START. The panel powers up: watch the lights!
The panel flashes RED.
Repeat the sequence (e.g. RED GREEN):

> red
Correct! The sequence grows longer. Watch again.
The panel flashes RED.
The panel flashes GREEN.
Repeat the sequence (e.g. RED GREEN):

> red green
Correct! The sequence grows longer. Watch again.
The panel flashes RED.
The panel flashes GREEN.
The panel flashes BLUE.
Repeat the sequence (e.g. RED GREEN):
```

Echo all four colours and the hatch gives way, at which point the exit walks
like any other:

```text
> red green blue amber
A rising chime: the full sequence! The vault hatch clicks open.

> vault hatch
You leave vault hatch.

The Sealed Cache
----------------
A dry vault. On a shelf: a data core worth the trouble.

Exits: chamber
```

Two things are worth confirming deliberately. Answer `green` on the first round
and the panel prints `BUZZ. The pattern was wrong, and the panel goes dark.`,
after which `play simon` starts a fresh round from one colour, because the buzz
cleared `busy` and the next START rewrites `level`. And while a round is
running, a second player who types `play simon` is told
`The panel is busy with someone else.`, though they still see every flash,
since the flashes are `remit`ted to the whole room.

## Going further

- **A real timing window.** After the `prompt()`, arm
  `set_attr(me, 'timer', wait(V('window', 15), 'trigger me/timeout'))`, and
  have `timeout` clear `busy` and announce a failure. `judge` then opens with
  [`cancel_wait(V('timer'))`](../reference/softcode.md#fn-cancel_wait), the
  same defuse the [self-destruct's abort](056_self_destruct.md) performs, so an
  answer that arrives in time calls the failure off and hesitation loses.
- **Speed up as it grows.** Read the beat as
  `max(1, V('beat', 1) - V('level', 1) + 1)` instead of `V('beat', 1)`, so the
  show quickens as the sequence lengthens and the round gets harder in two ways
  at once.
- **Randomize the pattern.** Build the pattern in `cmd_play` rather than
  hard-coding it, with `pads = ['red', 'green', 'blue', 'amber']` and
  `set_attr(me, 'pattern', ' '.join([pads[rand(0, 3)] for n in range(4)]))`.
  [`rand`](../reference/softcode.md#fn-rand) includes both endpoints, so
  `rand(0, 3)` covers exactly the four indexes, and no walkthrough can spoil
  the answer.
- **GMCP light cues.** In `signal`, alongside the flash, send
  [`oob(get(V('player')), 'Panel.Flash', {'pad': seq[i]})`](../reference/softcode.md#fn-oob)
  so a scripting client can light real buttons rather than print a line; see
  [item 193](193_gmcp_oob.md).
- **Reset between groups.** The hatch stays open once won, and an interrupted
  round leaves `busy` set, so give the panel a `restore` attribute that
  re-tags the hatch `closed` and zeroes `busy`, `level`, and `flash_i`. That is
  the routine [item 218](218_puzzle_reset.md) builds and then wires to a
  `$reset` command and an `ON_RESET` hook.
