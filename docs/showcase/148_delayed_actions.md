# 148. Delayed actions

> Checklist item 148 ([now]): *wait()/cancel_wait idioms, the persistence caveat*

**What you'll build:** A ceremony bell that rings a timed three-peal
sequence, one ring, a pause, two rings, a pause, a final ring, that you can
`silence` mid-chain, and that refuses to start a second ceremony over a
running one. A compact tour of every `wait()` idiom.

**Concepts:** [`wait()`](../reference/softcode.md#fn-wait) as REALM's
in-memory delay, *chaining* (each step schedules the next), the *stored
handle* so a timer can be cancelled with
[`cancel_wait()`](../reference/softcode.md#fn-cancel_wait), the
*generation-counter* pattern for overlapping timers, and the caveat that
governs all of them: what `wait()` loses on reboot.

## How it works

The finished bell holds exactly one pending timer at any moment and one
stored handle pointing at it. A ring fires the current peal and arms the
next; the handle is both the off switch and the "is a ceremony running?"
flag. This section answers three questions: what `wait()` actually
schedules, why the chain keeps only one timer alive, and how the stored
handle serves double duty.

### What does `wait()` schedule?

[`wait(seconds, command)`](../reference/softcode.md#fn-wait) is the
short-timer primitive. It runs a script command as the executor after an
exact delay, on its own async timer, so a 0.15-second fuse fires at 0.15
seconds rather than rounding up to the next heartbeat. It is **in-memory**:
a reboot cancels every pending wait. That is the whole trade against
[`expire()`](../reference/softcode.md#fn-expire), which stores its deadline
on the object and survives a restart ([tutorial
152](152_persistent_timers.md)). Reach for `wait()` when the delay is short
and expendable, and for `expire()` when it must live through a reboot.

### Why keep only one timer in flight?

Rather than schedule all three peals up front, each step does its ring and
schedules only the *next* one, `wait(2, 'trigger me/step_2')`. So there is
never a thicket of timers to reason about: exactly one is in flight, and it
is the one whose handle we keep. This is the self-destruct's countdown shape
([056](056_self_destruct.md)) in miniature.

### How the stored handle serves as both off switch and running-flag

`wait()` returns a handle string; the step stashes it in `pending` with
[`set_attr`](../reference/softcode.md#fn-set_attr). `silence` is then just
[`cancel_wait(V('pending'))`](../reference/softcode.md#fn-cancel_wait): a
timer you can wire, you can unwire. (`cancel_wait` succeeds only for a
controller of the object that scheduled the timer, so the handle alone is
not authority.) The same handle doubles as a running-flag, because `begin`
refuses to start when `pending` is already set.

### When a handle is out of reach, count generations instead

`cancel_wait` works because *we* scheduled the timer and kept its handle.
For timers you cannot reach, such as many presses stacking many independent
fuses, the robust idiom is a **generation counter**: each start takes a
ticket (`gen += 1`), each fire retires one, and only the fire that retires
the *last* ticket acts. Stale timers wake, see a newer generation, and go
back to sleep. That is the core of the [timed door
(029)](029_timed_door.md); read it there in full. The two idioms compose:
keep a handle when you own the timer, count generations when you do not.

## Build it

The chamber and the bell. The delay lives in a `gap` attribute, so the tempo
is one number to tune:

```text
@dig Ritual Chamber = ritual, out
ritual
@create ceremony bell
drop ceremony bell
@desc ceremony bell = A tall bronze bell on a rope. RING BELL begins the rite; SILENCE BELL stops it.
@set ceremony bell/gap = 2
```

The first two steps share one shape: each rings with
[`remit`](../reference/softcode.md#fn-remit) to everyone in the bell's
location ([`loc`](../reference/softcode.md#fn-loc)), then arms the next peal
`gap` seconds out and re-stashes the returned handle. The
[`V('gap', 2)`](../reference/softcode.md#fn-v) read falls back to 2 if the
attribute is missing:

```text
@set ceremony bell/step_1 = '''
remit(loc(me), 'The bell rings once. A hush falls over the chamber.')
# arm the next peal and stash its handle so silence can cancel it
set_attr(me, 'pending', wait(V('gap', 2), 'trigger me/step_2'))
'''
@set ceremony bell/step_2 = '''
remit(loc(me), 'The bell rings twice. The candles gutter.')
set_attr(me, 'pending', wait(V('gap', 2), 'trigger me/step_3'))
'''
```

The final step rings, then clears `pending` with
[`del_attr`](../reference/softcode.md#fn-del_attr) to end the chain and drop
the running-flag:

```text
@set ceremony bell/step_3 = '''
remit(loc(me), 'The bell rings a third and final time. It is done.')
del_attr(me, 'pending')
'''
```

The `begin` verb guards against a double ceremony: if `pending` is set a rite
is already underway, otherwise it evaluates `step_1` with
[`eval_attr`](../reference/softcode.md#fn-eval_attr) to start the chain. A
`$`-command dispatches to whoever types the pattern, so it needs no `target`
guard:

```text
@set ceremony bell/cmd_begin = '''
$ring bell:
if V('pending'):
    pemit(enactor, 'A ceremony is already underway.')
else:
    eval_attr(me, 'step_1')
'''
```

The `silence` verb cancels the one pending timer, clears the flag, and
announces the stop; with nothing pending it reports so privately with
[`pemit`](../reference/softcode.md#fn-pemit):

```text
@set ceremony bell/cmd_silence = '''
$silence bell:
if V('pending'):
    cancel_wait(V('pending'))
    del_attr(me, 'pending')
    remit(loc(me), 'The bell is stilled mid-peal.')
else:
    pemit(enactor, 'Nothing is ringing.')
'''
```

## Try it

A full peal runs itself once you start it:

```text
> ring bell
The bell rings once. A hush falls over the chamber.
  (2s) The bell rings twice. The candles gutter.
  (2s) The bell rings a third and final time. It is done.
```

Start it, then stop it mid-chain, then start it cleanly again:

```text
> ring bell
The bell rings once. A hush falls over the chamber.
> silence bell
The bell is stilled mid-peal.
  (the second and third peals never come)
> ring bell
The bell rings once. A hush falls over the chamber.
```

Typing `ring bell` a second time while a ceremony is running earns *A
ceremony is already underway.*, because the stored handle is the guard:

```text
> ring bell
The bell rings once. A hush falls over the chamber.
> ring bell
A ceremony is already underway.
```

## The reload caveat

Every `wait()` above is in-memory. If the server reboots between the first
and last peal, the pending timer is gone, and because `pending` is a stored
attribute it stays set with no timer behind it, so `begin` would report "a
ceremony is already underway" indefinitely. Three ways to handle it, in
rising order of effort:

1. **Accept it.** For a two-second flourish, a reboot mid-peal is invisible,
   and on boot a stale `pending` is a one-line cleanup.
2. **Guard on read.** Pair `pending` with an *absolute deadline*
   (`set_attr(me, 'until', now() + 6)`); `begin` treats `pending` as stale
   once [`now()`](../reference/softcode.md#fn-now) passes `until`. This
   survives the reboot without persistent timers, using the same `now()`
   arithmetic as [152](152_persistent_timers.md).
3. **Use `expire()`** for anything that genuinely must resume. That is the
   persistent path, and the whole subject of [tutorial
   152](152_persistent_timers.md).

The rule of thumb: use `wait()` for mechanical, expendable, sub-minute
delays, and `expire()` the moment a reboot losing the timer would be a bug.

## Going further

- **A skippable cutscene:** `wait()`-paced `remit()` lines with a `$skip`
  that `cancel_wait`s the chain. The [cutscene
  (203)](203_cutscenes.md) is this bell, grown up.
- **Belt-and-braces:** combine the stored handle *and* a generation counter,
  as [029](029_timed_door.md) discusses, for a timer that stays correct even
  if a handle ever goes missing.
- **Staggered volleys:** schedule several waits at once (not a chain) for
  overlapping effects, such as a firework finale, and reach for the
  generation counter to keep their cleanup sane.
