# 074. Custom channel

> Checklist item 74 ([now]): *world-master $chat, subscriber lists, pemit fan-out, history, muting*

**What you'll build:** A station-wide `[pub]` chat channel run entirely
from softcode: `join pub` subscribes you, `+pub <message>` talks from
anywhere on the station, `history pub` replays the last twenty lines,
and `mute pub` / `unmute pub` quiet it without unsubscribing.

**Concepts:** the world-zone master as a global command surface, the
reserved `+<channel>` input prefix, subscriber and mute lists as id
attributes, [`pemit()`](../reference/softcode.md#fn-pemit) fan-out to
targets in other rooms, a capped history list (the audit-log idiom from
the [voice recorder](007_voice_recorder.md)), and trigger aliases sharing
one [`eval_attr()`](../reference/softcode.md#fn-eval_attr) subroutine, the
relay idiom from the [security camera](054_security_camera.md).

## How it works

The finished channel is a single object that carries every channel
command and holds three lists: who is subscribed, who has muted, and the
recent lines. A subscriber types `+pub hi` from any public room and the
object renders one line and delivers it to every other subscriber
wherever they stand. This section answers four questions: why the `+pub`
syntax is safe to claim, how one object reaches every station room, where
the channel state lives, and how the two spellings of the talk command
share one body.

### Why the `+pub` syntax is free to claim

REALM has no built-in channel system, but the dispatcher reserves the
syntax. Any input starting with `+` is parsed as a channel line, so
`+pub hi` becomes an attempted `channel` command. No builtin named
`channel` ships, so the dispatcher falls through to the softcode
`$`-trigger search, which matches against the whole original input line.
That makes `$+pub *` a legal, collision-proof pattern, because the engine
has pre-cleared the `+` namespace for exactly this. Contrast `say` or
`who`: builtins dispatch before `$`-triggers, so those can never be
softcoded over.

### How one object reaches every station room

There is no Master Room yet, so the standing workaround is a **world-zone
master**: an object promoted to the brain of a `zone:world` zone that
every public room joins. The trigger search consults the zone masters of
the room you stand in, so one object carries the channel's `$`-commands
everywhere the zone reaches, and only there. A room nobody remembered to
`@zone` is off the grid, so its occupants cannot reach the channel at all.
That boundary is real, so say so in your world docs.

### Where the channel state lives

The channel is three lists on the master. `subs` holds subscriber ids,
`quiet` holds the subscribers who muted, and `hist` holds the last twenty
rendered lines, sliced `[-20:]` like every capped list in the showcase.
Speaking renders one line, appends it to `hist`, and
[`pemit()`](../reference/softcode.md#fn-pemit)s it to every subscriber not
in `quiet`. `pemit` delivers to a named target anywhere, so no shared room
is required, and a subscriber who is offline simply misses the delivery,
which is what `history` recovers.
[`escape()`](../reference/softcode.md#fn-escape) neuters color markup in
what was said, because players write chat lines and chat treats them as
text rather than code.

### How two command spellings share one body

The rendering and fan-out logic lives once in a `speak` attribute, and
`$+pub *` and the short `$+p *` are one-line callers via
[`eval_attr(me, 'speak', arg0)`](../reference/softcode.md#fn-eval_attr).
Because `eval_attr` runs as the caller, inside `speak` the executor is
still the master, so [`V()`](../reference/softcode.md#fn-v) reads the
master's own lists. Add a third spelling any time with one more one-line
`@set`.

Every channel command here is a `$`-command that fires on the master
itself when a subscriber types it, so none of them needs a `target`
guard. That guard is only for a reactive `ON_<EVENT>` hook, which fires on
every object in a room and must screen out business that is not its own.
There is no such hook in this build.

## Build it

Two station rooms, both joined to the `world` zone so the master reaches
them:

```text
@dig The Docking Ring = ring, out
ring
@zone here = world
@dig The Observation Deck = deck, ring
deck
@zone here = world
ring
```

The master is created like any object, then promoted to the zone's brain
with `@zone/master`:

```text
@create Comms Nexus
drop Comms Nexus
@desc Comms Nexus = A humming rack of relays. JOIN PUB subscribes; +pub <message> talks; HISTORY PUB replays; MUTE PUB / UNMUTE PUB quiet it.
@zone/master Comms Nexus = world
```

`join` refuses a double-subscribe rather than duplicate your id, and
writes membership with [`set_attr`](../reference/softcode.md#fn-set_attr):

```text
@set Comms Nexus/cmd_join = '''
$join pub:
subs = V('subs') or []
if enactor.id in subs:  # already a member: do not add the id twice
    pemit(enactor, 'You are already tuned to [pub].')
else:
    set_attr(me, 'subs', subs + [enactor.id])  # membership is a list of subscriber ids
    pemit(enactor, 'You tune in to [pub]. Talk with +pub <message>.')
'''
```

`leave` drops you from `subs`, and also clears your mute flag so a later
rejoin starts unmuted:

```text
@set Comms Nexus/cmd_leave = '''
$leave pub:
set_attr(me, 'subs', [i for i in (V('subs') or []) if i != enactor.id])
set_attr(me, 'quiet', [i for i in (V('quiet') or []) if i != enactor.id])  # leaving clears any mute too
pemit(enactor, 'You drop off [pub].')
'''
```

The voice is one subroutine. It refuses a non-subscriber, otherwise
renders the line, appends it to the capped history, and
[`pemit`](../reference/softcode.md#fn-pemit)s it to every subscriber not
muted, resolving each id with [`get`](../reference/softcode.md#fn-get):

```text
@set Comms Nexus/speak = '''
subs = V('subs') or []
if enactor.id not in subs:
    pemit(enactor, 'You are not tuned to [pub]. JOIN PUB first.')
else:
    line = f'[pub] {name(enactor)}: {escape(str(arg0))}'  # escape() keeps chat text out of the markup parser
    set_attr(me, 'hist', ((V('hist') or []) + [line])[-20:])  # keep only the newest 20 lines
    quiet = V('quiet') or []
    for i in subs:
        if i not in quiet:
            pemit(get('#' + str(i)), line)  # pemit reaches a subscriber in any room
'''
```

Both talk spellings are one-line callers of that subroutine, so the two
triggers share every rule the body enforces:

```text
@set Comms Nexus/cmd_pub = $+pub *: eval_attr(me, 'speak', arg0)
@set Comms Nexus/cmd_p = $+p *: eval_attr(me, 'speak', arg0)
```

`history` replays the stored lines, or shrugs privately if none exist yet:

```text
@set Comms Nexus/cmd_hist = '''
$history pub:
rows = V('hist') or []
if not rows:
    pemit(enactor, '[pub] Nothing has been said yet.')
else:
    for r in rows:
        pemit(enactor, r)
'''
```

`mute` adds you to `quiet`, and the add is idempotent so muting twice does
not stack:

```text
@set Comms Nexus/cmd_mute = '''
$mute pub:
q = V('quiet') or []
if enactor.id not in q:  # only add once, so a second mute is harmless
    set_attr(me, 'quiet', q + [enactor.id])
pemit(enactor, '[pub] muted. HISTORY PUB still works; UNMUTE PUB resumes delivery.')
'''
```

`unmute` is the same list with your id removed:

```text
@set Comms Nexus/cmd_unmute = '''
$unmute pub:
set_attr(me, 'quiet', [i for i in (V('quiet') or []) if i != enactor.id])
pemit(enactor, '[pub] unmuted.')
'''
```

## Try it

You on the Docking Ring, a friend on the Observation Deck:

```text
join pub                     -> You tune in to [pub]. ...
(Kess, on the deck) join pub
+pub anyone near the airlock?
```

Kess sees `[pub] You: anyone near the airlock?` a room away, and so do
you, because speakers hear their own line back as the delivery rather than
an echo. The short alias `+p on my way` lands identically. Then:

```text
(Kess) mute pub
+pub kess? you there?        -> Kess sees nothing
(Kess) history pub           -> ...replays both lines, including the missed one
(Kess) unmute pub
leave pub
+pub hello?                  -> You are not tuned to [pub]. JOIN PUB first.
```

Muting quiets delivery to you, including your own lines if you speak while
muted, and those still reach everyone else and the history.

## Going further

- **More channels:** the state is just attribute names, so `subs_ooc`,
  `hist_ooc`, and a `$+ooc *` trigger calling a parameterized `speak` add
  a second channel. One master hosts them all.
- **Speaker-mute:** a second list per player (`block_<id>`) checked
  against `enactor.id` at fan-out mutes a person, not the channel.
- **Channel who:** a `$roster pub` that pemits `name(get('#' + i))` for
  each subscriber. Note that it lists subscribers, not who is online:
  softcode has no presence query, so see
  [message in a bottle](083_message_in_bottle.md) for the honest
  workaround.
- **Join-gated channels:** a `use` lock on the master, or a tag check in
  `cmd_join`, makes `[crew]` invitation-only.
