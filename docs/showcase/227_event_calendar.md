# 227. Event calendar & RSVP

> Checklist item 227 ([now]): *event attrs, $rsvp, on_tick reminders*

**What you'll build:** a Community Board where any player schedules an event
with `event add 300 = Cargo Bay Fight Night`, where others `rsvp` to it, and
where a heartbeat pings the guest list as the start time nears and again when
the event begins. The host may call it off, and everyone who signed up hears
about it.

**Concepts:** a calendar kept as a run of numbered dict attributes
(`event_<n>`) on a world-zone master; an RSVP toggle stored as a list of
player ids inside each event; a
[`script_ticker`](../reference/softcode.md#npcs-behaviors) sweep that compares
each event's `at` against [`now()`](../reference/softcode.md#fn-now) and
[`pemit`](../reference/softcode.md#fn-pemit)s the attendees; and a `reminded`
counter that holds each announcement to exactly one delivery.

## How it works

The finished board is one object carrying two kinds of attribute: a numbered
row per scheduled event, and a handful of scripts that read those rows. Three
`$`-commands write the rows (schedule, RSVP, cancel), a fourth reads them out
as a listing, and a heartbeat on the same object walks the rows once a minute
to decide who needs telling. This section answers four questions: what a row
holds, how the sweep announces each event only once, why the sweep period and
the reminder window are counted in different units, and how a board in one
room reaches players scattered across the station.

### What one event row holds

An event is a dict stored under `event_<n>`, where `n` comes from a
`next_event` counter that only ever climbs, so ids stay stable even after
rows are deleted. The keys are `host` (the host's object id), `host_name`,
`title`, `at`, `rsvps`, and `reminded`.

The interesting one is `at`. It is an absolute time in epoch seconds, written
as `now() + seconds` when the event is scheduled, which turns every later
question into arithmetic: `at - now()` is the countdown, a negative result
means the event has already begun, and nothing in the build ever parses a
wall clock or reasons about a time zone.
[`now()`](../reference/softcode.md#fn-now) returns integer epoch seconds, so
these are ordinary integers you may compare and subtract.

### How a guest list lives inside the event

`rsvps` is a list of player ids held inside the same dict, so a guest list
travels with its event and a cancelled event takes its guest list with it.
The host is seeded onto the list at `event add`, which is why a brand new
event already reads "1 attending".

Because the row is a dict, `rsvp` rewrites it rather than mutating it in
place: it builds `dict(ev, rsvps=<new list>)` and stores that back with
[`set_attr`](../reference/softcode.md#fn-set_attr). Writing the whole dict
back is what makes the change stick, since editing the list you read out of
the attribute would leave the stored value untouched.

### How the sweep announces each event once

`reminded` is a counter, not a flag, and it is the whole of the "announce
once" discipline: 0 means nothing has been said, 1 means the advance warning
went out, and 2 means the start ping went out. Each beat, the sweep looks at
one row and sends at most one of two announcements. If the event is still in the
future, is inside the reminder window, and `reminded` is 0, it warns the
guest list and stamps `reminded` to 1. Otherwise, if the start time has
passed and `reminded` is under 2, it pings the guest list again and stamps 2.
Separately, once the event is well behind the clock, the row is deleted so
the calendar stays short. The [rent box](093_housing_rent.md) uses the same
counter trick with its `warned` attribute, for the same reason: a heartbeat
that reads a condition will read it true on every beat until something
records that it was acted on.

### Why the sweep period and the window use different units

This is the one place where two numbers in the build look comparable and are
not. The [`script_ticker`](../reference/softcode.md#npcs-behaviors) behavior's
`interval` counts **world beats**, and a beat is the world tempo `WORLD_TICK`,
four seconds by default, so `interval:15` fires the sweep roughly once every
60 seconds. The `window` attribute is compared against
[`now()`](../reference/softcode.md#fn-now) and is therefore in **plain
seconds**.

Do the multiplication once and keep the window several sweeps wide. A window
narrower than the gap between beats lets an event cross the entire window
between two sweeps, in which case the advance warning is skipped and the only
message anyone gets is "starting now". The build below pairs a 60 second
sweep with a 300 second window, so each event gets about five chances to be
caught on its way in.

### Why the board reaches players who are nowhere near it

Two things put the board in front of the whole station. First, reminders go
out with [`pemit`](../reference/softcode.md#fn-pemit), which delivers to a
player by identity rather than to a room, so an attendee hears the warning
wherever they happen to be standing.

Second, the board is a **world-zone master**: it carries the `zone_master`
tag plus the `zone:world` tag, which `@zone/master` sets together. The
engine's trigger search consults a room's zone masters, so `event add`,
`events`, `rsvp`, and `event cancel` answer for anyone standing in any room
tagged `zone:world`. That scope is exact rather than universal, and it is
worth stating plainly: a player in a room that carries no `zone:world` tag
gets no response at all, because the board is never consulted for them. REALM
has no Master Room, so a world-zone master is how a game-wide verb is built
today. The trigger search takes the first object whose pattern matches and
stops there, so a second master in the same zone that also answers `events`
would simply never be reached, which is a good reason to keep one board per
verb.

## Build it

Start with the shell. Dig a commons off wherever you are standing, walk into
it, put it in the `world` zone, then create the board and drop it there:

```text
@dig The Commons = commons, out
commons
@zone here = world
@create the Community Board
drop the Community Board
@desc the Community Board = A pinboard thick with flyers. EVENT ADD <seconds> = <title> schedules one; EVENTS lists them; RSVP <n> toggles attendance; EVENT CANCEL <n> (host) calls it off.
```

Crown the board as the zone's master so its verbs answer anywhere in the
`world` zone, give it a reminder window of 300 seconds, and hang the
heartbeat on it. Note the units: `interval:15` is fifteen world beats of about
four seconds each, so the sweep runs about once a minute, comfortably inside
the 300 second window:

```text
@zone/master the Community Board = world
@set the Community Board/window = 300
@behavior the Community Board = script_ticker, interval:15
```

`event add <seconds> = <title>` writes a row. Its steps in order: read the
delay and the title out of the two wildcards, refuse anything that is not a
player asking for a positive delay with a real title, then stamp the row,
advance the counter, and confirm:

```text
@set the Community Board/cmd_add = '''
$event add * = *:
seconds = int(trim(arg0)) if trim(arg0).isdigit() else 0
title = escape(trim(arg1))  # escape player text so a title cannot inject colour markup
if has_tag(enactor, 'player') and seconds > 0 and title:
    n = V('next_event', 1)  # ids only climb, so a deleted row never reuses its number
    set_attr(me, 'event_' + str(n), {'host': enactor.id, 'host_name': name(enactor), 'title': title, 'at': now() + seconds, 'rsvps': [enactor.id], 'reminded': 0})
    set_attr(me, 'next_event', n + 1)
    pemit(enactor, f'Scheduled {title} as event #{n}. You are on the guest list.')
else:
    pemit(enactor, 'Usage: EVENT ADD <seconds from now> = <title>.')
'''
```

`events` reads the calendar back. It walks every id up to the counter,
skipping numbers whose row has been deleted, keeps anything less than five
minutes past its start time, and prints the countdown and the headcount. An
event already under way prints a negative countdown, which is how a reader
spots the one happening right now:

```text
@set the Community Board/cmd_events = '''
$events:
rows = [[i, V('event_' + str(i))] for i in range(1, V('next_event', 1))]
upcoming = [r for r in rows if r[1] and r[1]['at'] - now() > -300]
if upcoming:
    pemit(enactor, 'Upcoming events:')
    for r in upcoming:
        ev = r[1]
        pemit(enactor, f'  #{r[0]} {ev["title"]} by {ev["host_name"]} - in {int(ev["at"] - now())}s - {len(ev["rsvps"])} attending')
else:
    pemit(enactor, 'No events scheduled. EVENT ADD <seconds> = <title>.')
'''
```

`rsvp <n>` is a toggle, so one verb both signs you up and takes you off. Each
branch writes the whole dict back with the rebuilt guest list:

```text
@set the Community Board/cmd_rsvp = '''
$rsvp *:
key = 'event_' + trim(arg0)
ev = V(key)
if not ev:
    pemit(enactor, 'No such event.')
elif enactor.id in ev['rsvps']:
    set_attr(me, key, dict(ev, rsvps=[r for r in ev['rsvps'] if r != enactor.id]))
    pemit(enactor, 'You cancel your RSVP to ' + ev['title'] + '.')
else:
    set_attr(me, key, dict(ev, rsvps=ev['rsvps'] + [enactor.id]))
    pemit(enactor, 'You RSVP to ' + ev['title'] + '.')
'''
```

`event cancel <n>` belongs to the host alone. It tells everyone still on the
guest list and then deletes the row, and the single "no such event, or you
are not its host" reply covers both refusals so a stranger learns nothing
about ids they do not own:

```text
@set the Community Board/cmd_cancel = '''
$event cancel *:
key = 'event_' + trim(arg0)
ev = V(key)
if ev and ev['host'] == enactor.id:
    for r in ev['rsvps']:
        guest = get('#' + r)
        if guest:
            pemit(guest, ev['title'] + ' has been cancelled by ' + name(enactor) + '.')
    del_attr(me, key)
else:
    pemit(enactor, 'No such event, or you are not its host.')
'''
```

Finally the sweep. A ticker fires only on the object that owns it, so unlike
a reactive [`ON_<EVENT>`](../reference/softcode.md#lifecycle-hooks) hook it
needs no
[`target` guard](../reference/softcode.md#guard-on-target). Its steps in
order: read the window, walk every id, skip deleted rows, then warn or start
or purge:

```text
@set the Community Board/on_tick = '''
window = V('window', 300)
for i in range(1, V('next_event', 1)):
    key = 'event_' + str(i)
    ev = V(key)
    if ev:
        left = ev['at'] - now()  # positive: still ahead. negative: already begun
        if ev['reminded'] < 1 and 0 < left <= window:
            for r in ev['rsvps']:
                guest = get('#' + r)
                if guest:
                    pemit(guest, f'Reminder: {ev["title"]} hosted by {ev["host_name"]} starts in under {int(left)} seconds.')
            set_attr(me, key, dict(ev, reminded=1))
        elif ev['reminded'] < 2 and left <= 0:
            for r in ev['rsvps']:
                guest = get('#' + r)
                if guest:
                    pemit(guest, ev['title'] + ' is starting now!')
            set_attr(me, key, dict(ev, reminded=2))
        if left < -300:
            del_attr(me, key)  # five minutes after the start, the row leaves the calendar
'''
```

## Try it

Bob schedules a fight night five minutes out, and Cass reads the board and
signs up. Note that the board answers Cass from any room tagged `zone:world`,
not only from the commons:

```text
> event add 300 = Cargo Bay Fight Night
Scheduled Cargo Bay Fight Night as event #1. You are on the guest list.

> events
Upcoming events:
  #1 Cargo Bay Fight Night by Bob - in 300s - 1 attending

> rsvp 1
You RSVP to Cargo Bay Fight Night.

> rsvp 1
You cancel your RSVP to Cargo Bay Fight Night.

> rsvp 1
You RSVP to Cargo Bay Fight Night.
```

Rather than waiting out the clock, wind the event's start time forward into
the reminder window and beat the sweep by hand. `@tr` runs the attribute as
though the heartbeat had fired, so both names on the guest list light up:

```text
> @eval set_attr(get('the Community Board'), 'event_1', dict(get_attr(get('the Community Board'), 'event_1'), at=now() + 30))
Done.

> @tr the Community Board/on_tick
Triggered the Community Board/on_tick.
   (Bob and Cass each hear) Reminder: Cargo Bay Fight Night hosted by Bob starts in under 30 seconds.
```

The two results worth confirming deliberately are that the warning fires once
and that the start ping is a separate stage. Beat the sweep again with
nothing changed and the room stays silent, because `reminded` is now 1. Push
`at` back to `now()` and beat once more for the start ping, which stamps
`reminded` to 2:

```text
> @tr the Community Board/on_tick
Triggered the Community Board/on_tick.
   (silence: reminded is already 1)

> @eval set_attr(get('the Community Board'), 'event_1', dict(get_attr(get('the Community Board'), 'event_1'), at=now()))
Done.

> @tr the Community Board/on_tick
Triggered the Community Board/on_tick.
   (Bob and Cass each hear) Cargo Bay Fight Night is starting now!
```

Cancellation is the host's alone. Cass gets the refusal, Bob gets obeyed, and
everyone on the guest list is told:

```text
> event cancel 1
No such event, or you are not its host.

> event cancel 1
   (Cass hears) Cargo Bay Fight Night has been cancelled by Bob.
```

Push `at` more than five minutes into the past and the next beat deletes the
row quietly, with no message to anybody, which is how the calendar keeps
itself short without a separate cleanup verb.

## Going further

- **expire() tokens instead of a sweep.** Mint a small object per event and
  arm it with [`expire(tok, seconds)`](../reference/softcode.md#fn-expire),
  whose [`ON_EXPIRE`](../reference/softcode.md#lifecycle-hooks) pings the
  guest list. The reminder then survives a reboot
  without a ticker running, since `expire()` persists where
  [`wait()`](../reference/softcode.md#fn-wait) lives only in memory. The
  hook destroys its object afterwards unless it clears `expires_at`, which
  suits a one-shot reminder exactly; see the
  [message in a bottle](083_message_in_bottle.md) for the full contract.
- **Recurring events.** On the "starting now" branch, re-stamp
  `at = now() + period` and reset `reminded` to 0 instead of letting the row
  age out, and a weekly game night schedules itself forever.
- **Capacity and a waitlist.** Cap the length of `rsvps`, spill the overflow
  into a `waitlist` key in the same dict, and promote the first name off it
  whenever somebody toggles their RSVP back off.
- **Calendar over GMCP.** Add [`oob(enactor, 'Events.List',
  {...})`](../reference/softcode.md#fn-oob) to the `events` verb so a capable
  client renders a real calendar widget from the very same rows.
