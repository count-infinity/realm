# 056. Self-Destruct Sequence

> Checklist item 56 ([now]): *cancellable wait() chains, escalating remits, secret codes*

**What you'll build:** A station master computer with a five-stage
self-destruct. It sounds a klaxon in every room of the zone, counts down
stage by stage, and offers an `abort` console that demands a secret code
from anywhere on the station. If nobody types the code in time, fire
fills every compartment.

**Concepts:** a cancellable [`wait()`](../reference/softcode.md#fn-wait)
chain where the handle is the defuse, a zone master that carries both a
station-wide alarm and a station-wide `$`-command,
[`act(..., targeting='zone')`](../reference/softcode.md#fn-act) as the
all-call, [`prompt()`](../reference/softcode.md#fn-prompt) for the code
entry, the `secret` attribute flag, and spawned proximity hazards as the
consequence.

## How it works

The finished machine has one visible switch and one hidden clock. When
the owner types `self destruct`, the master sounds a klaxon in every room
of the station and lights a countdown that re-arms itself stage by stage.
At any stage, anyone who types `abort` and enters the secret code cancels
the whole thing from wherever they are standing. If the countdown reaches
zero, the master spawns fire into every compartment. This section answers
four questions: how the countdown stays a single timer, how the alarm and
the abort both reach the whole station, how the code stays secret, and
why the fire is a spawned object rather than a line of text.

### How the countdown stays a single timer

The countdown is a chain, not a schedule. Exactly one
[`wait()`](../reference/softcode.md#fn-wait) is pending at any moment.
Each stage's script announces, decrements `count`, and schedules the
*next* stage with `wait(interval, 'trigger me/countdown')`, so aborting
never has to hunt down five separate timers, only the one in flight. That
scheduled command, `trigger me/countdown`, runs the plain `countdown`
attribute directly, the same way the [gas bomb](048_gas_bomb.md)'s fuse
runs `trigger me/detonate`; it is not a `$`-command, so no player input is
involved. `wait()` returns a **handle**, the script stashes it in
`pending`, and [`cancel_wait(handle)`](../reference/softcode.md#fn-cancel_wait)
is the entire defuse. A bomb you can wire, you can also unwire.

`wait()` is in-memory and dies with a reboot, which for a self-destruct
is the correct failure mode: a countdown that a crash silently forgets is
better than one that survives half-fired. Where a timer must persist, use
[`expire()`](../reference/softcode.md#fn-expire) instead, as the
[EMP charge](057_emp_charge.md) does.

### How the alarm and the abort reach the whole station

Rooms tagged `zone:station` make the master computer, which shares the
tag as a `zone_master`, both audible and addressable station-wide. The
`@zone/master` command sets both tags in one line. The zone then does two
jobs:

- Outbound, [`act(me, '...', targeting='zone')`](../reference/softcode.md#fn-act)
  propagates the klaxon to every room in the master's zone. This is a
  real propagated action rather than a text loop, so wards can veto it and
  a room can lock out `reach`, but for sirens it behaves as the all-call.
- Inbound, the softcode trigger search consults zone masters, so `$abort`
  on the master fires from **any** room in the zone. There are no abort
  consoles to scatter, because the zone itself is the console.

### How the code stays secret

`abort` does not parse arguments; it asks.
[`prompt()`](../reference/softcode.md#fn-prompt) captures the player's
next line into the `abort_check` callback, bound as `arg0`. The callback
runs *as the master*, so it may read the master's `code` attribute and
cancel the master's wait. The `code` attribute is flagged `secret` with
`@attr`, which makes it controller-only: a stranger's
[`get_attr`](../reference/softcode.md#fn-get_attr) reads nothing. The
guard is engine-enforced, the same way the combination hides in the
[combination safe](016_combination_safe.md).

### Why the fire is spawned, not narrated

The master cannot [`damage()`](../reference/softcode.md#fn-damage) someone
three rooms away, because damage is proximity authority. So zero hour
[`create_obj`](../reference/softcode.md#fn-create_obj)s `a sheet of
roaring flame` into every zone room, which is legal because a script
seeds objects only into rooms its owner controls. Each flame carries a
copied `blast_tick` heartbeat that burns whoever is standing there, and
each rides an [`expire()`](../reference/softcode.md#fn-expire) fuse so the
fires gutter out on their own. It is the same prototype-copy shape the
[gas bomb](048_gas_bomb.md) uses for its clouds.

`blast_tick` runs on each flame's own
[`script_ticker`](../reference/softcode.md#fn-attach_behavior) heartbeat,
so it is not a room-wide reactive hook and needs no `target` guard. It
does filter its loop over [`contents(loc(me))`](../reference/softcode.md#fn-contents)
to players and NPCs, so the fire never tries to burn an exit or the
sibling flame.

## Build it

The station is two compartments sharing one zone:

```text
@dig Reactor Core = core, out
core
@zone here = station
@dig Cargo Bay = bay, core
bay
@zone here = station
core
```

Now the master computer. `@zone/master` crowns it the zone's brain in one
line, tagging it both `zone_master` and `zone:station`. The interval is
the seconds between stages, the code is the abort phrase, and `@attr`
flags that code `secret` so only a controller can read it back:

```text
@create Station Brain
drop Station Brain
@desc Station Brain = A pillar of screens and switches. A red panel reads: SELF DESTRUCT. A smaller one reads: ABORT.
@zone/master Station Brain = station
@set Station Brain/interval = 10
@set Station Brain/code = ZEBRA-9
@attr Station Brain/code = secret
```

Initiation is owner-only and refuses to double-arm. It announces
station-wide, lights the first `wait()`, and keeps the handle so the abort
can find it:

```text
@set Station Brain/cmd_selfdestruct = '''
$self destruct:
if enactor is not owner(me):  # command authority: only the owner may arm
    pemit(enactor, 'The console demands command authority.')
elif V('pending'):  # one wait is pending at a time; refuse a second chain
    pemit(enactor, 'The countdown is already running.')
else:
    set_attr(me, 'count', 5)
    act(me, f'KLAXON: SELF-DESTRUCT SEQUENCE INITIATED. {5 * V("interval", 10)} SECONDS TO ZERO. ABORT requires command code.', targeting='zone')
    set_attr(me, 'pending', wait(V('interval', 10), 'trigger me/countdown'))  # stash the handle so abort can cancel it
'''
```

Each stage of the chain announces, decrements the counter, and re-arms
the single pending wait. Stage zero hands over to `boom` instead:

```text
@set Station Brain/countdown = '''
n = V('count', 0) - 1
if n <= 0:
    eval_attr(me, 'boom')  # zero hour: hand over to the detonation
else:
    set_attr(me, 'count', n)
    act(me, f'SELF-DESTRUCT IN {n * V("interval", 10)} SECONDS.', targeting='zone')
    set_attr(me, 'pending', wait(V('interval', 10), 'trigger me/countdown'))  # re-arm the one pending wait
'''
```

The `abort` command asks for the code when the countdown is armed, and
says so plainly when it is not. It is a single conditional, so it stays
one line:

```text
@set Station Brain/cmd_abort = $abort: prompt(enactor, 'Enter the abort code:', 'abort_check') if V('pending') else pemit(enactor, 'The self-destruct is not armed.')
```

The callback that `prompt()` runs checks the captured line against the
secret code. A match cancels the one pending wait and clears the counter;
anything else keeps the clock running:

```text
@set Station Brain/abort_check = '''
if trim(arg0) == str(V('code')):  # arg0 is the player's next line, captured by prompt()
    cancel_wait(V('pending'))  # the one pending wait is the whole countdown
    del_attr(me, 'pending')
    del_attr(me, 'count')
    act(me, f'KLAXON: SELF-DESTRUCT ABORTED. Authorization: {name(enactor)}.', targeting='zone')
else:
    pemit(enactor, 'INVALID CODE. The countdown continues.')
'''
```

The heartbeat that each flame will carry sweeps its own room every tick
and burns the living things in it. It runs on the flame's ticker, not as
a room-wide reactive hook, so it needs no target guard, but it does filter
to players and NPCs:

```text
@set Station Brain/blast_tick = '''
for o in contents(loc(me)):
    if has_tag(o, 'player') or has_tag(o, 'npc'):  # skip exits, items, the sibling flame
        pemit(o, 'Fire roars over you!')
        damage(o, roll('2d6'))  # proximity authority: the flame is in the room
'''
```

And zero hour spawns a flame in every compartment, copies the heartbeat
onto each, gives each a one-second ticker, and sets a self-clearing fuse:

```text
@set Station Brain/boom = '''
del_attr(me, 'pending')
del_attr(me, 'count')
act(me, 'The deck heaves. Fire tears through every compartment!', targeting='zone')
for r in zone_rooms('station'):
    b = create_obj('a sheet of roaring flame', location=r)
    if b:  # create_obj returns None for a room the owner does not control
        set_attr(b, 'on_tick', V('blast_tick'))  # copy the heartbeat onto each flame
        attach_behavior(b, 'script_ticker', interval=1)
        expire(b, 20)  # persistent fuse: the fire gutters out on its own, even across a reboot
'''
```

## Try it

From the Reactor Core, as the owner, start the sequence and the klaxon
carries across the whole station:

```text
> self destruct
(everywhere on station) KLAXON: SELF-DESTRUCT SEQUENCE INITIATED. 50 SECONDS TO ZERO. ABORT requires command code.
```

Someone standing in the Cargo Bay hears every stage, `SELF-DESTRUCT IN 40
SECONDS.` then `30` and so on, and can answer from right there. A wrong
code keeps the clock running; the right one stops it:

```text
> abort
Enter the abort code:
> WOMBAT
INVALID CODE. The countdown continues.

> abort
Enter the abort code:
> ZEBRA-9
(everywhere) KLAXON: SELF-DESTRUCT ABORTED. Authorization: Zeke.
```

Let it run instead, and at zero every compartment reads `The deck heaves.
Fire tears through every compartment!`. The flames then take over,
burning anyone present each tick until their `expire()` fuse clears them.
With nothing pending, `abort` answers `The self-destruct is not armed.`,
and a stranger who tries to read the code off the console gets nothing,
because the attribute is `secret`.

## Going further

- **Escalating urgency.** Stage the message too: switch on `n` to add
  `EVACUATE. EVACUATE.` under 20 seconds, or `ansi('rh', ...)` the final
  stage red.
- **Two-man rule.** Require a second officer. A first `$turn key` sets a
  `key_turned` timestamp, and `cmd_selfdestruct` refuses unless it is
  under 30 seconds old, using the `now()` arithmetic from the
  [motion sensor](055_motion_sensor.md)'s timestamps.
- **Blast doors.** `boom` currently torches every zone room. Skip rooms
  whose exits are all `closed`, or spawn flame only along open paths from
  the core; the [gas bomb](048_gas_bomb.md)'s exit walk slots straight in.
- **Wrong-code alarms.** The failed branch of `abort_check` can page the
  owner, the way the [tripwire alarm](050_tripwire_alarm.md) pages: three
  wrong codes is a story beat, not just a typo.
```