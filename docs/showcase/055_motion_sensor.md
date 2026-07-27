# 055. Motion Sensor Log

> Checklist item 55 ([now]): *ON_ENTER/ON_LEAVE, now(), in-object log attrs*

**What you'll build:** A little black dome that records who entered and left
its room, with timestamps, into a capped in-object log, plus a `review` command
that plays the record back as "so-many-seconds ago" lines.

**Concepts:** paired
[`ON_ENTER`/`ON_LEAVE`](../reference/softcode.md#lifecycle-hooks) witnesses,
[`now()`](../reference/softcode.md#fn-now) as the clock, a **list attribute as
an append-only log** with a slice cap so it cannot grow forever, and the honest
limit of the departure event.

## How it works

The finished device is one dome lying on the floor of the room it watches. Every
time a character walks in or out, the dome appends a small record to a `log`
attribute on itself, and a `review` command reads that log back with each entry
aged against the current clock. This section answers three questions: how a
dropped object hears arrivals and departures, why the records are plain data
capped by a slice, and why a walker who teleports away leaves a gap the log
cannot fill.

### How does a dome on the floor hear people come and go?

Movement fires two witnessed hooks, and an object already in the room hears both
of them. When someone walks in, the engine fires every room object's
[`ON_ENTER`](../reference/softcode.md#lifecycle-hooks); when someone walks out,
its `ON_LEAVE`; and in each case the mover is bound as `enactor`. This is the
same witnessed shape as the [security camera](054_security_camera.md), except
the camera forwards each event live while the dome remembers it. A departure
fires while the mover still stands in the origin room and an arrival fires once
the mover has reached the destination, which is the two-action form movement
always takes (see [action phases](../design/action-phases.md)).

One fact from that model shapes the guard below. An `ON_ENTER` event targets the
**room**, not the dome, so the usual
[`target is me`](../reference/softcode.md#guard-on-target) test is wrong here:
the dome is a witness and reads the mover through `enactor` instead. It filters
`enactor` to real characters so that dropping a second gadget into the room, or
any other non-character arrival, never writes a spurious line. Two domes in one
room are two independent sensors, so each logs a walker once, which is correct.

### Why are the records plain data with a slice cap?

Each entry is a three-element list, `[name, verb, timestamp]`, and the timestamp
is [`now()`](../reference/softcode.md#fn-now) in epoch seconds. Storing the raw
second rather than a formatted string is deliberate, because arithmetic is the
point: `now() - stamp` at playback time gives an age that is true whenever you
read it, so the log ages itself with no ticker.

The cap is a slice. The write appends the new entry and then keeps only the tail
with [`((V('log') or []) + [entry])[-20:]`](../reference/softcode.md#fn-v), which holds the newest twenty records
and lets old ones fall off the front. An attribute that only ever grows is a
leak, so cap every log you build. (The camera's "Recording" idea in item 54
wants the same slice, and the [tripwire](050_tripwire_alarm.md) caps its own
counter the same way in spirit.)

Playback is then a loop over that list. `review` walks the records oldest first
and [`pemit`](../reference/softcode.md#fn-pemit)s one line per record, computing
the age at that moment. Sandboxed softcode runs `for` loops and comprehensions,
so rendering the log is ordinary list work.

### Why does a teleport leave a gap?

`@teleport` does not fire `ON_LEAVE`. A teleport is a placement, not a walk, so
the engine fires the arrival event (your dome logs teleporters appearing) but no
departure. The [security camera](054_security_camera.md) documents the same
asymmetry. An "entered" with no matching "left" therefore means one of two
things: they are still inside, or they left by means the dome cannot see. Real
surveillance has the same blind spot, so read your logs accordingly.

## Build it

One room worth watching, with the dome dropped where it will lie in wait:

```text
@dig The Server Vault = vault, out
vault
@create motion sensor
drop motion sensor
@desc motion sensor = A black dome in the corner. A red LED blinks twice a second, forever. REVIEW plays back its log.
```

The two witnesses come next, identical but for one word. Each guards on
`enactor` (never `target is me`, since the event targets the room), logs only a
real character, and appends-then-slices so the log stays capped at twenty:

```text
@set motion sensor/on_enter = '''
x = enactor
# ON_ENTER fires on every object in the room with the mover as enactor, and it
# targets the room, not the dome, so guard on enactor: log a real mover (a
# player or npc), never a dropped gadget.
if has_tag(x, 'player') or has_tag(x, 'npc'):
    # append the record, then slice to the newest 20 so the log cannot grow forever
    set_attr(me, 'log', ((V('log') or []) + [[name(x), 'entered', now()]])[-20:])
'''
@set motion sensor/on_leave = '''
x = enactor
if has_tag(x, 'player') or has_tag(x, 'npc'):
    set_attr(me, 'log', ((V('log') or []) + [[name(x), 'left', now()]])[-20:])
'''
```

Finally the playback command. `review` reads the log, prints a friendly line
when it is empty, and otherwise walks it oldest first with the age computed at
read time:

```text
@set motion sensor/cmd_review = '''
$review:
entries = V('log') or []
if not entries:
    pemit(enactor, 'The log is empty.')
else:
    # now() - stamp is the age in seconds, true whenever you read it
    for e in entries:
        pemit(enactor, f'[{now() - e[2]}s ago] {e[0]} {e[1]}.')
'''
```

## Try it

Have someone wander through, then read the dome:

```text
(Zeke walks in, waits, walks out; you walk in)
review
  [31s ago] Zeke entered.
  [12s ago] Zeke left.
  [3s ago] You entered.
```

The three ages vary with the wall clock; the order and the wording are what to
confirm. Now the gap, demonstrated: `@teleport` yourself out and back, and
`review` again. Your teleport *out* leaves no "left" line, while your teleport
back *in* is logged, because arrivals fire for placements and walks alike but
departures fire only for walks. Twenty records is the whole memory, so walk in
and out enough times and Zeke's visit quietly scrolls off the front of the list.

## Going further

- **Owner's eyes only.** Open `review` with a check that pages a locked-out
  message when `enactor is not owner(me)`, using
  [`owner(me)`](../reference/softcode.md#fn-owner); the log keeps recording
  either way.
- **Silent alarm splice.** The dome already has the event, so add the
  [tripwire](050_tripwire_alarm.md)'s owner page
  ([`pemit(owner(me), ...)`](../reference/softcode.md#fn-pemit)) inside
  `on_enter` and it logs and pages at once.
- **Occupancy count.** Track a single `inside` counter alongside the log, plus
  one on enter and minus one on leave, and show it in the dome's description.
  Mind the teleport gap you just learned about.
- **A wipe switch.** A `$wipe` command,
  [`set_attr(me, 'log', [])`](../reference/softcode.md#fn-set_attr), gated to the
  owner. Every surveillance state wants a way to be cleared.
