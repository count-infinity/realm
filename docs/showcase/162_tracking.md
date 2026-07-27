# 162. Tracking

> Checklist item 162 ([now]): *ON_LEAVE footprint stamps, skill_check reads, expire() decay*

**What you'll build:** A wilderness where passers-by leave a trail. Every
time someone crosses a room they stamp footprints into it, and a skilled
tracker can `track` to read who came through and how long ago, while the
unskilled see only meaningless scuffs. The tracks fade on their own.

**Concepts:** a **zone master hearing [`ON_LEAVE`](../reference/softcode.md#lifecycle-hooks)**
across every room it owns (as in [071 (guard response)](071_guard_response.md));
**footprints as owned objects** stamped with who and when;
[`skill_check`](../reference/softcode.md#fn-skill_check) gating what a
tracker can read; and [`expire()`](../reference/softcode.md#fn-expire) as
evidence decay (as in [083 (message in a bottle)](083_message_in_bottle.md)).

## How it works

The finished piece is one master object that sits quietly in the wilds and
mints a small evidence object every time a player walks out of any room in the
zone. Reading those objects is a separate command that gates on a skill, and
each object deletes itself after a few minutes so a cold trail vanishes with no
housekeeping. This section answers three questions: how one object hears the
whole zone, why the footprint is an object rather than an attribute, and why the
master beats hanging the hook on each room.

### How one object hears the whole zone

Every move fires an `ON_LEAVE` on the room being left, and a zone master hears
the events of every room it owns, so a single `Trailcraft` master witnesses
*every* departure in the wilds through one hook. When that hook runs, `here` is
bound to the room where the departure happened, not to wherever the master
itself is standing, so the master can drop a footprint object straight into the
room the walker just left. It stamps the print with the walker's id, their name,
and [`now()`](../reference/softcode.md#fn-now).

Because the master watches everyone, it is a **global witness** and takes no
`if target is me:` [guard](../reference/softcode.md#guard-on-target). What it
does need is a domain filter: it stamps only objects tagged `player`, so wild
critters padding through leave the ground clean. For the propagation model
behind all of this see [the event architecture](../architecture/events.md), and
for a guided tour of witnesses and hooks see
[245 (event bus tour)](245_event_bus_tour.md).

### Why a footprint is an object, not an attribute

A print is an ordinary owned object tagged `footprint`, and that choice buys two
things at once. First it is readable: `track` gathers the `footprint` objects in
the reader's room and turns them into a report, but only after a passed
`skill_check(enactor, 'tracking')`, so an unskilled reader learns nothing.
Second it decays for free. Because the print is an object, `expire(fp, 300)`
gives it a lifetime, and the world tick destroys it when the lease lapses. A
cold trail literally disappears with no sweeper script to write.

### Why a master, not a hook on each room

You could hang `ON_LEAVE` on every room, but the master does the job once for
the whole zone, and every new room you tag into `wilds` starts leaving tracks
the moment it joins. Membership is the tag, so the master never needs to learn
that a room exists.

## Build it

First dig two wilds rooms, tag each into the `wilds` zone, then create the
`Trailcraft` master, make it the zone master, and drop it in place:

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

The stamp mints a dated footprint on every player's departure and gives it a
five-minute lease. The `if has_tag(enactor, 'player')` line is the domain
filter, not a target guard: this master is a global witness, so the filter is
about *what walked*, and [`create_obj`](../reference/softcode.md#fn-create_obj)
drops the print into `here`, the room the walker just left:

```text
@set Trailcraft/on_leave = '''
if has_tag(enactor, 'player'):
    fp = create_obj('a set of footprints', tags=['footprint'], location=here)
    set_attr(fp, 'quarry', '#' + enactor.id)   # a stable id survives a rename
    set_attr(fp, 'quarry_name', name(enactor))
    set_attr(fp, 'at', now())
    expire(fp, 300)
'''
```

The `track` command reads the ground where the reader stands. It gathers the
`footprint` objects with [`contents`](../reference/softcode.md#fn-contents), and
then a chain of cases decides the response: unmarked ground, a failed
[`skill_check`](../reference/softcode.md#fn-skill_check) that yields only scuffs,
or a success that names each quarry and how long ago they passed. Each line
reaches the reader with [`pemit`](../reference/softcode.md#fn-pemit):

```text
@set Trailcraft/cmd_track = '''
$track:
spot = loc(enactor)
prints = [o for o in contents(spot) if has_tag(o, 'footprint')]
if not prints:
    pemit(enactor, 'The ground here is unmarked.')
elif not skill_check(enactor, 'tracking'):
    pemit(enactor, 'The scuffs here mean nothing to you.')
else:
    trail = [get_attr(p, 'quarry_name', 'someone') + ' passed about ' + str(now() - get_attr(p, 'at', now())) + 's ago' for p in prints]
    pemit(enactor, 'You read the ground: ' + ', '.join(trail))
'''
```

## Try it

Have someone cross the Clearing, then read the ground where they stood. A
skilled tracker reads the trail; an unskilled one sees only scuffs:

```text
> (Vera) thicket
Vera walks off into The Thicket.

> (you, skilled in tracking) track
You read the ground: Vera passed about 3s ago

> (you, unskilled) track
The scuffs here mean nothing to you.
```

The elapsed number varies with how long you wait; everything else is fixed. Wait
five minutes (or `@examine` the print and watch its `expires_at`) and the trail
is gone, so `track` finds unmarked ground. Every room you tag `zone:wilds`
starts keeping tracks the moment it joins, and the master never needs to know
they exist.

## Going further

- **Which way did they go?** A print is dropped in the room a quarry *leaves*,
  so the freshest print in a neighbouring room points down the trail. A good
  roll can scan [`exits`](../reference/softcode.md#fn-exits)`(spot)`, read each
  destination room's prints, and name the exit the tracks lead down.
- **Harder trails:** subtract from the check for rain (read the
  [weather](036_weather_system.md) master), for stone floors (a room
  `hard_ground` tag), or for a quarry who `hid`, pitting stealth against
  tracking as a contest.
- **Blood, not boots:** the same stamp on `ON_DAMAGE` drops blood that decays
  faster, so a wounded fugitive is easier to follow, briefly.
- **Counter-tracking:** a `$cover tracks` command that
  [`destroy_obj`](../reference/softcode.md#fn-destroy_obj)s the prints in your
  room on a skill check, so the pursued get a move too.
