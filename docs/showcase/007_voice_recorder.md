# 007. Voice recorder

> Checklist item 7 ([now]): *^listen triggers, transcript attrs, $play*

**What you'll build:** A reel-to-reel voice recorder: `record` arms it,
everything said in the room lands on the tape, `stop` closes the take,
and `play` performs the transcript back to whoever's listening.
Espionage in four attributes.

**Concepts:** `^pattern:` **listen triggers** (scripts that fire on
overheard speech), the speaker as `enactor` and the words as `arg0`, a
capped transcript list (the audit-log idiom),
[`escape()`](../reference/softcode.md#fn-escape) for player-authored
text, and where listen triggers do and *don't* reach.

Builds on the [magic 8-ball](005_magic_8ball.md). The
[security camera](054_security_camera.md) builds this same microphone
into a cross-room relay, and adds movement events on top of speech.

## How it works

**`^` is `$` for ears.** An attribute named `listen_*` whose value is
`^pattern: code` fires when speech matching the pattern is heard where
the object stands. `^*` matches everything: the whole line arrives as
`arg0` and the speaker is bound as `enactor`, so one trigger turns any
object into a microphone. Two engine rules keep this sane:

- **Only the room listens.** Listen triggers scan the room's contents
  and the room itself, never anyone's inventory. A recorder in your
  pocket still takes `$`-commands (those *do* search inventory), but it
  overhears nothing. Wiretaps must be *planted*.
- **An object never overhears itself.** The engine skips every listen
  trigger sitting on the speaker, so a deck that speaks its tape aloud
  can never re-record its own playback. (The `listen` lock can further
  gate whose speech an object may hear.)

A listen trigger is a script with an action behind it, so the
[event data namespace](../reference/softcode.md#event-data-namespace) is
bound too: `adata('message')` is the **whole line** that was said,
regardless of what the pattern captured. Under `^*` the two are the same
thing and `arg0` is the plainer read, but the moment the pattern narrows
(`^*payroll*:` captures only the words *around* the keyword, in `arg0`
and `arg1`), `adata('message')` is how you get the sentence back. Record
with the payload, match with the pattern.

**The tape is a list attribute.** Each captured line is appended as
`Speaker: words`, and the list is sliced to its newest 20 with
`(old + [row])[-20:]`, because unbounded lists on hot attributes are the
classic MUD database leak (the [bank](087_bank_accounts.md) caps its
audit logs the same way).
[`escape()`](../reference/softcode.md#fn-escape) neuters any color
markup in what was said: players write the tape's contents, so the tape
stores their words as text, not markup.

**Arming is a flag.** `recording` gates the listen trigger; `record`
sets it (and wipes the previous take), `stop` clears it. Playback
[`remit()`](../reference/softcode.md#fn-remit)s each row, and `remit` is
plain delivered text rather than speech, so playback can't re-trigger
listeners and can't be blocked.

## Build it

The scripts here are `'''` multi-line blocks (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)).

The deck, with a live tape counter on its face: the `[[...]]` block runs
per look and reads the tape length and the REC flag fresh with
[`V`](../reference/softcode.md#fn-v), so the face never goes stale:

```text
@create voice recorder
drop voice recorder
@desc voice recorder = A palm-sized deck of scuffed bakelite with one spinning reel. [[n = len(V('transcript', [])); result = f'The counter reads {n} line' + ('' if n == 1 else 's') + ('; the REC lamp burns red.' if V('recording', 0) else '.')]]
```

Arming: `record` blanks the tape, raises the flag with
[`set_attr`](../reference/softcode.md#fn-set_attr), and clicks loudly
enough for the whole room to hear:

```text
@set voice recorder/cmd_record = '''
$record:
set_attr(me, 'transcript', [])  # a fresh take: arming wipes the old tape
set_attr(me, 'recording', 1)
remit(here, 'The voice recorder clicks; a red REC lamp lights.')
'''
```

The microphone itself: one `^*` trigger hears every line said in the
room, and while the flag is up it stamps the speaker's
[`name`](../reference/softcode.md#fn-name) onto the escaped words and
appends the row:

```text
@set voice recorder/listen_all = '''
^*:
if V('recording', 0):
    row = f'{name(enactor)}: {escape(arg0)}'
    set_attr(me, 'transcript', (V('transcript', []) + [row])[-20:])  # keep only the newest 20 rows
'''
```

Stopping just lowers the flag; the tape keeps its take:

```text
@set voice recorder/cmd_stop = '''
$stop:
set_attr(me, 'recording', 0)
remit(here, 'The REC lamp dims.')
'''
```

Playback: room-wide, row by row, or a private shrug via
[`pemit`](../reference/softcode.md#fn-pemit) if the tape is blank:

```text
@set voice recorder/cmd_play = '''
$play:
rows = V('transcript', [])
if not rows:
    pemit(enactor, 'The tape is blank.')
else:
    remit(here, 'The voice recorder crackles and plays:')
    for r in rows:
        remit(here, '  > ' + r)  # plain delivery: playback can't be overheard or blocked
'''
```

## Try it

With a friend in the room:

```text
record                       -> The voice recorder clicks; a red REC lamp lights.
say The drop is at midnight.
(Kess) say Bring the case and come alone.
stop                         -> The REC lamp dims.
(Kess) say Wait, forget all that.
look voice recorder          -> ... The counter reads 2 lines.
play
```

Playback crackles out both recorded lines, `> Bilda: The drop is at
midnight.` and `> Kess: Bring the case and come alone.`, and *not* the
line said after `stop`. Now pocket it (`get voice recorder`) and try
`record` plus `say`: the commands work from your inventory, but the tape
stays blank, because only a planted recorder hears the room. The spy
move: `drop` it running, walk out, come back and `play`.

## Going further

- **Keyword wiretap:** the pattern is a real pattern, so `^*payroll*:`
  records only sentences containing "payroll". Swap `arg0` for
  `adata('message')` in the body, or the tape keeps the words *around*
  the keyword and drops the keyword itself. A parrot that repeats pirate
  words is the same trigger with `say()` in the body.
- **Timestamped takes:** put [`now()`](../reference/softcode.md#fn-now)
  in the row, as in `f'{now()} {name(enactor)}: ...'`, and the tape
  becomes evidence with times on it.
- **Voice-activated:** drop the `recording` flag entirely and let `^*`
  always record; then the REC lamp in the description is the only tell
  that the room is bugged.
- **Playback as speech:** swap the `remit`s for `say(r)` and the
  recorder audibly *speaks* each line, which other listen-triggered
  gadgets in the room will overhear. (It still never overhears itself.)
