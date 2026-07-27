# 181. Announcement system

> Checklist item 181 ([now]): *server-wide pemit fan-out, per-player opt-out, persistent history, contrast with zone remit (078) and act countdown (056)*

**What you'll build:** an `Announcer` mic that pushes a formatted notice to
**every character on the grid** with `announce <message>`, keeps a history
players replay with `news`, and honors a per-player opt-out
(`mute news` / `unmute news`).

**Concepts:** server-wide fan-out with [`pemit()`](../reference/softcode.md#fn-pemit)
per player (so the opt-out filters it, which is why this is not a
[`remit()`](../reference/softcode.md#fn-remit) loop), a persistent **history**
attribute, tag-based **opt-out**, staff gating, and the deliberate contrast with
the two broadcast idioms you have already met.

## How it works

The finished shape is one admin-owned mic sitting on the world zone. A staffer
types `announce ...`, the mic records the notice and then loops over every
player on the grid, sending each one the line unless they have opted out. Two
more verbs read back and control that flow: `news` replays the stored history,
and `mute news` / `unmute news` toggle a per-player tag. This section answers
three questions: why the fan-out loops players instead of rooms, why
"server-wide" really means everyone, and where the staff gate and history live.

### Why loop players with `pemit`, not rooms with `remit`

The [station PA](078_pa_system.md) uses [`remit()`](../reference/softcode.md#fn-remit)
over [`zone_rooms()`](../reference/softcode.md#fn-zone_rooms): fast, unstoppable,
and unfilterable, because everyone standing in the room hears it with no
exceptions. That fits a ceiling speaker, but it works against a server-wide
notice with an opt-out, since `remit` delivers to a whole room and offers no way
to skip one listener. So the announcer loops **players**, not rooms, with
[`search_world(tag='player')`](../reference/softcode.md#fn-search_world), and
[`pemit`](../reference/softcode.md#fn-pemit)s each one individually, skipping
anybody tagged `no_announce`. The cost is one message per player rather than one
per room; the payoff is per-person control.

For a *resistible* broadcast, one that a soundproof room or a ward may veto, you
would reach for [`act(..., targeting='zone')`](../reference/softcode.md#fn-act),
the alarm idiom from the [self-destruct sequence](056_self_destruct.md). An
announcement is opt-out-able rather than resistible: the listener chooses to skip
it, but no room or ward blocks it on their behalf.

### Why server-wide reaches every player, wherever they stand

Because delivery keys off each player object rather than a location, a character
off in Limbo, nowhere near the booth and in no zone, still hears the notice.
That is the difference from the zone-scoped PA: the PA reaches a *place*, while
the announcer reaches *people*. The engine itself loops the same
`tag='player'` set for its own server-wide work, so the fan-out matches how the
grid already thinks about "all players".

### Where the gate, the history, and the opt-out live

Broadcasting is owner-gated by a tag check,
[`has_tag(enactor, 'admin')`](../reference/softcode.md#fn-has_tag); the mic is
admin-owned, so it also holds the authority to tag players who opt out. Widen
the gate to a `staff` tag or a `use` lock if more than admins should hold the
mic.

Every notice is appended to the `history` attribute (trimmed to the last 30)
*before* delivery, so `news` replays what a muted or just-logged-in player
missed. Muting suppresses *live* delivery only by adding the `no_announce` tag
with [`add_tag`](../reference/softcode.md#fn-add_tag); the history always keeps
the full record, and `unmute news` removes the tag again with
[`remove_tag`](../reference/softcode.md#fn-remove_tag).

All four verbs are `$`-commands, dispatched by the pattern the player types, so
they take no [`target` guard](../reference/softcode.md#guard-on-target): that
guard is for reactive `ON_<EVENT>` hooks that fire on every object in a room, and
this mic has none.

## Build it

The mic lives in a booth crowned onto the world zone so its `$`-commands are
reachable from anywhere. Dig the booth, tag the room `world`, create the mic,
drop it, describe it, and make it the world-zone master:

```text
@dig The Broadcast Booth = booth, out
booth
@zone here = world
@create Announcer
drop Announcer
@desc Announcer = A brass microphone wired to every character on the grid.
@zone/master Announcer = world
```

The broadcast verb gates on the `admin` tag, records the line into `history`
before sending, then fans out to every player who has not opted out:

```text
@set Announcer/cmd_announce = $announce *: '''
if not has_tag(enactor, 'admin'):
    pemit(enactor, 'Only staff may broadcast.')
else:
    # record before delivery, so a muted or absent player still finds it in news
    line = f'{escape(arg0)}  --{name(enactor)}'
    set_attr(me, 'history', ((V('history') or []) + [line])[-30:])
    for p in search_world(tag='player'):
        if not has_tag(p, 'no_announce'):
            pemit(p, ansi('yh', '[NOTICE] ') + escape(arg0))
    pemit(enactor, 'Broadcast sent to all listening players.')
'''
```

The replay verb reads the stored history and numbers the last ten notices:

```text
@set Announcer/cmd_news = $news: '''
h = V('history') or []
if not h:
    pemit(enactor, 'No notices on file.')
else:
    for i, ln in enumerate(h[-10:]):
        pemit(enactor, f'{i+1}. {ln}')
'''
```

The opt-out verbs tag and untag the caller, so the fan-out loop skips or resumes
them on the next broadcast:

```text
@set Announcer/cmd_mute = $mute news: '''
add_tag(enactor, 'no_announce')
pemit(enactor, 'You opt out of live notices. NEWS still shows history; UNMUTE NEWS resumes delivery.')
'''
@set Announcer/cmd_unmute = $unmute news: '''
remove_tag(enactor, 'no_announce')
pemit(enactor, 'Live notices resumed.')
'''
```

## Try it

A staffer broadcasts; a character in the booth and one far away in Limbo both
hear it, and the staffer sees a private confirmation. The `[NOTICE]` prefix
arrives as bright-yellow markup:

```text
announce Reactor drill at 0300. This is only a drill.
   -> |Y[NOTICE] |nReactor drill at 0300. This is only a drill.
   -> Broadcast sent to all listening players.
   (Kess in the booth, and Zeke in Limbo)
   -> |Y[NOTICE] |nReactor drill at 0300. This is only a drill.
```

Opting out silences the *live* line but keeps the record:

```text
mute news
   -> You opt out of live notices. NEWS still shows history; UNMUTE NEWS resumes delivery.
(after the next announce, no live line arrives)
news
   -> 1. Reactor drill at 0300. This is only a drill.  --Bob
   -> 2. Second notice, please ignore.  --Bob
```

`unmute news` resumes delivery, and its next `announce` reaches Kess again. A
non-staff character who tries to broadcast is turned away:

```text
announce free credits!
   -> Only staff may broadcast.
```

## Going further

- **Priorities:** a `$alert <message>` variant in red that *ignores*
  `no_announce` for genuine emergencies, since opt-out is a courtesy rather than
  a mute on the fire alarm.
- **Timed notices:** a `script_ticker` walking a list of scheduled
  `[hour, text]` rows announces shift changes on their own, the
  [NPC schedule](068_npc_schedule.md) clock idiom.
- **Countdowns:** for a dramatic, abortable sequence (launch in 10, 9, ...),
  chain [`wait()`](../reference/softcode.md#fn-wait)s and let `$abort`
  [`cancel_wait()`](../reference/softcode.md#fn-cancel_wait), which is the
  [self-destruct](056_self_destruct.md) klaxon rather than a one-shot notice.
- **Channels versus notices:** for a *conversation* instead of a broadcast,
  reach for the subscriber-list [custom channel](074_custom_channel.md); an
  announcement is one-way by design.
```
