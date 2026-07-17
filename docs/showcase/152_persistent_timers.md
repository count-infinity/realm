# 152. Reboot-surviving timers

> Checklist item 152 — [now] — *expire() persistence vs wait(), ON_EXPIRE, absolute-deadline storage*

**What you'll build:** A galley egg timer you wind with `set timer 5`.
It counts down, rings when it lapses, and — the whole point — **keeps
counting across a server reboot**, because its deadline lives on the
object, not in memory. This is the canonical persistence tutorial the
rest of the category defers to.

**Concepts:** the two schedulers and why only one survives a restart
(`wait()` in-memory vs `expire()` persistent), `ON_EXPIRE` as an event
the object *survives* by clearing its own timestamp, and **absolute-
deadline storage** (`now() + N`) so "time remaining" is reboot-proof.

## How it works: two schedulers, one survivor

REALM gives you two ways to make something happen later, and the *only*
difference that matters here is what a reboot does to them:

| | `wait(sec, cmd)` | `expire(obj, sec)` |
|---|---|---|
| Lives in | memory (an async timer) | a `db.expires_at` attribute on the object |
| Fires | the command, as the executor | `ON_EXPIRE` on the object, **then destroys it** |
| Survives reboot? | **No** — pending waits are forgotten | **Yes** — the world's housekeeping task re-reads `expires_at` and fires it whenever it's due |
| Use for | short, expendable, mechanical delays ([148](148_delayed_actions.md)) | anything a reboot losing would be a *bug* |

`wait()` is memory; `expire()` is state. Because `expire()`'s countdown
is a plain attribute, it doesn't need to be "re-armed" on boot — the
reaper just compares `now()` to the stored deadline and acts. **That is
the entire reason it survives**, and it's why every long-lived timer in
the showcase — the [gas cloud (048)](048_gas_bomb.md), the [message in a
bottle (083)](083_message_in_bottle.md) — is an `expire()`.

**`ON_EXPIRE` destroys by default; the handler survives by clearing the
deadline.** When `expires_at` lapses, the reaper fires `ON_EXPIRE` and
*then destroys the object* — unless the hook has cleared or pushed out
`expires_at`. For a smoke cloud that's perfect (ring the alarm, vanish).
For an egg timer we want to *keep* the timer, so its `ON_EXPIRE`
`del_attr`s `expires_at` — the survival move first seen on
[083](083_message_in_bottle.md)'s bottle. Miss that `del_attr` and the
timer rings once and disintegrates.

**Absolute deadlines make "remaining" reboot-proof.** Alongside the
engine's `expires_at`, we stamp our own `rings_at = now() + seconds`.
`now()` is wall-clock epoch seconds, so a `check` that reports
`rings_at - now()` is correct *forever* — five minutes into a countdown,
reboot the server, and `check` still reads ~the right number, because the
deadline is an absolute moment in time, not a counter that paused. This
absolute-deadline idiom is how you'd anchor [144](144_game_calendar.md)'s
calendar to keep flowing across downtime.

## Build it

The galley and the timer:

```text
@dig Galley = galley, out
galley
@create egg timer
drop egg timer
@desc egg timer = A brass mechanical timer. SET TIMER <minutes> winds it; CHECK TIMER reads the dial.
```

`set timer` arms both clocks — the persistent `expire()` and our
absolute `rings_at`. `check` reports the remaining seconds off the
absolute deadline. `ON_EXPIRE` rings and clears the timestamp so the
timer lives to be wound again:

```text
@set egg timer/cmd_set = $set timer *: (pemit(enactor, 'Give it whole minutes.') if not trim(arg0).isdigit() else (set_attr(me, 'rings_at', now() + int(arg0) * 60), expire(me, int(arg0) * 60), pemit(enactor, 'The timer winds up with a ratchet and begins ticking.')))
@set egg timer/cmd_check = $check timer: pemit(enactor, 'The timer is not set.') if not V('rings_at') else pemit(enactor, str(max(0, V('rings_at', 0) - now())) + ' seconds remain.')
@set egg timer/on_expire = del_attr(me, 'expires_at'); del_attr(me, 'rings_at'); remit(loc(me), 'BRRRING! The egg timer goes off, rattling on the counter.')
```

The `del_attr(me, 'expires_at')` in `on_expire` is load-bearing: it's the
difference between a timer you can reuse and a timer that self-destructs
on its first ring.

## Try it

```text
set timer 5      -> The timer winds up with a ratchet and begins ticking.
check timer      -> 300 seconds remain.
```

Wait (or, in a test, forge the clock forward past the deadline). When it
lapses the housekeeping task fires the ring:

```text
   -> BRRRING! The egg timer goes off, rattling on the counter.
check timer      -> The timer is not set.
```

And the timer is **still there** on the counter, ready to wind again —
because `on_expire` cleared its own deadline before the reaper could
reap it. The reboot proof is structural: `expires_at` and `rings_at` are
both persisted attributes, so a restart mid-countdown loses nothing —
the reaper picks the countdown back up from the stored deadline, exactly
as it does for the [message in a bottle (083)](083_message_in_bottle.md)
adrift at sea. Contrast a `wait()`-based timer ([148](148_delayed_actions.md)),
which a restart forgets entirely — the right trade only for delays you're
happy to lose.

## Going further

- **A snooze:** an `ON_EXPIRE` that *renews* instead of clears —
  `expire(me, 60)` — rings, then rings again a minute later until
  someone `stop`s it (the gas cloud's "step itself down" trick).
- **Persistent cooldowns:** the absolute-deadline idiom is how ability
  cooldowns survive a reboot — store `ready_at = now() + cd` and gate on
  `now() >= ready_at`, no timer object at all.
- **A reboot-proof calendar:** anchor [144](144_game_calendar.md)'s clock
  to `now()` — store an `origin` epoch and compute the date as a function
  of `now() - origin`, so game-time keeps flowing while the server sleeps.
- **When *not* to persist:** a 30-second blast door ([029](029_timed_door.md))
  or a self-destruct ([056](056_self_destruct.md)) *should* be forgotten
  on reboot — persistence is a tool, not a virtue. Choose it when losing
  the timer is a bug, not by default.
