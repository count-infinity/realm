# 068. NPC daily schedule

> Checklist item 68 — [now] — *softcode clock, attach_behavior/detach_behavior by hour*

**What you'll build:** Verity, a supplier who opens her Market Street
stall at nine, trades all day, locks up at nine in the evening, walks
upstairs to her loft, and sleeps. At night the shop physically stands
empty — and the `shopkeeper` behavior itself is off her, so even
shouting `buy` at the counter gets nothing.
**Concepts:** a softcode clock (one object, one `on_tick`), deriving a
state machine from game time, `attach_behavior`/`detach_behavior` from
softcode, scripted `move` for a real commute, composing with the
built-in `shopkeeper`.

## How it works

There is no global game clock in the engine — because you can build a
better one in two lines. **A clock is an object whose `on_tick`
increments an `hour` attribute modulo 24**, driven by `script_ticker`.
Attribute reads are open to every script, so the whole town shares it:
`get_attr('town clock', 'hour', 12)`.

Verity runs her own `script_ticker`. Each tick she asks the clock and
routes to one of two state attributes with `trigger()`:

```
9 <= hour < 21  →  open_up:    not at the shop? walk a step toward it.
                               at the shop, not trading? attach the
                               shopkeeper behavior, announce, trade.
otherwise       →  close_down: still trading? detach shopkeeper and
                               announce. otherwise walk home and sleep.
```

Two design points worth stealing:

- **Presence is the mechanic, twice over.** The `buy`/`list` commands
  find a merchant by scanning the room for the `shopkeeper` behavior —
  so closing is *literally* `detach_behavior(me, 'shopkeeper')`, and
  walking away is belt-and-braces. No "closed" flag to keep in sync.
- **The commute is real movement.** The scripted `move('downstairs')`
  goes through exit locks and doors like any player. One exit per tick
  — with a longer route you'd watch her walk to work street by street.

The stock is her inventory (`give` her goods to restock), prices come
from each item's `value` times her markup, and her disposition toward
the buyer still moves the price — the built-in behavior composes with
everything the arc taught before.

## Build it

Dig the shop and the loft above it (from the Square of item 60):

```
@dig Market Street = market, square
market
@zone here = town
@dig The Loft = upstairs, downstairs
```

**The town clock.** Any object, anywhere; `interval:1` here means one
game hour per world tick — brisk for testing. At the default 4-second
tick, `interval:225` gives a 15-minute half-hour... pick your tempo,
it's one number:

```
@create town clock
drop town clock
@set town clock/hour = 6
@set town clock/on_tick = set_attr(me, 'hour', (V('hour', 0) + 1) % 24)
@behavior town clock = script_ticker, interval:1
```

**The keeper and her routine.** Three attributes: the dispatcher, and
the two states it routes between:

```
@create Verity
@tag Verity = npc
drop Verity
@set Verity/on_tick = h = get_attr('town clock', 'hour', 12); trigger('open_up' if 9 <= h < 21 else 'close_down')
@set Verity/open_up = (move('downstairs') if name(here) != 'Market Street' else (None if 'shopkeeper' in behaviors(me) else (attach_behavior(me, 'shopkeeper', markup=1.2), say('Shutters up! Fresh goods at fair prices!'))))
@set Verity/close_down = ((detach_behavior(me, 'shopkeeper'), say('Closing up. Come back at nine.')) if 'shopkeeper' in behaviors(me) else (move('upstairs') if name(here) != 'The Loft' else None))
@behavior Verity = script_ticker, interval:1
```

Read `close_down` inside-out: the *first* off-hours tick catches her
still trading — detach, announce, done for that tick. The next walks
her home. After that both conditions are cold and she sleeps for free.
The `'shopkeeper' in behaviors(me)` check is the state flag — no extra
attribute needed, the attached behavior *is* the state.

**Stock the stall:**

```
@create ration pack
@set ration pack/value = 8
give ration pack to Verity
```

## Try it

Give yourself coin, then live a day beside her (with `interval:1`, an
hour passes per world tick — `@stats` shows the tick):

```
@set me/credits = 40
list                     (before nine)  → "There's no merchant here."
                         (at nine she walks down; on the next tick:)
                         → Verity says, "Shutters up! Fresh goods at fair prices!"
list                     → ration pack — 10 credits   (8 × 1.2 markup)
buy ration pack          → yours, and Verity pockets the 10
                         (at hour 21:)
                         → Verity says, "Closing up. Come back at nine."
list                     → "There's no merchant here."  (she hasn't even left yet)
```

Then she climbs to the loft, and Market Street stands quiet till dawn.

## Going further

- **Lock up behind her:** in `close_down`, `close('downstairs')` and
  set the exit's lock on the way out; reopen in `open_up` — knock all
  you like at midnight.
- **A longer commute:** put the loft across town and let
  `open_up`/`close_down` walk a route attr one exit per tick (the
  `patrol` behavior shows the pattern) — townsfolk will pass her on
  the way to work.
- **Night shift wanderer:** attach item 60's `wandering` in
  `close_down` and detach it in `open_up` — a keeper who bar-crawls
  after close, and still opens at nine sharp.
- **One clock, many lives:** the guard changes at the post, Mira calls
  last orders, the scamp gets a curfew — all reading the same
  `town clock/hour` attribute you already built.
