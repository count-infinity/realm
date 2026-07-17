# 148. Delayed actions

> Checklist item 148 — [now] — *wait() chains, stored handles, cancel_wait, generation counters, reload caveat*

**What you'll build:** A ceremony bell that rings a timed three-peal
sequence — one ring, a pause, two rings, a pause, a final ring — that you
can `silence` mid-chain, and that refuses to start a second ceremony over
a running one. A compact tour of every `wait()` idiom.

**Concepts:** `wait()` as REALM's in-memory delay, **chaining** (each
step schedules the next), the **stored handle** so a timer can be
cancelled, `cancel_wait()`, the **generation-counter** pattern for
overlapping timers, and — the caveat that governs all of them — what
`wait()` loses on reload.

## How it works

**`wait(seconds, command)` is the short-timer primitive.** It runs a
script command as the executor after an exact delay — its own async timer
on a live server, precise to the tenth of a second. It is **in-memory**:
a reboot forgets every pending wait. That is the whole trade against
`expire()` (persistent, [tutorial 152](152_persistent_timers.md)) — short
and expendable versus long-lived and must-survive.

**A chain is one pending timer at a time.** Rather than schedule all
three peals up front, each step does its ring and schedules only the
*next* (`wait(2, 'trigger me/step_2')`). So there is never a thicket of
timers to reason about — exactly one is in flight, and it's the one whose
handle we keep. This is the self-destruct's countdown shape
([056](056_self_destruct.md)) in miniature.

**The stored handle is the off switch.** `wait()` returns a handle
string; stash it in `pending`. `silence` is then just `cancel_wait(
V('pending'))` — a timer you can wire, you can unwire. The
same handle doubles as a "is a ceremony running?" flag: `begin` refuses
if `pending` is set.

**When you can't cancel, count generations instead.** `cancel_wait`
works because *we* scheduled the timer and kept its handle. For timers
you can't reach — many presses stacking many independent fuses — the
robust idiom is a **generation counter**: each start takes a ticket
(`pending += 1`), each fire retires one, and only the fire that retires
the *last* ticket acts; stale timers wake, see a newer generation, and go
back to sleep. That's the beating heart of the [timed door
(029)](029_timed_door.md); read it there in full. The two idioms compose
— keep a handle when you own the timer, count generations when you don't.

## Build it

The chamber and the bell:

```text
@dig Ritual Chamber = ritual, out
ritual
@create ceremony bell
drop ceremony bell
@desc ceremony bell = A tall bronze bell on a rope. RING BELL begins the rite; SILENCE BELL stops it.
@set ceremony bell/gap = 2
```

The three steps — each rings, then arms the next `gap` seconds out and
re-stashes the handle; the last clears `pending` to end the chain. The
delay is an attribute, so the tempo is one number to tune:

```text
@set ceremony bell/step_1 = remit(loc(me), 'The bell rings once. A hush falls over the chamber.'); set_attr(me, 'pending', wait(V('gap', 2), 'trigger me/step_2'))
@set ceremony bell/step_2 = remit(loc(me), 'The bell rings twice. The candles gutter.'); set_attr(me, 'pending', wait(V('gap', 2), 'trigger me/step_3'))
@set ceremony bell/step_3 = remit(loc(me), 'The bell rings a third and final time. It is done.'); del_attr(me, 'pending')
```

The two verbs — `begin` guards against a double ceremony, `silence`
cancels the one pending timer:

```text
@set ceremony bell/cmd_begin = $ring bell: pemit(enactor, 'A ceremony is already underway.') if V('pending') else eval_attr(me, 'step_1')
@set ceremony bell/cmd_silence = $silence bell: (cancel_wait(V('pending')), del_attr(me, 'pending'), remit(loc(me), 'The bell is stilled mid-peal.')) if V('pending') else pemit(enactor, 'Nothing is ringing.')
```

## Try it

```text
ring bell        -> The bell rings once. A hush falls over the chamber.
                 (2s) The bell rings twice. The candles gutter.
                 (2s) The bell rings a third and final time. It is done.
```

Start it and stop it mid-chain:

```text
ring bell        -> The bell rings once...
silence bell     -> The bell is stilled mid-peal.
                 (the second and third peals never come)
ring bell        -> ...and it starts cleanly again, one ceremony at a time.
```

`ring bell` a second time while one is running earns *A ceremony is
already underway.* — the stored handle is the guard.

## The reload caveat (read this)

Every `wait()` above is in-memory. If the server reboots between the
first and last peal, the pending timer is **gone** — and `pending` is
left set with no timer behind it, so `begin` would wrongly report "a
ceremony is already underway" forever. Three ways to handle it, in rising
order of effort:

1. **Accept it.** For a two-second flourish, a reboot mid-peal is
   invisible; on boot, a stale `pending` is a one-line cleanup.
2. **Guard on read.** Pair `pending` with an *absolute deadline*
   (`set_attr(me, 'until', now() + 6)`); `begin` treats `pending` as
   stale once `now() > until` — surviving the reboot without persistent
   timers, using the `now()` arithmetic of
   [152](152_persistent_timers.md).
3. **Use `expire()`** for anything that genuinely must resume — that's
   the persistent path, and the whole subject of
   [tutorial 152](152_persistent_timers.md).

The rule of thumb: **`wait()` for mechanical, expendable, sub-minute
delays; `expire()` the moment a reboot losing the timer would be a bug.**

## Going further

- **A skippable cutscene:** `wait()`-paced `remit()`s with a `$skip`
  that `cancel_wait`s the chain — tutorial 203's cutscene is this bell,
  grown up.
- **Belt-and-braces:** combine the stored handle *and* a generation
  counter, as [029](029_timed_door.md) discusses, for a timer that stays
  correct even if a handle ever goes missing.
- **Staggered volleys:** schedule several waits at once (not a chain) for
  overlapping effects — a firework finale — and reach for the generation
  counter to keep their cleanup sane.
