# 146. Item decay

> Checklist item 146 — [now] — *decay strategies, batch sweeper vs per-item ticker vs expire()*

**What you'll build:** A cargo hold where perishables rot on a shared
schedule — a single **pantry sweeper** burns down every perishable's
shelf life in one pass and turns the spoiled ones to sludge. The same
outcome as [tutorial 018](018_refrigerator.md)'s self-rotting peach,
reached by the opposite architecture — which is the real lesson here.

**Concepts:** the three ways to expire things in REALM and *when each
wins* — per-item `expire()`, per-item ticker (018), and the **batch
sweeper** built below — plus `search_world()` as the sweep query and
dumb data items with no behavior of their own.

## How it works: three architectures for decay

REALM gives you three tools for "this should go away on a schedule."
They are not interchangeable; the choice is a real design decision.

| Approach | Who owns the clock | Cost | Best when |
|---|---|---|---|
| **Per-item `expire()`** | the engine (one `expires_at` per item, reaped on the housekeeping task) | O(1) per item, no scan | items have a fixed *lifetime* and just need to vanish (or fire one `ON_EXPIRE`) — smoke, corpses, [019](019_trash_incinerator.md)'s trash |
| **Per-item ticker** | each item ([018](018_refrigerator.md)) | O(items-with-behavior) per tick | decay rate depends on the item's **surroundings** (a fridge, a freezer) — the item must ask its holder every tick |
| **Batch sweeper** *(this one)* | one central object | O(all-perishables) per sweep, but **one** behavior and **one** policy knob | you want *central control* — global spoilage rate, one place to tune, dumb data items, bulk reporting |

The peach in 018 owns its own ticker because its rate is *local* — cold
box versus counter. When rate is *global* and you'd rather tune one
number than a thousand items, invert it: make the items inert data and
give one object the clock. That's the sweeper.

**Items are pure data.** A perishable is just a `perishable`-tagged
object with a `shelf` count. No behavior, no script — it doesn't know it
can rot. All the intelligence is in the sweeper.

**The sweep is one query and one pass.** The sweeper's tick runs
`search_world(tag='perishable')`, decrements each `shelf`, and — for any
that hit zero — announces the spoilage in that item's room, drops a
puddle of sludge where it lay, and destroys it. `create_obj` and
`destroy_obj` run with the sweeper's owner authority, so a builder-owned
sweeper rots only its owner's goods; an admin-owned one polices the
station. (Contrast 018's peach, which destroys *itself* — always
allowed. Here one object reaches out and reaps many, which is exactly
why the authority note matters.)

## Build it

A hold and two perishables with different shelf lives — pure data, no
behaviors:

```text
@dig Cargo Hold = hold, out
hold
@create crate of rations
@tag crate of rations = perishable
@set crate of rations/shelf = 3
drop crate of rations
@create field medkit
@tag field medkit = perishable
@set field medkit/shelf = 5
drop field medkit
```

The sweeper. Its `sweep` attribute is the whole policy: decrement, then
replace-and-destroy anything at or below zero. The `on_tick` just runs
it, so you can also `@tr` it by hand:

```text
@create pantry sweeper
drop pantry sweeper
@set pantry sweeper/sweep = [(set_attr(o, 'shelf', get_attr(o, 'shelf', 0) - 1), (remit(loc(o), 'The ' + name(o) + ' has spoiled into reeking sludge.'), create_obj('a puddle of sludge', ['thing'], loc(o)), destroy_obj(o)) if get_attr(o, 'shelf', 0) <= 0 else None) for o in search_world(tag='perishable')]
@set pantry sweeper/on_tick = eval_attr(me, 'sweep')
@behavior pantry sweeper = script_ticker, interval:1
```

The trick that avoids a double-decrement: the tuple sets `shelf` first,
then the `if` re-reads the **freshly stored** value — one subtraction,
checked in place.

## Try it

```text
@tr pantry sweeper/on_tick       both lose a shelf point (crate 2, medkit 4)
@tr pantry sweeper/on_tick       crate 1, medkit 3
@tr pantry sweeper/on_tick
   -> The crate of rations has spoiled into reeking sludge.
```

Three sweeps and the crate (shelf 3) is a puddle on the hold floor,
while the medkit (shelf 5) is still good at shelf 2. One object drove
both fates, and neither item ran a line of its own code. Add a hundred
more perishables and the sweeper handles them all on the same tick —
raise or lower every shelf life by editing one `sweep` policy, not a
hundred items.

## Going further

- **Environmental rate, kept central:** read `get_attr(loc(o),
  'decay_rate', 1)` inside the sweep and you get 018's fridge behavior
  *and* central control — the sweeper honors cold rooms while still being
  the one clock.
- **Staged rot:** instead of destroy, step a `stage` attribute and swap
  the desc (fresh → wilted → mush), harvesting 018's replacement idea
  without a per-item ticker.
- **Report before you reap:** the [maintenance sweeper
  (149)](149_maintenance_sweeper.md) shows the dry-run-first discipline —
  wrap this sweep the same way to preview a purge before it happens.
- **Lifetimes that must survive a reboot:** if a perishable should rot
  *even while the server is down*, hang an `expire()` on it instead —
  the persistent path of [tutorial 152](152_persistent_timers.md). The
  sweeper's counter pauses across downtime; `expire()` doesn't.
