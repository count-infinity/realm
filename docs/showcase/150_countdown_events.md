# 150. Global countdown events

> Checklist item 150 ([now]): *server-wide announcements at T-minus intervals, wait() chains, remit loops over all rooms*

**What you'll build:** An Event Herald that runs a countdown to **every
room on the server**. Typing `countdown 3 for the Convergence` announces "in 3
minutes... 2... 1... begins NOW!" station-wide, and the same object is generic
enough to reuse for any event, at any duration, from one command.

**Concepts:** the world-zone master as a server-wide broadcaster,
[`search_world(tag='room')`](../reference/softcode.md#fn-search_world) as the
all-rooms fan-out, a **parameterized, reusable**
[`wait()`](../reference/softcode.md#fn-wait) countdown (label and length passed
as arguments), and [`cancel_wait()`](../reference/softcode.md#fn-cancel_wait) to
scrub it.

## How it works

The finished Herald is one object that owns a countdown as *data*: an event
label and a number of minutes remaining, both stored as attributes. A command
seeds those two values and lights the first tick; each tick announces the
current minute to the whole world, counts down by one, and schedules the next
tick a `gap` seconds later; at zero the chain hands off to a `fire` step that
delivers the "begins NOW!" line. This section answers three questions: how the
announcement reaches every room, why the countdown is reusable rather than
welded to one event, and how the `wait()` chain carries itself to zero.

### How the announcement reaches every room

This is the [self-destruct (056)](056_self_destruct.md) countdown widened from
one station to the whole world. There, the countdown is **zone-scoped**:
[`act(..., targeting='zone')`](../reference/softcode.md#fn-act) reaches one
station, and the payload is fire in that station's rooms. Here the goal is
server-wide, so the Herald loops [`remit()`](../reference/softcode.md#fn-remit)
over `search_world(tag='room')` instead. Every room a builder digs is tagged
`room`, so that query returns the entire world, and a `remit` into each one
delivers the line to everyone standing there. The reach is genuinely global: a
player in a room that belongs to no zone at all still hears it, because the
fan-out keys on the `room` tag, not on any zone.

For a broadcast confined to one area, use 056's zone targeting instead, so pick
the blast radius deliberately: `search_world(tag='room')` for the whole world,
`act(targeting='zone')` for a single zone.

### How the Herald hears the command from anywhere

REALM has no Master Room yet, so a command that should work world-wide rides on
a **world-zone master**: an object crowned master of a `zone:world` room. The
softcode command search consults the masters of whatever zone the typist is
standing in, so once your public rooms carry the `zone:world` tag, the Herald
hears `countdown` and `scrub` from any of them. This is the same world-master
trick that carries the global note in [083](083_message_in_bottle.md).
`@zone/master Event Herald = world` sets both tags at once: it tags the Herald
`zone:world` and marks it a `zone_master`.

### How the countdown stays reusable

The countdown is data, not a fixed script. `label` and `remaining` are
attributes that the command writes, so one Herald runs a countdown to
*anything* (a market opening, a boss spawn, a server event) without
re-authoring. 056's countdown is welded to one station's self-destruct, whereas
this one is a reusable utility driven entirely by its two arguments.

### How the wait() chain carries itself to zero

The countdown itself is a `wait()` chain, the [148](148_delayed_actions.md)
idiom. The `tick` step reads `remaining`, and while it is above zero it calls
`announce`, decrements the counter with
[`decr`](../reference/softcode.md#fn-decr), and schedules the next `tick` a
`gap` seconds later, stashing the returned handle in `pending`. When
`remaining` reaches zero it hands off to `fire`, which clears the bookkeeping
attributes and delivers the final line. `scrub` reads that handle back with
[`V`](../reference/softcode.md#fn-v) and cancels the one pending tick, as
`cancel_wait(V('pending'))`. Being `wait()`-based, the chain lives in
memory, which is the right fit for a countdown: a reboot mid-count simply
forgets it rather than resuming a stale one.

## Build it

Dig two rooms into the world zone to prove the broadcast reaches everywhere,
then create the Herald and crown it their master. `gap` is the pause between
ticks, in seconds.

```text
@dig Plaza = plaza, out
plaza
@zone here = world
@dig Docks = docks, plaza
docks
@zone here = world
plaza
@create Event Herald
drop Event Herald
@zone/master Event Herald = world
@set Event Herald/banner = STATION ANNOUNCEMENT
@set Event Herald/gap = 2
```

The `announce` helper fans one line out to every room. It is a single
comprehension over `search_world(tag='room')`, and the f-string reads the
current `label` and `remaining` off the Herald, falling back to neutral wording
if a value is missing.

```text
@set Event Herald/announce = [remit(r, f"{V('banner', 'ATTENTION')}: {V('label', 'an event')} in {V('remaining', 0)} minutes.") for r in search_world(tag='room')]
```

`tick` is the heart of the chain. It reads the minutes left, and either fires
the finale at zero or announces the current minute, counts down, and schedules
the next tick.

```text
@set Event Herald/tick = '''
n = V('remaining', 0)
if n <= 0:
    eval_attr(me, 'fire')
else:
    eval_attr(me, 'announce')
    decr('remaining')
    # stash the wait handle so scrub can cancel the one pending tick
    set_attr(me, 'pending', wait(V('gap', 2), 'trigger me/tick'))
'''
```

`fire` is the zero-hour payload. It clears the countdown's bookkeeping and
sends the "begins NOW!" line to every room.

```text
@set Event Herald/fire = '''
del_attr(me, 'pending')
del_attr(me, 'remaining')
for r in search_world(tag='room'):
    remit(r, f"{V('label', 'the event')} begins NOW!")
'''
```

Now the two verbs. `countdown <n> for <label>` is owner-only and refuses to
stack a second count over a running one, so a live countdown is protected until
it finishes or is scrubbed.

```text
@set Event Herald/cmd_countdown = '''
$countdown * for *:
if enactor != owner(me):
    pemit(enactor, 'Command authority required.')
elif V('pending'):
    pemit(enactor, 'A countdown is already running.')
else:
    set_attr(me, 'label', arg1)
    set_attr(me, 'remaining', int(arg0))
    eval_attr(me, 'tick')
'''
```

`scrub countdown` calls a running count off: it cancels the pending tick, clears
the bookkeeping, and tells the world the event is off.

```text
@set Event Herald/cmd_scrub = '''
$scrub countdown:
if V('pending'):
    cancel_wait(V('pending'))
    del_attr(me, 'pending')
    del_attr(me, 'remaining')
    for r in search_world(tag='room'):
        remit(r, f"{V('label', 'the event')} has been called off.")
else:
    pemit(enactor, 'No countdown is running.')
'''
```

## Try it

With players scattered across the Plaza and the Docks, standing in a world-zone
room as the owner:

```text
> countdown 3 for the Convergence
(every room) STATION ANNOUNCEMENT: the Convergence in 3 minutes.
(gap) STATION ANNOUNCEMENT: the Convergence in 2 minutes.
(gap) STATION ANNOUNCEMENT: the Convergence in 1 minutes.
(gap) the Convergence begins NOW!
```

Everyone on the server hears every step of the count, wherever they stand,
including rooms that belong to no zone. Start another and call it off:

```text
> countdown 5 for the Eclipse
> scrub countdown
(every room) the Eclipse has been called off.
```

A non-owner who tries `countdown` gets *Command authority required.*, and
`countdown` over a live count earns *A countdown is already running.*, so it is
one countdown at a time, from one command, to the whole world.

## Going further

- **A real payload:** have `fire` do more than announce, spawning the boss,
  opening the arena exits, or firing an [`act()`](../reference/softcode.md#fn-act)
  world event. The countdown becomes the ramp to any global happening.
- **Scheduled, not manual:** trigger `countdown` from the daily timetable of
  [145](145_scheduled_events.md) so a nightly event announces itself.
- **Opt-out channel:** filter the broadcast by an `announce_optout` attribute on
  the player (skip a room's listeners who set it) for players who mute server
  pings, the announcement pattern of [181](181_announcements.md).
- **Per-zone flavor:** vary the wording inside `announce` by the room's zone to
  localize it, so the docks hear a foghorn where the plaza hears a chime.
