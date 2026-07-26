# 029. Timed Door

> Checklist item 29 ([now]): *wait()/cancel_wait, state reversion, atomicity*

**What you'll build:** A blast door that only a wall switch opens, and
thirty seconds later it slams itself shut. Press the switch twice and the
countdown extends instead of slamming early: one door, any number of
presses, exactly one slam.

**Concepts:** a `$`-command trigger that drives door state (the `closed`
tag, written raw), [`wait()`](../reference/softcode.md#fn-wait) for short
mechanical timers (and why not
[`expire()`](../reference/softcode.md#fn-expire)), and a **pending-ticket
counter**, the small piece of state that makes stacked timers collapse into
a single reversion instead of racing each other.

## How it works

The finished door is an ordinary exit wearing the `closed` tag, with a wall
switch beside it. Pressing the switch strips the tag so the door opens,
then schedules a timer that puts the tag back. Everything interesting is
one hazard: pressing twice must not slam the door twice. This section
covers why the door itself needs no scripting, which of REALM's two timers
fits a thirty-second relay, and how a small counter turns any number of
presses into exactly one slam.

**The door is stock parts.** An exit carrying the `closed` tag refuses
traversal and prints its `closed_msg`, so the door is a solved problem the
moment you tag it (the [lockable door](025_lockable_door.md) leans on the
same convention). The switch's script does the rest by writing that tag
directly, [`remove_tag`](../reference/softcode.md#fn-remove_tag) to open and
[`add_tag`](../reference/softcode.md#fn-add_tag) to shut. A script runs with
its object's owner's authority, and you built both the switch and the door,
so the switch may write the door's state. No scripting lives on the door at
all.

**Which timer, `wait()` or `expire()`?** REALM has two schedulers and they
are not interchangeable.
[`wait(seconds, command)`](../reference/softcode.md#fn-wait) is an in-memory
countdown, exact and cheap, that dies with a restart.
[`expire(obj, seconds)`](../reference/softcode.md#fn-expire) is a persistent
lifetime that survives reboots, but when it fires it destroys the object
unless the handler clears the timestamp. For a thirty-second mechanical
relay `wait()` is the honest choice: the worst a badly timed reboot can do
is leave the door open until someone presses the switch again, whereas
bending `expire()` to the job means hanging a self-destruct on your door and
remembering to defuse it every time the handler runs. Short and expendable
wants `wait()`; long-lived and must-not-leak wants `expire()`. (The
[gas bomb](048_gas_bomb.md) uses both, side by side, for exactly these
reasons.)

**Why two presses must not mean two slams.** The naive version has every
press do open plus `wait(30, close)`. Press at t=0 and again at t=20 and two
countdowns are now in flight: the first slams the door at t=30, ten seconds
into the second press's window, and the second slams again at t=50, perhaps
onto someone who stepped through at t=45. A timer you cannot cancel from
inside has to be defused by state. Each press takes a ticket with
[`incr('pending')`](../reference/softcode.md#fn-incr), each slam retires one
with [`decr('pending')`](../reference/softcode.md#fn-decr) (which hands back
the new count), and only the slam that retires the last ticket actually
closes the door. A stale timer wakes, sees a newer ticket still
outstanding, and goes back to sleep.
[`cancel_wait()`](../reference/softcode.md#fn-cancel_wait) solves the same
race a different way, by keeping the handle `wait()` returns and calling the
old timer off before scheduling a fresh one; the ticket counter is the
version that stays correct even for a timer you did not schedule yourself,
and the two compose.

## Build it

Dig the door first, closed, with a refusal line that points at the switch.
`blast door` has no compass opposite, so the vault's only door is this one
face:

```text
@dig Generator Room
@teleport me = Generator Room
@dig Reactor Vault = blast door
@tag blast door = closed
@set blast door/closed_msg = The blast door is sealed. There must be a switch.
```

That door will slam behind people, so give the vault a humble way back out
(a slammed door that strands players is the
[one-way exit](028_one_way_exit.md)'s cautionary tale):

```text
@teleport me = Reactor Vault
@open service hatch = Generator Room
@teleport me = Generator Room
```

Now the switch. Its `delay` is data, so the countdown is tunable without
touching the scripts. The scripts themselves are `'''` multi-line blocks
(see [multi-line input](../guides/world-management.md#multi-line-input-heredocs)):

```text
@create pressure switch
drop pressure switch
@set pressure switch/delay = 30
```

The press script takes a ticket, opens the door (or just resets the
countdown if it is already open), and schedules this press's slam. It reads
the door with [`get`](../reference/softcode.md#fn-get) and announces to the
room with [`remit`](../reference/softcode.md#fn-remit) at
[`loc(me)`](../reference/softcode.md#fn-loc):

```text
@set pressure switch/cmd_press = '''
$press switch:
d = get('blast door')
incr('pending')                  # a ticket per press; pending counts timers in flight, so it starts at 0
if has_tag(d, 'closed'):
    remove_tag(d, 'closed')      # raw state, not the close command, so it fires no hooks
    remit(loc(me), 'Hydraulics whine, the blast door grinds open. Somewhere a countdown starts ticking.')
else:
    remit(loc(me), 'Clunk. The countdown resets.')
wait(V('delay', 30), 'trigger me/slam')   # trigger me/slam runs the switch's own slam script when the timer fires
'''
```

The slam script retires a ticket, and only the last one standing gets to
close anything:

```text
@set pressure switch/slam = '''
d = get('blast door')
p = decr('pending')              # retire one ticket; decr hands back the NEW count
if p <= 0 and not has_tag(d, 'closed'):
    add_tag(d, 'closed')
    remit(loc(me), 'WHAM! The blast door slams shut.')
'''
```

The `p <= 0` test is the ticket check: a stale timer finds `p` still above
zero and does nothing. The
[`has_tag`](../reference/softcode.md#fn-has_tag) test,
`not has_tag(d, 'closed')`, is the other half of atomicity, because if
someone `close`d the door by hand mid-window, the expiring timer must not
slam a door that is already shut.

## Try it

Press once and the door opens; the countdown runs in the background:

```text
> blast door
The blast door is sealed. There must be a switch.

> press switch
Hydraulics whine, the blast door grinds open. Somewhere a countdown starts ticking.
```

Press again before the first countdown ends and the door stays open while
the count climbs. Thirty seconds after the SECOND press the room hears one
slam, at the later deadline:

```text
> press switch
Clunk. The countdown resets.

(about thirty seconds after the second press)
WHAM! The blast door slams shut.
```

Two countdowns were genuinely scheduled, but the room hears exactly one
slam. `@examine pressure switch` mid-window shows `pending` climbing as you
press and falling as each timer retires. Step through the open door and it
slams behind you, sealing the vault until the next press:

```text
> press switch
> blast door
(you are in the Reactor Vault, and behind you) WHAM! The blast door slams shut.

> service hatch
(the crawl back out to the Generator Room)
```

## Going further

- **Restart-proof variant.** If this door guards something that must never
  stay open across a reboot, move the timer onto the door with
  [`expire(d, 30)`](../reference/softcode.md#fn-expire) on press, and give
  the door
  `@set blast door/on_expire = add_tag(me, 'closed'); del_attr(me, 'expires_at'); remit(loc(me), 'WHAM!')`.
  The [`del_attr`](../reference/softcode.md#fn-del_attr) is load-bearing:
  `expires_at` is the only thing the world tick reads to decide death, so an
  `ON_EXPIRE` that leaves the timestamp past-due gets its object destroyed.
  Clear it (or push it out with `expire(me, 999)`) and the door survives its
  own slam.
- **`cancel_wait()` variant.** Stash the handle,
  [`set_attr(me, 'timer', wait(...))`](../reference/softcode.md#fn-set_attr),
  and [`cancel_wait`](../reference/softcode.md#fn-cancel_wait) it on the next
  press so only one timer is ever alive; the ticket check then never sees a
  stale wake-up. Both patterns compose.
- **Both faces.** This door is one face; for a two-faced timed door, pair
  the exits and mirror their state as the
  [lockable door](025_lockable_door.md) does, and have press and slam write
  both faces.
- **Alarm coupling.** The slam script is just softcode, so add
  [`act(...)`](../reference/softcode.md#fn-act) to a guard post, or have the
  [security camera](054_security_camera.md) relay the slam.
