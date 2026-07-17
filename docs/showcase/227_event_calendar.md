# 227. Event calendar & RSVP

> Checklist item 227 — [now] — *event ledger attrs, RSVP toggle, ticker reminders that pemit attendees, host cancel*

**What you'll build:** a Community Board where any player schedules an
event — `event add 300 = Cargo Bay Fight Night` — and others `rsvp` to it.
A heartbeat watches the clock and pings everyone on the guest list as the
start time nears, then again when it begins. Hosts can cancel, and the
attendees are told.

**Concepts:** events as a **ledger of dict attributes** (`event_<n>`) on a
world-zone master; an **RSVP toggle** stored as an id list per event; a
**`script_ticker` reminder sweep** that reads each event's `at` against
`now()` and `pemit`s the attendees (the [job board](094_job_board.md) /
[housing rent](093_housing_rent.md) heartbeat, aimed at a calendar); and a
purge so past events age out.

## How it works

**An event is a dated dict; the calendar is a run of them.** `event_<n> =
{host, host_name, title, at, rsvps, reminded}` with a `next_event`
counter. `at` is an absolute epoch time (`now() + seconds`), so the
reminder logic is pure arithmetic — no wall-clock parsing, no timezones,
just `at - now()`. `rsvps` is the guest list; the host is auto-added.

**Reminders ride the heartbeat, staged by a `reminded` flag.** The board
runs a `script_ticker`. Each beat sweeps every event and does three
things: if it's inside the reminder window and hasn't been announced
(`reminded < 1`), ping the guest list and bump the flag; if it's now
started (`reminded < 2`), ping again and bump; and if it's well past,
delete the row. The `reminded` flag is what keeps each announcement to
*once* — the same "warn once" discipline the [rent box](093_housing_rent.md)
uses so the courier doesn't nag every tick.

**Why `pemit`, and why a world-zone master.** Reminders must reach
attendees wherever they are, so they go by `pemit` (delivery by id, not
room). And because the board is a **world-zone master**, `event add`,
`events`, and `rsvp` work from any world room — you don't have to stand at
the board to sign up for a party across the station.

## Build it

A world-zone commons and the board, with a heartbeat:

```text
@dig The Commons = commons, out
commons
@zone here = world
@create the Community Board
drop the Community Board
@desc the Community Board = A pinboard thick with flyers. EVENT ADD <seconds> = <title> schedules one; EVENTS lists them; RSVP <n> toggles attendance; EVENT CANCEL <n> (host) calls it off.
@zone/master the Community Board = world
@set the Community Board/window = 60
@behavior the Community Board = script_ticker, interval:30
```

`event add <seconds> = <title>` and `events` (upcoming, with the countdown
and headcount):

```text
@set the Community Board/cmd_add = $event add * = *:sec = int(arg0) if trim(arg0).isdigit() else 0; title = trim(arg1); ok = has_tag(enactor, 'player') and sec > 0 and bool(title); [(set_attr(me, 'event_' + str(n), {'host': enactor.id, 'host_name': name(enactor), 'title': escape(t), 'at': now() + s, 'rsvps': [enactor.id], 'reminded': 0}), set_attr(me, 'next_event', n + 1), pemit(enactor, 'Scheduled ' + escape(t) + ' as event #' + str(n) + '. You are on the guest list.')) for g, s, t in [[ok, sec, title]] if g for n in [get_attr(me, 'next_event', 1)]]; pemit(enactor, 'Usage: EVENT ADD <seconds from now> = <title>.') if not ok else None
@set the Community Board/cmd_events = $events:rows = [[i, get_attr(me, 'event_' + str(i))] for i in range(1, get_attr(me, 'next_event', 1)) if get_attr(me, 'event_' + str(i))]; up = [r for r in rows if r[1]['at'] - now() > -300]; pemit(enactor, 'Upcoming events:' if up else 'No events scheduled. EVENT ADD <seconds> = <title>.'); [pemit(enactor, '  #' + str(r[0]) + ' ' + r[1]['title'] + ' by ' + r[1]['host_name'] + ' - in ' + str(int(r[1]['at'] - now())) + 's - ' + str(len(r[1]['rsvps'])) + ' attending') for r in up]
```

`rsvp <n>` toggles you on or off the guest list:

```text
@set the Community Board/cmd_rsvp = $rsvp *:n = trim(arg0); ev = get_attr(me, 'event_' + n); ok = bool(ev); going = ok and enactor.id in ev['rsvps']; [(set_attr(me, 'event_' + n, dict(x, rsvps=[r for r in x['rsvps'] if r != enactor.id] if go else x['rsvps'] + [enactor.id])), pemit(enactor, ('You cancel your RSVP to ' + x['title'] + '.') if go else ('You RSVP to ' + x['title'] + '.'))) for g, x, go in [[ok, ev, going]] if g]; pemit(enactor, 'No such event.') if not ok else None
```

`event cancel <n>` — the host calls it off and everyone on the list hears:

```text
@set the Community Board/cmd_cancel = $event cancel *:n = trim(arg0); ev = get_attr(me, 'event_' + n); ok = bool(ev) and ev['host'] == enactor.id; [([pemit(get('#' + str(r)), x['title'] + ' has been cancelled by ' + name(enactor) + '.') for r in x['rsvps'] if get('#' + str(r))], del_attr(me, 'event_' + n)) for g, x in [[ok, ev]] if g]; pemit(enactor, 'No such event, or you are not its host.') if not ok else None
```

The reminder sweep — soon, started, purge — each staged by the `reminded`
flag so it fires once:

```text
@set the Community Board/on_tick = [([pemit(get('#' + str(r)), 'Reminder: ' + ev['title'] + ' hosted by ' + ev['host_name'] + ' starts in under ' + str(int(ev['at'] - now())) + ' seconds.') for r in ev['rsvps'] if get('#' + str(r))], set_attr(me, 'event_' + str(i), dict(ev, reminded=1))) for i in range(1, get_attr(me, 'next_event', 1)) for ev in [get_attr(me, 'event_' + str(i))] if ev and ev['reminded'] < 1 and 0 < ev['at'] - now() <= get_attr(me, 'window', 60)]; [([pemit(get('#' + str(r)), ev['title'] + ' is starting now!') for r in ev['rsvps'] if get('#' + str(r))], set_attr(me, 'event_' + str(i), dict(ev, reminded=2))) for i in range(1, get_attr(me, 'next_event', 1)) for ev in [get_attr(me, 'event_' + str(i))] if ev and ev['reminded'] < 2 and ev['at'] - now() <= 0]; [del_attr(me, 'event_' + str(i)) for i in range(1, get_attr(me, 'next_event', 1)) for ev in [get_attr(me, 'event_' + str(i))] if ev and now() - ev['at'] > 300]
```

## Try it

Bob schedules a fight night 300 seconds out; Cass RSVPs:

```text
(Bob)  event add 300 = Cargo Bay Fight Night
   -> Scheduled Cargo Bay Fight Night as event #1. You are on the guest list.
(Cass) events
   Upcoming events:
     #1 Cargo Bay Fight Night by Bob - in 300s - 1 attending
(Cass) rsvp 1
   -> You RSVP to Cargo Bay Fight Night.
```

Wind the clock in for a demo (set `at` near now and force a beat) and the
guest list lights up:

```text
@eval set_attr(get('the Community Board'), 'event_1', dict(get_attr(get('the Community Board'), 'event_1'), at=now() + 30))
@tr the Community Board/on_tick
   -> (to Bob and Cass) Reminder: Cargo Bay Fight Night hosted by Bob starts in under 30 seconds.
```

Push `at` to `now()` and beat again for the "starting now!" ping. Each
fires exactly once — the `reminded` flag sees to that — and long after the
event the sweep quietly deletes the row.

## Going further

- **expire() tokens instead of a sweep** — mint a per-event object with
  `expire(tok, seconds)` whose `ON_EXPIRE` pings the list; the reminder
  then survives a reboot without a running ticker (the
  [message in a bottle](083_message_in_bottle.md) persistence model).
- **Recurring events** — on the "started" beat, re-stamp `at = now() +
  period` and reset `reminded` instead of purging, for a weekly game night.
- **Capacity & waitlist** — cap `rsvps` and spill overflow into a
  `waitlist`, promoting from it when someone cancels.
- **Calendar over GMCP** — `oob(enactor, 'Events.List', {...})` on `events`
  so a client can render a real calendar widget from the same ledger.
```
