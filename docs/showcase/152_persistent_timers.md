# 152. Reboot-surviving timers

> Checklist item 152 ([now]): *timers that resume after a server restart; a persistent expire() deadline survives where an in-memory wait() is forgotten*

**What you'll build:** A galley egg timer you wind with `set timer 5`. It counts
down, rings when it lapses, and, the whole point, keeps counting across a server
reboot, because its deadline lives on the object rather than in memory. This is
the persistence pattern the rest of this category refers back to.

**Concepts:** the two schedulers and why only one survives a restart
([`wait()`](../reference/softcode.md#fn-wait) in memory versus
[`expire()`](../reference/softcode.md#fn-expire) persistent),
[`ON_EXPIRE`](../reference/softcode.md#lifecycle-hooks) as an event the object
*survives* by clearing its own timestamp, the
[`target` guard](../reference/softcode.md#guard-on-target) that keeps one
timer's ring from disturbing another, and **absolute-deadline storage**
([`now()`](../reference/softcode.md#fn-now) `+ N`) so "time remaining" stays
correct across downtime.

## How it works: two schedulers, one survivor

The finished timer holds two stored numbers and one reaction. Winding it stamps
a deadline both on the engine (`expires_at`) and on our own attribute
(`rings_at`); reading it subtracts the current time from that deadline; and when
the deadline lapses a single hook rings the alarm and clears the deadline so the
timer stays put. This section answers three questions: why one scheduler
survives a reboot when the other does not, how the timer lives to ring a second
time, and how "time remaining" stays honest across downtime.

REALM gives you two ways to make something happen later, and the only difference
that matters here is what a reboot does to them:

| | `wait(sec, cmd)` | `expire(obj, sec)` |
|---|---|---|
| Lives in | memory (an async timer) | a `db.expires_at` attribute on the object |
| Fires | the command, as the executor | `ON_EXPIRE` on the object, then destroys it |
| Survives reboot? | **No**, pending waits are forgotten | **Yes**: the world's housekeeping task re-reads `expires_at` and fires it whenever it is due |
| Use for | short, expendable, mechanical delays ([148](148_delayed_actions.md)) | anything a reboot losing would be a *bug* |

### Why does `expire()` survive a reboot when `wait()` does not?

`wait()` is memory; `expire()` is state. Because `expire()`'s countdown is a
plain persisted attribute, it needs no re-arming on boot: the housekeeping task
compares `now()` to the stored deadline and acts. That is the entire reason it
survives, and it is why every long-lived timer in the showcase, the
[gas cloud (048)](048_gas_bomb.md) and the
[message in a bottle (083)](083_message_in_bottle.md), is an `expire()`.

### How does the timer live to ring a second time?

`ON_EXPIRE` destroys by default, and the handler survives by clearing the
deadline. When `expires_at` lapses, the reaper fires `ON_EXPIRE` and then
destroys the object, unless the hook has cleared or pushed out `expires_at`. For
a smoke cloud that default is perfect: ring the alarm, vanish. For an egg timer
we want to *keep* the timer, so its `ON_EXPIRE` runs
[`del_attr`](../reference/softcode.md#fn-del_attr) on `expires_at`. Leave that
`del_attr` out and the timer rings once and disintegrates.

`ON_EXPIRE` reaches every object in the room, not only the one whose deadline
lapsed, so the hook opens with `if target is me:` and reacts only to its own
expiry. Without that guard, a second timer on the same counter would clear its
own state the moment a neighbor rang. This is the standard reactive-hook guard
described under [Guard on `target`](../reference/softcode.md#guard-on-target),
and the `is` is an identity check, not `==`.

### How does "time remaining" stay right across a reboot?

Alongside the engine's `expires_at`, we stamp our own `rings_at = now() + N`.
Because `now()` is wall-clock epoch seconds, a `check` that reports
`rings_at - now()` stays correct across a restart: five minutes into a
countdown you can reboot the server and `check` still reads about the right
number, because the deadline is an absolute moment in time rather than a counter
that paused. The same absolute-deadline idiom anchors
[144](144_game_calendar.md)'s calendar so it keeps flowing across downtime.

## Build it

Dig the galley, step into it, and drop a timer with a self-describing look:

```text
@dig Galley = galley, out
galley
@create egg timer
drop egg timer
@desc egg timer = A brass mechanical timer. SET TIMER <minutes> winds it; CHECK TIMER reads the dial.
```

`set timer` reads a whole number of minutes, refuses anything else with
[`trim`](../reference/softcode.md#fn-trim), then arms both clocks: the engine's
persistent [`expire()`](../reference/softcode.md#fn-expire) and our own absolute
`rings_at`, stamped with [`set_attr`](../reference/softcode.md#fn-set_attr):

```text
@set egg timer/cmd_set = '''
$set timer *:
if not trim(arg0).isdigit():
    pemit(enactor, 'Give it whole minutes.')
else:
    minutes = int(arg0)
    set_attr(me, 'rings_at', now() + minutes * 60)
    expire(me, minutes * 60)
    pemit(enactor, 'The timer winds up with a ratchet and begins ticking.')
'''
```

`check` reports the seconds left by subtracting `now()` from the stored
deadline, so the answer is computed fresh on every read rather than counted down
in memory, and [`pemit`](../reference/softcode.md#fn-pemit) shows it to the
reader alone:

```text
@set egg timer/cmd_check = '''
$check timer:
if not V('rings_at'):
    pemit(enactor, 'The timer is not set.')
else:
    remaining = max(0, V('rings_at', 0) - now())
    pemit(enactor, str(remaining) + ' seconds remain.')
'''
```

When the deadline lapses the housekeeping task fires `ON_EXPIRE`. The guard keeps
the hook reacting only to its own expiry, clearing both stamps so the reaper
keeps the timer, and [`remit`](../reference/softcode.md#fn-remit) rings the whole
galley:

```text
@set egg timer/on_expire = '''
if target is me:
    # clear the deadline first so the reaper keeps the timer instead of destroying it
    del_attr(me, 'expires_at')
    del_attr(me, 'rings_at')
    remit(loc(me), 'BRRRING! The egg timer goes off, rattling on the counter.')
'''
```

The `del_attr(me, 'expires_at')` is load-bearing: it is the difference between a
timer you can wind again and a timer that self-destructs on its first ring.

## Try it

```text
set timer 5      -> The timer winds up with a ratchet and begins ticking.
check timer      -> 300 seconds remain.
```

Wait (or, in a test, forge the clock forward past the deadline). When it lapses
the housekeeping task fires the ring:

```text
   -> BRRRING! The egg timer goes off, rattling on the counter.
check timer      -> The timer is not set.
```

The timer is **still there** on the counter, ready to wind again, because
`on_expire` cleared its own deadline before the reaper could reap it. The reboot
proof is structural: `expires_at` and `rings_at` are both persisted attributes,
so a restart mid-countdown loses nothing, and the reaper picks the countdown
back up from the stored deadline, exactly as it does for the
[message in a bottle (083)](083_message_in_bottle.md) adrift at sea. A
`wait()`-based timer ([148](148_delayed_actions.md)) is forgotten by a restart
instead, the right trade only for delays you are happy to lose.

## Going further

- **A snooze:** an `ON_EXPIRE` that *renews* instead of clears,
  `expire(me, 60)`, rings, then rings again a minute later until someone
  `stop`s it (the gas cloud's step-itself-down trick).
- **Persistent cooldowns:** the absolute-deadline idiom is how ability cooldowns
  survive a reboot. Store `ready_at = now() + cd` and gate on
  `now() >= ready_at`, with no timer object at all.
- **A reboot-proof calendar:** anchor [144](144_game_calendar.md)'s clock to
  `now()`, storing an `origin` epoch and computing the date as a function of
  `now() - origin`, so game-time keeps flowing while the server sleeps.
- **When *not* to persist:** a 30-second blast door
  ([029](029_timed_door.md)) or a self-destruct ([056](056_self_destruct.md))
  *should* be forgotten on reboot. Persistence is a tool, not a virtue; choose it
  when losing the timer is a bug.
