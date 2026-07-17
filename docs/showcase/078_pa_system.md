# 078. Station PA system

> Checklist item 78 — [now] — *zone_rooms() remit loop, zone-master $-verbs, act(targeting='zone') contrast*

**What you'll build:** A public-address console: `announce <message>`
and every room on the station hears the two-tone chime and your words
— and because the console is the zone's master, the command works
from any room on the station, not just the one holding the
microphone.

**Concepts:** `zone_rooms()` + `remit()` as the plain-delivery
broadcast, the **zone master** making one object's `$`-verbs
station-wide, owner gating on a public console, `ansi()` for the
house style, and when to prefer `act(..., targeting='zone')` instead.

## How it works

**A zone is the broadcast domain.** Rooms tagged `zone:station` are
enumerable — `zone_rooms('station')` — so the whole PA is one loop:

```
[remit(r, ...) for r in zone_rooms('station')]
```

`remit()` is *delivered text*: it cannot be vetoed, filtered, or
overheard by `^listen` triggers, exactly like a ceiling speaker —
unstoppable and inert. Compare the
[self-destruct klaxon](056_self_destruct.md), which used
`act(me, ..., targeting='zone')`: that runs the propagation engine,
so wards can block it, rooms can lock out `reach`, and behaviors can
react. Rule of thumb: **`act` when the world should get a say
(alarms, magic, anything resistible), `remit` when it's just
loudspeakers.** A PA is loudspeakers.

**The zone master makes the console ambient.** The trigger search
consults zone masters of the room you stand in, so `$announce *` on
the console answers from every station room — the PennMUSH
Zone-Master-Room trick. The gooseneck mic in Operations is set
dressing; mechanically, the whole station is the console.

**Gating is the script's first branch.** Station-wide verbs reach
everyone, so the first test is *who's asking*: the build refuses
anyone but the console's owner. (A `use` lock or a crew tag widens
that honestly — see Going further.)

## Build it

Three compartments, one zone:

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

(The station is a three-room chain — Operations, the Mess Hall, the
Brig — so walking back from the Brig is two hops, `mess` then `ops`.)

The console, promoted to zone master:

```text
@create PA console
drop PA console
@desc PA console = A gooseneck microphone over a punchboard of room switches. ANNOUNCE <message> pages the whole station.
@zone/master PA console = station
```

The verb — gate, chime, loop:

```text
@set PA console/cmd_announce = $announce *: (pemit(enactor, 'The console wants the station master. It ignores you.') if enactor != owner(me) else ([remit(r, ansi('yh', 'BONG-bong. ') + escape(arg0) + ansi('c', ' (PA)')) for r in zone_rooms('station')], pemit(enactor, 'Your voice rolls out of every speaker on the station.')))
```

That's the whole system: three `@zone` tags, one master, one trigger.

## Try it

From Operations, as the owner:

```text
announce Docking clamps release in five minutes. Clear bay two.
   -> (every station room) BONG-bong. Docking clamps release in five minutes. Clear bay two. (PA)
   -> (you) Your voice rolls out of every speaker on the station.
```

Someone standing in the Brig hears it word for word — including you,
in Operations: the announcer's own room is a zone room like any
other. Now walk to the Mess Hall and announce from there: the zone
master answers anywhere on the station, no console in sight. Finally
have a visitor try it:

```text
(Zeke) announce free credits in ops!
   -> The console wants the station master. It ignores you.
```

## Going further

- **Crew access** — swap the owner check for
  `has_tag(enactor, 'crew')` or a `use` lock on the console: the
  captain deputizes without handing over ownership.
- **Deck selection** — `$announce * on *`: filter the loop to rooms
  whose zone tags include `arg1` — multi-zone stations get per-deck
  paging from one console.
- **The resistible version** — swap the loop for
  `act(me, ..., targeting='zone')` and a soundproofed room (an
  `on_check` ward) can genuinely not hear the PA; that's the alarm
  pattern from [item 56](056_self_destruct.md).
- **Scheduled announcements** — a `script_ticker` + a list of
  `[hour, text]` rows: shift changes call themselves
  ([item 68](068_npc_schedule.md) has the clock idiom).
