# 009. Music box / wind-up toy

> Checklist item 9 — [now] — *wait() chains, decaying counter attrs*

**What you'll build:** A clockwork music box. Wind the key and it
plinks out its tune one note at a time, each turn of the spring worth
one note — wind it more for a longer song, and listen to it slow into
that final drooping *plink* when the spring runs out.

**Concepts:** **`wait()` chains** — a script that schedules its own
next beat — as softcode's other clock, a decaying counter attribute as
the spring, guarding against double-chains, `pose()` as an object,
tempo and tune as data.

Builds on the [magic 8-ball](005_magic_8ball.md). The
[jukebox](003_jukebox.md) solves the same "timed performance" problem
with a `script_ticker`; build both and you'll know which clock to
reach for.

## How it works

**A wait chain is a relay race.** `wait(seconds, 'trigger
me/play_note')` runs an attribute's script exactly `seconds` from now,
once. If that script *ends by scheduling the same wait again*, you get
a heartbeat-free timer that runs precisely at its own tempo — each
note passes the baton to the next. The chain dies the moment a link
declines to re-arm, which is exactly what a wind-down spring wants.
The trade-off against the jukebox's ticker: `wait()` is in-memory, so
a reboot mid-tune silences the box (harmless here; for a bomb fuse
that mattered — see the [gas bomb](048_gas_bomb.md)).

**The spring is a decaying counter.** `turns` is set by winding and
decremented by every note. Note plays only while `turns > 0`; the last
note re-arms nothing and poses the wind-down instead. Winding *adds*
turns (capped — springs are finite), so you can top up mid-song.

**One chain, ever.** The subtle bug in every wait-chain gadget:
winding twice must not start two relays, or the box plays duplicate
notes forever. The guard is one comparison — only start the chain when
the spring was previously *empty* (`t == 0`). A running box just gets
more turns; a stopped box gets a fresh chain.

**The tune is data.** A list of note descriptions, cycled by a
`cursor` (`i % len(notes)`), and a `tempo` attribute for the seconds
between notes. Retune, rewrite, or slow the box with `@set` — the
scripts never change.

## Build it

The box and its data — tempo in seconds, the tune as a list:

```text
@create music box
drop music box
@set music box/tempo = 5
@set music box/notes = ["a bright, glassy arpeggio", "three descending notes, like rain off a roof", "a tiny waltz figure, slightly out of tune"]
```

The key. Add three turns (capped at nine), and start the relay only if
the spring was slack:

```text
@set music box/cmd_wind = $wind music box: t = V('turns', 0); (set_attr(me, 'turns', min(t + 3, 9)), pose(f'clicks softly as {name(enactor)} winds the brass key.'), (wait(V('tempo', 5), 'trigger me/play_note') if t == 0 else None))
```

The movement — one note per link: pose it, advance the cursor, spend a
turn, and either pass the baton or wind down:

```text
@set music box/play_note = t = V('turns', 0); notes = V('notes', []); i = V('cursor', 0); (pose(f'plays {notes[i % len(notes)]}.'), incr('cursor'), decr('turns'), (wait(V('tempo', 5), 'trigger me/play_note') if t - 1 > 0 else pose('slows... and stops with a final, drooping plink.'))) if t > 0 and notes else None
```

`pose` speaks in the third person as the box, so the room reads
`music box plays a bright, glassy arpeggio.` — ambience, not spam
directed at anyone.

## Try it

```text
wind music box
```

`music box clicks softly as Bilda winds the brass key.` — then every
five seconds a note, three in all, ending with `music box slows...
and stops with a final, drooping plink.` Wind it twice in quick
succession and you get six turns but still one note per beat (the
chain guard at work); keep cranking and the spring caps at nine.
`@examine music box` mid-song shows the machinery honestly: `turns`
counting down, `cursor` counting up.

## Going further

- **Ritardando:** re-arm with `wait(tempo + (9 - t), ...)` and the box
  genuinely slows as the spring loosens — decay you can hear.
- **A jack-in-the-box:** same chain, but when `turns` hits zero,
  `create_obj` the clown and `remit` the shriek — a music box is just
  a fuse with better manners (compare the [gas bomb](048_gas_bomb.md)).
- **Overwinding:** if a wind would pass the cap, snap the spring —
  refuse all future winds until someone with a `repair` skill check
  fixes it.
- **A lullaby field:** each note also `apply_effect`s a drowsiness
  modifier on listeners — gadgets become gameplay the moment a note
  does more than pose.
