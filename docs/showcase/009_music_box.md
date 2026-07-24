# 009. Music box / wind-up toy

> Checklist item 9 ([now]): *wait() chains, decaying counter attrs*

**What you'll build:** A clockwork music box. Wind the key and it plinks
out its tune one note at a time, each turn of the spring worth one note.
Wind it more for a longer song, and listen for the final drooping
*plink* when the spring runs out.

**Concepts:** **[`wait()`](../reference/softcode.md#fn-wait) chains** (a
script that schedules its own next beat) as softcode's other clock, a
decaying counter attribute as the spring, guarding against double
chains, `pose()` as an object, tempo and tune as data.

Builds on the [magic 8-ball](005_magic_8ball.md). The
[jukebox](003_jukebox.md) solves the same "timed performance" problem
with a `script_ticker`; build both and you'll know which clock to reach
for.

## How it works

**A wait chain is a relay race.**
[`wait(seconds, 'trigger me/play_note')`](../reference/softcode.md#fn-wait)
runs an attribute's script exactly `seconds` from now, once, on its own
timer rather than the world heartbeat. If that script *ends by
scheduling the same wait again*, you get a timer that runs precisely at
its own tempo, each note passing the baton to the next. The chain dies
the moment a link declines to re-arm, which is exactly what a wind-down
spring wants. The trade-off against the jukebox's ticker: `wait()` is
in-memory, so a reboot mid-tune silences the box. That is harmless here;
where it matters, use [`expire()`](../reference/softcode.md#fn-expire),
the persistent timer, and the [gas bomb](048_gas_bomb.md) shows the two
side by side (a `wait()` fuse, an `expire()` dissipation).

**The spring is a decaying counter.** `turns` is set by winding and
decremented by every note. A note plays only while `turns > 0`; the last
note re-arms nothing and poses the wind-down instead. Winding *adds*
turns (capped, because springs are finite), so you can top up mid-song.

**One chain, ever.** The subtle bug in every wait-chain gadget: winding
twice must not start two relays, or the box plays duplicate notes
forever. The guard is one comparison, made *before* the wind adds turns:
only start the chain when the spring was previously empty (`t == 0`). A
running box just gets more turns; a stopped box gets a fresh chain.

**The tune is data.** A list of note descriptions, cycled by a `cursor`
(`i % len(notes)` wraps around, so a long song repeats the tune), and a
`tempo` attribute for the seconds between notes. Retune, rewrite, or
slow the box with `@set`; the scripts never change.

## Build it

The scripts here are `'''` multi-line blocks (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)).

The box and its data, tempo in seconds and the tune as a list:

```text
@create music box
drop music box
@set music box/tempo = 5
@set music box/notes = ["a bright, glassy arpeggio", "three descending notes, like rain off a roof", "a tiny waltz figure, slightly out of tune"]
```

The key. Read the spring *first*, add three turns (capped at nine), and
start the relay only if the spring was slack when you looked:

```text
@set music box/cmd_wind = '''
$wind music box:
t = V('turns', 0)  # read BEFORE adding: the chain guard needs the old value
set_attr(me, 'turns', min(t + 3, 9))
pose(f'clicks softly as {name(enactor)} winds the brass key.')
if t == 0:  # only a slack spring starts a chain; a running box just gets more turns
    wait(V('tempo', 5), 'trigger me/play_note')
'''
```

The movement, one note per link: pose the note, advance the cursor,
spend a turn, and either pass the baton or wind down:

```text
@set music box/play_note = '''
t = V('turns', 0)
notes = V('notes', [])
if t > 0 and notes:
    i = V('cursor', 0)
    pose(f'plays {notes[i % len(notes)]}.')
    incr('cursor')
    decr('turns')
    if t > 1:
        wait(V('tempo', 5), 'trigger me/play_note')  # pass the baton
    else:
        pose('slows... and stops with a final, drooping plink.')
'''
```

`pose` speaks in the third person as the box, so the room reads
`music box plays a bright, glassy arpeggio.`, which is ambience, not
spam directed at anyone.

## Try it

```text
wind music box
```

You'll see `music box clicks softly as Bilda winds the brass key.`, then
a note every five seconds, three in all:

```text
music box plays a bright, glassy arpeggio.
music box plays three descending notes, like rain off a roof.
music box plays a tiny waltz figure, slightly out of tune.
music box slows... and stops with a final, drooping plink.
```

Wind it twice in quick succession and you get six turns but still one
note per beat (the chain guard at work); keep cranking and the spring
caps at nine. `@examine music box` mid-song shows the machinery
honestly: `turns` counting down, `cursor` counting up.

## Going further

- **Ritardando:** re-arm with `wait(tempo + (9 - t), ...)` and the box
  genuinely slows as the spring loosens, decay you can hear.
- **A jack-in-the-box:** same chain, but when `turns` hits zero,
  [`create_obj`](../reference/softcode.md#fn-create_obj) the clown and
  [`remit`](../reference/softcode.md#fn-remit) the shriek. A music box is
  just a fuse with better manners (compare the
  [gas bomb](048_gas_bomb.md)).
- **Overwinding:** if a wind would pass the cap, snap the spring and
  refuse all future winds until someone with a `repair` skill check
  fixes it.
- **A lullaby field:** each note also
  [`apply_effect`](../reference/softcode.md#fn-apply_effect)s a
  drowsiness modifier on listeners; gadgets become gameplay the moment a
  note does more than pose.
