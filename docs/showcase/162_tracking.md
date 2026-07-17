# 162. Tracking

> Checklist item 162 — now — *ON_LEAVE footprint stamps, skill_check to read them, expire() decay*

**What you'll build:** A wilderness where passers-by leave a trail. Every
time someone crosses a room they stamp footprints into it; a skilled
tracker can `track` to read who came through and how long ago, while the
unskilled see only meaningless scuffs. The tracks fade on their own.

**Concepts:** a **zone master hearing `ON_LEAVE`** across every room it
owns ([tutorial 071](071_guard_response.md)); **footprints as owned
objects** stamped with who and when; `skill_check` gating what a tracker
can read; and `expire()` as **evidence decay** ([tutorial 083](083_message_in_bottle.md)).

## How it works

**One master hears the whole zone.** Tag your wilds into a `wilds` zone
and crown a `Trailcraft` master. Every move fires an `ON_LEAVE` on the
room being left — and a zone master hears its member rooms' events, so
`Trailcraft` witnesses *every* departure in the wilds with one hook. It
drops a footprint object into the room the walker just left, stamped with
their id, their name, and `now()`. (It stamps only players, so the world
doesn't carpet itself in critter prints.)

**Footprints are objects, so they're readable and they decay.** A print
is an ordinary owned object tagged `footprint`. `track` reads the prints
in your room — but only a passed `skill_check(enactor, 'tracking')`
turns scuffs into information; fail and the ground tells you nothing.
And because a print is an object, `expire(fp, 300)` gives it a lifetime:
the world tick destroys it when it lapses, so a cold trail literally
disappears — no sweeper script, evidence decay for free.

**Why a master and not the room.** You could hang `ON_LEAVE` on every
room, but the master does it once for the whole zone, and every new room
you tag in starts leaving tracks automatically — membership is the tag.

## Build it

Two wilds rooms in a zone, and the tracking master:

```text
@dig The Clearing = clearing, out
clearing
@zone here = wilds
@dig The Thicket = thicket, back
thicket
@zone here = wilds
back
@create Trailcraft
@zone/master Trailcraft = wilds
drop Trailcraft
```

The stamp — on every player's departure, mint a dated footprint that
fades in five minutes:

```text
@set Trailcraft/on_leave = (None if not has_tag(enactor,'player') else (lambda fp: (set_attr(fp,'quarry','#'+enactor.id), set_attr(fp,'quarry_name', name(enactor)), set_attr(fp,'at', now()), expire(fp, 300)))(create_obj('a set of footprints', tags=['footprint'], location=here)))
```

The read — `track` gates on the tracking skill and reports who and how
long ago:

```text
@set Trailcraft/cmd_track = $track: spot = loc(enactor); prints = [o for o in contents(spot) if has_tag(o,'footprint')]; (pemit(enactor,'The ground here is unmarked.') if not prints else (pemit(enactor,'The scuffs here mean nothing to you.') if not skill_check(enactor,'tracking') else pemit(enactor, 'You read the ground: ' + ', '.join([get_attr(p,'quarry_name','someone') + ' passed about ' + str(now()-get_attr(p,'at',now())) + 's ago' for p in prints]))))
```

## Try it

Have someone cross the Clearing, then track where they stood:

```text
(Vera)  thicket        -> Vera walks off into The Thicket
(you, skilled) track   -> You read the ground: Vera passed about 3s ago
(you, unskilled) track -> The scuffs here mean nothing to you.
```

Wait five minutes (or `@examine` the print and watch its `expires_at`)
and the trail is gone — `track` finds unmarked ground. Every room you
tag `zone:wilds` starts keeping tracks the moment it joins; the master
never needs to know they exist.

## Going further

- **Which way did they go?** Prints are dropped in the room a quarry
  *leaves*, so the freshest print in a neighbouring room points down the
  trail — a good roll can scan `exits(spot)`, read each destination
  room's prints, and name the exit the tracks lead down.
- **Harder trails:** subtract from the check for rain (read the
  [weather](036_weather_system.md) master), for stone floors (a room
  `hard_ground` tag), or for a quarry who `hid` — stealth vs tracking as
  a contest.
- **Blood, not boots:** the same stamp on `ON_DAMAGE` drops blood that
  decays faster — a wounded fugitive is easier to follow, briefly.
- **Counter-tracking:** a `$cover tracks` command that `destroy_obj`s
  the prints in your room on a skill check — the pursued get a move too.
