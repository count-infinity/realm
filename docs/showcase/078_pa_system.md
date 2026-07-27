# 078. Station PA system

> Checklist item 78 ([now]): *zone_rooms() remit loop, zone-master $-verbs, act(targeting='zone') contrast*

**What you'll build:** A public-address console. Type `announce <message>`
and every room on the station hears the two-tone chime and your words.
Because the console is the zone's master, the command works from any room
on the station, not only the one holding the microphone.

**Concepts:** [`zone_rooms()`](../reference/softcode.md#fn-zone_rooms) plus
[`remit()`](../reference/softcode.md#fn-remit) as the plain-delivery
broadcast, the zone master making one object's `$`-verbs station-wide,
owner gating on a public console with
[`owner()`](../reference/softcode.md#fn-owner),
[`ansi()`](../reference/softcode.md#fn-ansi) for the house style, and when
to prefer [`act(..., targeting='zone')`](../reference/softcode.md#fn-act)
instead.

## How it works

The finished system is one console object promoted to the master of a
`zone:station` zone that every compartment joins. When the owner types
`announce <message>`, the console renders one chimed line and delivers it
into every station room at once, the announcer's own room included. This
section answers four questions: how one command reaches every room, why
the broadcast uses `remit` rather than a propagated action, where the
owner check belongs, and why the verb needs no `target` guard.

### How one command reaches every station room

Rooms tagged `zone:station` are enumerable, so
[`zone_rooms('station')`](../reference/softcode.md#fn-zone_rooms) returns
the whole set and the broadcast is one loop over it. The reach in the
other direction comes from the **zone master**: the console carries both
the `zone_master` tag and the `zone:station` tag, and the trigger search
consults the zone masters of the room you stand in (the PennMUSH
Zone-Master-Room pattern), so `$announce *` on the console answers from
every station room. The gooseneck mic in Operations is set dressing, since
mechanically the whole station is the console. A room nobody remembered to
`@zone` is off the grid, so its occupants neither hear the PA nor can
trigger it, which is the same zone boundary the
[custom channel](074_custom_channel.md) leans on.

### Why remit rather than a propagated action

[`remit()`](../reference/softcode.md#fn-remit) is delivered text. It cannot
be vetoed, filtered, or overheard by `^listen` triggers, exactly like a
ceiling speaker. Compare the
[self-destruct klaxon](056_self_destruct.md), which reaches the same zone
with [`act(me, ..., targeting='zone')`](../reference/softcode.md#fn-act):
that runs the propagation engine (see
[action phases](../design/action-phases.md)), so wards can block it, a room
can set `lock_reach` to shut out the reach, and behaviors can react with an
`ON_<EVENT>` hook. The rule of thumb is to use `act` when the world should
get a say (alarms, magic, anything resistible) and `remit` when it is just
loudspeakers. A PA is loudspeakers.

### Where the owner check belongs

Station-wide verbs reach everyone, so the first branch of the script tests
who is asking, and the build refuses anyone but the console's owner. It
compares the caller with [`owner(me)`](../reference/softcode.md#fn-owner)
using `is`, an identity check, rather than `==`. A `use` lock or a crew tag
widens that honestly, as the Going further section shows.

### Why the verb needs no target guard

`$announce *` is a `$`-command, so the engine fires it on the console
itself when someone types `announce`, never on the other objects in the
room. That is the case that takes no `target` guard. The guard is only for
a reactive `ON_<EVENT>` hook, which fires on every object in a room and
must screen out business that is not its own (see
[Guard on `target`](../reference/softcode.md#guard-on-target)). This build
has no such hook, only the one `$`-verb, so no guard appears.

## Build it

The station is a three-room chain, Operations to the Mess Hall to the Brig,
and each room is tagged into the `station` zone as it is dug (walking back
from the Brig is two hops, `mess` then `ops`):

```text
@dig Operations = ops, out
ops
@zone here = station
@dig The Mess Hall = mess, ops
mess
@zone here = station
@dig The Brig = brig, mess
brig
@zone here = station
mess
ops
```

The console is created like any object, then promoted to the zone's brain
with `@zone/master`, which tags it both `zone_master` and `zone:station` in
one line:

```text
@create PA console
drop PA console
@desc PA console = A gooseneck microphone over a punchboard of room switches. ANNOUNCE <message> pages the whole station.
@zone/master PA console = station
```

The `announce` verb is a `$`-command on the console. It gates on the owner,
builds one chimed line, loops it into every station room with
[`remit`](../reference/softcode.md#fn-remit), and confirms privately to the
speaker with [`pemit`](../reference/softcode.md#fn-pemit):

```text
@set PA console/cmd_announce = '''
$announce *:
if enactor is not owner(me):  # station-wide reach, so gate on identity first
    pemit(enactor, 'The console wants the station master. It ignores you.')
else:
    line = ansi('yh', 'BONG-bong. ') + escape(arg0) + ansi('c', ' (PA)')  # escape() keeps announcement text out of the markup parser
    for r in zone_rooms('station'):  # every room tagged zone:station, the speaker's own included
        remit(r, line)
    pemit(enactor, 'Your voice rolls out of every speaker on the station.')
'''
```

That is the whole system: three `@zone` tags, one master, one trigger.

## Try it

From Operations, as the owner:

```text
> announce Docking clamps release in five minutes. Clear bay two.
(every station room) BONG-bong. Docking clamps release in five minutes. Clear bay two. (PA)
(you) Your voice rolls out of every speaker on the station.
```

Someone standing in the Brig hears it word for word, and so do you in
Operations, because the announcer's own room is a zone room like any other.
Now walk to the Mess Hall and announce from there: the zone master answers
anywhere on the station, with no console in sight. Finally have a visitor
try it, and the owner gate turns them away:

```text
(Zeke) > announce free credits in ops!
The console wants the station master. It ignores you.
```

## Going further

- **Crew access.** Swap the owner check for `has_tag(enactor, 'crew')` or a
  `use` lock on the console, so the captain deputizes without handing over
  ownership.
- **Deck selection.** A `$announce * on *` pattern filters the loop to
  rooms whose zone tags include `arg1`, giving multi-zone stations per-deck
  paging from one console.
- **The resistible version.** Swap the loop for
  [`act(me, ..., targeting='zone')`](../reference/softcode.md#fn-act) and a
  soundproofed room (an `on_check` ward) genuinely does not hear the PA;
  that is the alarm pattern from the
  [self-destruct sequence](056_self_destruct.md).
- **Scheduled announcements.** A `script_ticker` plus a list of
  `[hour, text]` rows lets shift changes call themselves; the
  [NPC schedule](068_npc_schedule.md) has the clock idiom.
