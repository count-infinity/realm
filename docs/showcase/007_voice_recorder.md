# 007. Voice recorder

> Checklist item 7 — [now] — *^listen triggers, transcript attrs, $play*

**What you'll build:** A reel-to-reel voice recorder: `record` arms it,
everything said in the room lands on the tape, `stop` closes the take,
and `play` performs the transcript back to whoever's listening —
espionage in four attributes.

**Concepts:** `^pattern:` **listen triggers** (scripts that fire on
overheard speech), the speaker as `enactor` and the words as `arg0`, a
capped transcript list (the audit-log idiom), `escape()` for
player-authored text, where listen triggers do and *don't* reach.

Builds on the [magic 8-ball](005_magic_8ball.md). The
[security camera](054_security_camera.md) is the visual cousin —
events instead of speech.

## How it works

**`^` is `$` for ears.** An attribute named `listen_*` whose value is
`^pattern: code` fires when speech matching the pattern is heard where
the object stands. `^*` matches everything, the whole line arriving as
`arg0` and the speaker as `enactor` — so one trigger turns any object
into a microphone. Two engine rules keep this sane:

- **Only the room listens.** Listen triggers scan the room's contents
  and the room itself — never anyone's inventory. A recorder in your
  pocket still takes `$`-commands (those *do* search inventory), but it
  overhears nothing. Wiretaps must be *planted*.
- **An object never overhears itself.** The engine skips a trigger
  whose owner is the speaker, so a recorder that plays back a tape
  containing "record" can't loop into recording its own voice. (The
  `listen` lock can further gate whose speech an object may hear.)

A listen trigger is a script with an action behind it, so the event
namespace is bound too: `adata('message')` is the **whole line** that
was said, regardless of what the pattern captured. Under `^*` the two
are the same thing and `arg0` is the plainer read — but the moment the
pattern narrows (`^*payroll*:` captures only the words *around* the
keyword, in `arg0` and `arg1`), `adata('message')` is how you get the
sentence back. Record with the payload, match with the pattern.

**The tape is a list attribute.** Each captured line is appended as
`Speaker: words`, and the list is sliced to its newest 20 —
`(old + [row])[-20:]` — because unbounded lists on hot attributes are
the classic MUD database leak (the [bank](087_bank_accounts.md) caps
its audit logs the same way). `escape()` neuters any color markup in
what was said: players write the tape's contents, so the tape treats
them as text, not code.

**Arming is a flag.** `recording` gates the listen trigger; `record`
sets it (and wipes the previous take), `stop` clears it. Playback
`remit()`s each row — plain delivered text, so it can't re-trigger
listeners and can't be blocked.

## Build it

The deck, with a live tape counter on its face:

```text
@create voice recorder
drop voice recorder
@desc voice recorder = A palm-sized deck of scuffed bakelite with one spinning reel. [[n = len(V('transcript', [])); result = f'The counter reads {n} line' + ('' if n == 1 else 's') + ('; the REC lamp burns red.' if V('recording', 0) else '.')]]
```

Transport controls — arm (and blank the tape), the microphone itself,
and stop:

```text
@set voice recorder/cmd_record = $record: (set_attr(me, 'recording', 1), set_attr(me, 'transcript', []), remit(here, 'The voice recorder clicks; a red REC lamp lights.'))
@set voice recorder/listen_all = ^*: set_attr(me, 'transcript', (V('transcript', []) + [f'{name(enactor)}: {escape(arg0)}'])[-20:]) if V('recording', 0) else None
@set voice recorder/cmd_stop = $stop: (set_attr(me, 'recording', 0), remit(here, 'The REC lamp dims.'))
```

Playback — room-wide, row by row, or a private shrug if the tape is
blank:

```text
@set voice recorder/cmd_play = $play: rows = V('transcript', []); pemit(enactor, 'The tape is blank.') if not rows else remit(here, 'The voice recorder crackles and plays:'); [remit(here, '  > ' + r) for r in rows]
```

## Try it

With a friend in the room:

```text
record                       -> The voice recorder clicks; a red REC lamp lights.
say The drop is at midnight.
(Kess) say Bring the case and come alone.
stop                         -> The REC lamp dims.
(Kess) say Wait, forget all that.
look voice recorder          -> The counter reads 2 lines; ...
play
```

Playback crackles out both recorded lines — `> Bilda: The drop is at
midnight.` and `> Kess: Bring the case and come alone.` — and *not*
the line said after `stop`. Now pocket it (`get voice recorder`) and
try `record` + `say`: the commands work from your inventory, but the
tape stays blank — only a planted recorder hears the room. The spy
move: `drop` it running, walk out, come back and `play`.

## Going further

- **Keyword wiretap:** the pattern is a real pattern — `^*payroll*:`
  records only sentences containing "payroll". Swap `arg0` for
  `adata('message')` in the body or the tape keeps the words *around*
  the keyword and drops the keyword itself. A parrot that repeats
  pirate words is the same trigger with `say()` in the body.
- **Timestamped takes:** append `str(now()) + ' ' + name(enactor) +
  ...` and the tape becomes evidence with times on it.
- **Voice-activated:** drop the `recording` flag entirely and let
  `^*` always record — then the REC lamp in the description is the
  only tell that the room is bugged.
- **Playback as speech:** swap the `remit`s for `say(r)` and the
  recorder audibly *speaks* each line — which other listen-triggered
  gadgets in the room will overhear. (It still never overhears
  itself.)
