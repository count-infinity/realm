# 146. Item decay

> Checklist item 146 ([now]): *decay behavior, expire()/ON_EXPIRE, batch sweeps*

**What you'll build:** A cargo hold where perishables rot on a shared
schedule. A single **pantry sweeper** burns down every perishable's shelf life
in one pass and turns the spoiled ones to sludge. This reaches the same outcome
as [tutorial 018](018_refrigerator.md)'s self-rotting peach by the opposite
architecture, which is the real lesson here.

**Concepts:** the three ways to expire things in REALM and *when each wins*:
per-item [`expire()`](../reference/softcode.md#fn-expire), a per-item ticker
(018), and the **batch sweeper** built below, plus
[`search_world()`](../reference/softcode.md#fn-search_world) as the sweep query
and dumb data items with no behavior of their own.

## How it works: three architectures for decay

REALM gives you three tools for "this should go away on a schedule." They are
not interchangeable, so the choice is a real design decision. The finished
build here is the third one: inert data items plus one central clock that
walks them all.

| Approach | Who owns the clock | Cost | Best when |
|---|---|---|---|
| **Per-item `expire()`** | the engine (one `expires_at` per item, reaped on the housekeeping pass) | no per-item work; the housekeeping pass reaps by timestamp | items have a fixed *lifetime* and just need to vanish (or fire one `ON_EXPIRE`): smoke, corpses, [019](019_trash_incinerator.md)'s trash |
| **Per-item ticker** | each item ([018](018_refrigerator.md)) | O(items-with-behavior) per tick | decay rate depends on the item's **surroundings** (a fridge, a freezer), so the item asks its holder every tick |
| **Batch sweeper** *(this one)* | one central object | O(all-perishables) per sweep, but **one** behavior and **one** policy knob | you want *central control*: a global spoilage rate, one place to tune, dumb data items, bulk reporting |

The peach in 018 owns its own ticker because its rate is *local* (a cold box
versus a counter). When the rate is *global* and you would rather tune one
number than a thousand items, invert it: make the items inert data and give one
object the clock. That is the sweeper.

**Items are pure data.** A perishable is just a `perishable`-tagged object with
a `shelf` count. It has no behavior and no script, so it has no notion of
rotting. All the intelligence lives in the sweeper.

**The sweep is one query and one pass.** The sweeper's tick runs
[`search_world(tag='perishable')`](../reference/softcode.md#fn-search_world),
decrements each `shelf`, and for any that hit zero it announces the spoilage in
that item's room, drops a puddle of sludge where it lay, and destroys it.
[`create_obj`](../reference/softcode.md#fn-create_obj) and
[`destroy_obj`](../reference/softcode.md#fn-destroy_obj) run with the sweeper's
owner authority, so a builder-owned sweeper reaps only goods that owner
controls, while an admin-owned one polices the whole station. Contrast 018's
peach, which destroys *itself* (always allowed). Here one object reaches out
and reaps many, which is exactly why the authority note matters.

## Build it

A hold and two perishables with different shelf lives, pure data with no
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

The sweeper itself starts as an ordinary object dropped in the hold:

```text
@create pantry sweeper
drop pantry sweeper
```

The `sweep` attribute is the whole policy. For each perishable the query
returns, it does two things in order: it decrements that item's `shelf` with
[`set_attr`](../reference/softcode.md#fn-set_attr), then re-reads the freshly
stored count with [`get_attr`](../reference/softcode.md#fn-get_attr) and, if it
has reached zero, announces the spoilage to the item's room with
[`remit`](../reference/softcode.md#fn-remit), drops a puddle, and destroys the
item. Because `set_attr` stores immediately, the re-read sees the new value, so
the count drops by exactly one per sweep:

```text
@set pantry sweeper/sweep = '''
for o in search_world(tag='perishable'):
    set_attr(o, 'shelf', get_attr(o, 'shelf', 0) - 1)
    if get_attr(o, 'shelf', 0) <= 0:
        # create_obj/destroy_obj run as the sweeper's owner, so it reaps
        # only goods that owner controls (loc(o) is the item's room).
        remit(loc(o), 'The ' + name(o) + ' has spoiled into reeking sludge.')
        create_obj('a puddle of sludge', ['thing'], loc(o))
        destroy_obj(o)
'''
```

The `on_tick` hook just runs that policy, so the same
[`@behavior`](../reference/softcode.md#lifecycle-hooks) heartbeat that fires it
every interval also lets you fire it by hand with `@tr pantry sweeper/on_tick`.
[`eval_attr`](../reference/softcode.md#fn-eval_attr) runs the stored `sweep`
routine under the caller's authority, which here is the sweeper:

```text
@set pantry sweeper/on_tick = eval_attr(me, 'sweep')
@behavior pantry sweeper = script_ticker, interval:1
```

## Try it

Fire the sweeper by hand a few times and watch the two shelf lives diverge:

```text
> @tr pantry sweeper/on_tick
Triggered pantry sweeper/on_tick.
   (crate 3 -> 2, medkit 5 -> 4)

> @tr pantry sweeper/on_tick
Triggered pantry sweeper/on_tick.
   (crate 2 -> 1, medkit 4 -> 3)

> @tr pantry sweeper/on_tick
Triggered pantry sweeper/on_tick.
The crate of rations has spoiled into reeking sludge.
   (crate hits 0 and becomes a puddle; medkit rides on at 2)
```

Three sweeps and the crate (shelf 3) is a puddle on the hold floor, while the
medkit (shelf 5) is still good at shelf 2. One object drove both fates, and
neither item ran a line of its own code. Add a hundred more perishables and the
sweeper handles them all on the same tick, and you raise or lower every shelf
life by editing one `sweep` policy rather than a hundred items.

## Going further

- **Environmental rate, kept central:** read `get_attr(loc(o), 'decay_rate',
  1)` inside the sweep and you get 018's fridge behavior *and* central control,
  because the sweeper honors cold rooms while still being the one clock.
- **Staged rot:** instead of destroying the item, step a `stage` attribute and
  swap the desc (fresh, then wilted, then mush), harvesting 018's replacement
  idea without a per-item ticker.
- **Report before you reap:** the [maintenance sweeper
  (149)](149_maintenance_sweeper.md) shows the dry-run-first discipline, so
  wrap this sweep the same way to preview a purge before it happens.
- **Lifetimes that must survive a reboot:** if a perishable should rot *even
  while the server is down*, hang an [`expire()`](../reference/softcode.md#fn-expire)
  on it instead, the persistent path of [tutorial 152](152_persistent_timers.md).
  The sweeper's counter pauses across downtime because it only steps on a live
  tick, whereas `expire()` stores an absolute time and comes due on schedule
  regardless.
