# 150. Global countdown events

> Checklist item 150 — [now] — *server-wide broadcast, reusable wait() countdown, world-zone master*

**What you'll build:** An Event Herald that runs a countdown to **every
room on the server** — `countdown 3 for the Convergence` announces "in 3
minutes... 2... 1... begins NOW!" station-wide — and is generic enough to
reuse for any event, any duration, from one command.

**Concepts:** the world-zone master as a server-wide broadcaster,
`search_world(tag='room')` as the all-rooms fan-out, a **parameterized,
reusable** `wait()` countdown (label and length as arguments), and
`cancel_wait()` to scrub it.

## How it works

This is the [self-destruct (056)](056_self_destruct.md) countdown turned
inside out. There, the countdown was **zone-scoped** — `act(...,
targeting='zone')` reached one station, and the payload was fire in that
station's rooms. Here we want **server-wide** and **reusable**, so two
things change:

- **Broadcast is world-wide.** Instead of a zone all-call, the Herald
  loops `remit()` over `search_world(tag='room')` — every room in the
  world. (Crown it on a `zone:world` room so the same object could also
  *hear* global `$`-commands, the world-master trick of
  [083](083_message_in_bottle.md).) For a broadcast confined to one area,
  use 056's zone targeting instead; pick the blast radius deliberately.
- **The countdown is data, not a fixed script.** `label` and `remaining`
  are attributes set by the command, so one Herald runs a countdown to
  *anything* — a market opening, a boss spawn, a server event — without
  re-authoring. 056's countdown is welded to one station's self-destruct;
  this one is a reusable utility.

**The countdown itself is a `wait()` chain** — the [148](148_delayed_actions.md)
idiom. One `tick` step announces the current `remaining`, decrements,
and schedules the next tick `gap` seconds later, keeping the handle in
`pending`; at zero it hands off to `fire`. `scrub` is `cancel_wait(
get_attr(me, 'pending'))`. Being `wait()`-based, it's in-memory — right
for a countdown, where a reboot mid-count should simply forget it rather
than resume a stale one.

## Build it

Two world-zone rooms to prove the broadcast reaches everywhere, and the
Herald as their master:

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

The broadcast helper, the countdown tick, and the zero-hour fire — each
fans out over every room:

```text
@set Event Herald/announce = [remit(r, get_attr(me, 'banner', 'ATTENTION') + ': ' + get_attr(me, 'label', 'an event') + ' in ' + str(get_attr(me, 'remaining', 0)) + ' minutes.') for r in search_world(tag='room')]
@set Event Herald/tick = n = get_attr(me, 'remaining', 0); (eval_attr(me, 'fire') if n <= 0 else (eval_attr(me, 'announce'), set_attr(me, 'remaining', n - 1), set_attr(me, 'pending', wait(get_attr(me, 'gap', 2), 'trigger me/tick'))))
@set Event Herald/fire = del_attr(me, 'pending'); del_attr(me, 'remaining'); [remit(r, get_attr(me, 'label', 'the event') + ' begins NOW!') for r in search_world(tag='room')]
```

The two verbs — owner-only `countdown <n> for <label>`, and `scrub` to
call it off. `countdown` refuses to stack over a running one:

```text
@set Event Herald/cmd_countdown = $countdown * for *: pemit(enactor, 'Command authority required.') if enactor != owner(me) else (pemit(enactor, 'A countdown is already running.') if get_attr(me, 'pending') else (set_attr(me, 'label', arg1), set_attr(me, 'remaining', int(arg0)), eval_attr(me, 'tick')))
@set Event Herald/cmd_scrub = $scrub countdown: (cancel_wait(get_attr(me, 'pending')), del_attr(me, 'pending'), del_attr(me, 'remaining'), [remit(r, get_attr(me, 'label', 'the event') + ' has been called off.') for r in search_world(tag='room')]) if get_attr(me, 'pending') else pemit(enactor, 'No countdown is running.')
```

## Try it

With players scattered across the Plaza and the Docks, as the owner:

```text
countdown 3 for the Convergence
   -> (every room) STATION ANNOUNCEMENT: the Convergence in 3 minutes.
   (gap) ... the Convergence in 2 minutes.
   (gap) ... the Convergence in 1 minutes.
   (gap) the Convergence begins NOW!
```

Everyone on the server hears each beat, wherever they stand. Start
another and call it off:

```text
countdown 5 for the Eclipse
scrub countdown
   -> (every room) The Eclipse has been called off.
```

A non-owner who tries `countdown` gets *Command authority required.*, and
`countdown` over a live count earns *A countdown is already running.* —
one countdown at a time, from one command, to the whole world.

## Going further

- **A real payload:** have `fire` do more than announce — spawn the boss,
  open the arena exits, `act()` a world event. The countdown becomes the
  ramp to any global happening.
- **Scheduled, not manual:** trigger `countdown` from the daily timetable
  of [145](145_scheduled_events.md) so the nightly event announces itself.
- **Opt-out channel:** filter the broadcast by an `announce_optout` attr
  on the player (skip `if not has_attr(p, 'announce_optout')`) for players
  who mute server pings — the announcement pattern of tutorial 181.
- **Per-zone flavor:** switch the room's zone inside `announce` to localize
  the wording — the docks hear a foghorn, the plaza a chime.
