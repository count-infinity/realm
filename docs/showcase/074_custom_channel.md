# 074. Custom channel

> Checklist item 74 — [now] — *world-master $chat, subscriber lists, pemit fan-out, history, muting*

**What you'll build:** A station-wide `[pub]` chat channel run entirely
from softcode: `join pub` subscribes you, `+pub <message>` talks from
anywhere on the station, `history pub` replays the last twenty lines,
and `mute pub` / `unmute pub` quiet it without unsubscribing.

**Concepts:** the **world-zone master** as a global command surface,
the reserved `+<channel>` input prefix, subscriber/mute lists as id
attributes, `pemit()` fan-out to targets in other rooms, a capped
history list (the audit-log idiom), and trigger aliases via a shared
`eval_attr()` subroutine.

## How it works

**First, the native check.** REALM has no built-in channel system —
but the dispatcher *reserves the syntax*: any input starting with `+`
is parsed as a channel line (`+pub hi` → command `channel`), and since
no builtin named `channel` ships, the whole raw line falls through to
the softcode `$`-trigger search untouched. So `$+pub *` is a legal,
collision-proof pattern — the engine has pre-cleared the `+` namespace
for exactly this. (Contrast `say` or `who`: builtins dispatch before
`$`-triggers, so those can never be softcoded over.)

**Global reach is the world-zone master.** There is no Master Room
yet; the standing workaround is an object tagged as a **zone master**
for a `zone:world` zone that every public room joins. The trigger
search consults zone masters of the room you stand in, so one object
carries the channel's `$`-commands everywhere the zone reaches — and
*only* there: a room nobody remembered to `@zone` is off the grid.
That boundary is real; say so in your world docs.

**The channel is three lists on the master.** `subs` (subscriber ids),
`quiet` (subscribers who muted), `hist` (the last 20 rendered lines,
sliced `[-20:]` like every hot list in the showcase). Speaking renders
one line, appends it to history, and `pemit()`s it to every subscriber
not in `quiet` — `pemit` delivers to a named target anywhere, no
shared room required, and a subscriber who is offline simply misses
the delivery (that's what `history` is for). `escape()` neuters color
markup in what was said: players write chat lines, so chat treats them
as text, not code.

**Aliases are triggers sharing a subroutine.** The rendering/fan-out
logic lives once in a `speak` attribute; `$+pub *` and the short
`$+p *` are one-line callers via `eval_attr(me, 'speak', arg0)` — the
relay idiom from the [security camera](054_security_camera.md). Add a
third spelling any time with one `@set`.

## Build it

Two station rooms, both joined to the `world` zone:

```text
@dig The Docking Ring = ring, out
ring
@zone here = world
@dig The Observation Deck = deck, ring
deck
@zone here = world
ring
```

The master — created like any object, then promoted to the zone's
brain with `@zone/master`:

```text
@create Comms Nexus
drop Comms Nexus
@desc Comms Nexus = A humming rack of relays. JOIN PUB subscribes; +pub <message> talks; HISTORY PUB replays; MUTE PUB / UNMUTE PUB quiet it.
@zone/master Comms Nexus = world
```

Membership — join refuses a double-subscribe, leave also clears your
mute flag:

```text
@set Comms Nexus/cmd_join = $join pub: subs = get_attr(me, 'subs') or []; (pemit(enactor, 'You are already tuned to [pub].') if enactor.id in subs else (set_attr(me, 'subs', subs + [enactor.id]), pemit(enactor, 'You tune in to [pub]. Talk with +pub <message>.')))
@set Comms Nexus/cmd_leave = $leave pub: set_attr(me, 'subs', [i for i in (get_attr(me, 'subs') or []) if i != enactor.id]); set_attr(me, 'quiet', [i for i in (get_attr(me, 'quiet') or []) if i != enactor.id]); pemit(enactor, 'You drop off [pub].')
```

The voice — one subroutine, two trigger spellings:

```text
@set Comms Nexus/speak = subs = get_attr(me, 'subs') or []; line = '[pub] ' + name(enactor) + ': ' + escape(str(arg0)); (pemit(enactor, 'You are not tuned to [pub]. JOIN PUB first.') if enactor.id not in subs else (set_attr(me, 'hist', ((get_attr(me, 'hist') or []) + [line])[-20:]), [pemit(get('#' + str(i)), line) for i in subs if i not in (get_attr(me, 'quiet') or [])]))
@set Comms Nexus/cmd_pub = $+pub *: eval_attr(me, 'speak', arg0)
@set Comms Nexus/cmd_p = $+p *: eval_attr(me, 'speak', arg0)
```

History and muting:

```text
@set Comms Nexus/cmd_hist = $history pub: rows = get_attr(me, 'hist') or []; pemit(enactor, '[pub] Nothing has been said yet.') if not rows else [pemit(enactor, r) for r in rows]
@set Comms Nexus/cmd_mute = $mute pub: q = get_attr(me, 'quiet') or []; (set_attr(me, 'quiet', q if enactor.id in q else q + [enactor.id]), pemit(enactor, '[pub] muted. HISTORY PUB still works; UNMUTE PUB resumes delivery.'))
@set Comms Nexus/cmd_unmute = $unmute pub: set_attr(me, 'quiet', [i for i in (get_attr(me, 'quiet') or []) if i != enactor.id]); pemit(enactor, '[pub] unmuted.')
```

## Try it

You on the Docking Ring, a friend on the Observation Deck:

```text
join pub                     -> You tune in to [pub]. ...
(Kess, on the deck) join pub
+pub anyone near the airlock?
```

Kess sees `[pub] You: anyone near the airlock?` a room away; so do
you (speakers hear their own line back — that's the delivery, not an
echo). The short alias `+p on my way` lands identically. Then:

```text
(Kess) mute pub
+pub kess? you there?        -> Kess sees nothing
(Kess) history pub           -> ...replays both lines, including the missed one
(Kess) unmute pub
leave pub
+pub hello?                  -> You are not tuned to [pub]. JOIN PUB first.
```

Muting quiets *delivery to you* — including your own lines if you
speak while muted; they still reach everyone else and the history.

## Going further

- **More channels** — the state is just attr names: `subs_ooc`,
  `hist_ooc`, a `$+ooc *` trigger calling a parameterized `speak`.
  One master hosts them all.
- **Speaker-mute** — a second list per player (`block_<id>`) checked
  against `enactor.id` at fan-out: mute a *person*, not the channel.
- **Channel who** — a `$roster pub` that pemits `name(get('#'+i))`
  for each subscriber. (Note it lists *subscribers*, not who is
  online — softcode has no presence query; see
  [message in a bottle](083_message_in_bottle.md) for the honest
  workaround.)
- **Join-gated channels** — a `use` lock on the master, or a tag
  check in `cmd_join`, makes `[crew]` invitation-only.
