# 200. Collection counters

> Checklist item 200 ([now]): *zone-master ON_GET counting, tagged objectives*

**What you'll build:** a "salvage five relays" objective that tracks itself.
Scatter `objective`-tagged relays across a zone, and the Salvage Foreman (the
zone master) counts each one the moment a player picks it up, announces the
running total, and pays out at five. There is no turn-in step, because the
world is already watching.

**Concepts:** the **zone master as an `ON_GET` witness**; reading **`target`**,
the event's own data, to learn what was taken; a **monotonic count** kept
honest by a `counted` tag; owner authority for writing a player's sheet.

## How it works

The finished shape is three attributes on one object. A room is tagged into a
zone, the Salvage Foreman is crowned that zone's master, and a single `on_get`
script on the Foreman does all the bookkeeping: it identifies the relay, marks
it, bumps a number on the player, and pays out on the fifth. This section
answers three questions in turn: how the Foreman hears a pickup it is not
present for, how it knows *which* item moved, and why the tally never slides
backwards.

### How the Foreman hears a pickup in a room it is not standing in

Picking something up propagates an `item:on_get` action, and `ON_GET` fires on
everything that witnesses it: the room, the room's other contents, the item
itself, and the **masters of every zone the room belongs to** (see
[`ON_<EVENT>` lifecycle hooks](../reference/softcode.md#lifecycle-hooks) and
[Action Propagation](../architecture/events.md) for the full chain). Zone
membership is a tag convention, so `@zone here = salvage` on each room and
`@zone/master Salvage Foreman = salvage` on the object is the whole wiring;
[World Management](../guides/world-management.md#zones-areas) covers the
commands. That is the same zone-wide surveillance the
[guard response](071_guard_response.md) master uses for `ON_ATTACK`, and it
means one `on_get` attribute hears every relay taken anywhere in the salvage
zone, including rooms the Foreman never visits. A pickup in a room outside the
zone reaches the Foreman not at all, which is exactly the scoping you want for
a per-area objective.

### How the Foreman knows which relay was taken

On an `item:on_get` the picked-up item **is** the action's `target`, one of the
names REALM binds into any script reacting to an action (the
[event data namespace](../reference/softcode.md#event-data-namespace); the
[event bus tour](245_event_bus_tour.md) walks through the rest). So the witness
reads the relay straight off the event rather than searching for it, and
[`has_tag`](../reference/softcode.md#fn-has_tag) on that `target` separates a
relay from a wrench or a lamp.

Because the Foreman is a zone master, it is a **global witness** and takes no
`if target is me:` guard. That guard exists for an object reacting to its own
business, since an `ON_<EVENT>` hook fires on every object in the room and an
unguarded reaction would fire on a neighbour's traffic
([Guard on `target`](../reference/softcode.md#guard-on-target)). A zone master
is the deliberate exception, because watching everybody's pickups is precisely
its job. The tag test on `target` is what keeps it honest: with five relays and
a wrench lying on the same floor, one pickup counts exactly one relay, and the
wrench counts nothing.

### Why the tally only ever goes up

`ON_GET` runs on the **reaction pass**, after the engine has already moved the
item, so by the time the script runs the relay is in the taker's inventory and
its location is the taker. Counting from `target` therefore needs no deferred
`wait(0)` re-read, and no pending queue: the event names the thing that moved,
so the script never has to go looking for where it moved to.

That leaves one problem, which is a player dropping a relay and grabbing it
again. The script solves it by stamping the relay with a `counted` tag
*before* it touches the total, so the guard `not has_tag(target, 'counted')`
rejects every later pickup of that same relay. Progress lives in a single
`salvage_count` number on the player and only ever rises. The stamp-first order
also settles a subtler case: if two masters of the same zone both run a
counting hook, the first one to see the relay marks it and the second finds it
already counted, so the pickup is still worth exactly one.

### Why the Foreman has to be admin-owned

The Foreman writes `salvage_count` onto somebody else's character sheet, and
that is owner authority: a script may write a player's attributes when its own
owner outranks the player, which in practice means staff. Build this as an
admin, the same rule the
[quest framework](198_quest_framework.md) relies on. Under a merely-builder
owner, [`set_attr`](../reference/softcode.md#fn-set_attr) returns `False` and
the counter silently stays at zero while everything else appears to work, so a
tally frozen at nothing is the symptom to look for.

## Build it

Stand in the room you want as the heart of the salvage zone. Tag the room into
the zone, create the Foreman, leave it in the room, and crown it master of that
zone:

```text
@zone here = salvage
@create Salvage Foreman
drop Salvage Foreman
@zone/master Salvage Foreman = salvage
```

The goal is a plain data attribute, so the payout threshold is editable later
without touching the script:

```text
@set Salvage Foreman/goal = 5
```

Now the witness itself, written as a
[heredoc block](../guides/world-management.md#multi-line-input-heredocs): open
the `@set` with `'''`, type the body as ordinary indented Python, and close
with a line of `'''`. It runs five steps in order, which are to test the item
on the event, stamp it, raise the player's total, report the new total, and pay
out once the goal is reached. [`V`](../reference/softcode.md#fn-v) reads the
Foreman's own `goal`, while
[`get_attr`](../reference/softcode.md#fn-get_attr) and `set_attr` read and
write the player's counter, and
[`pemit`](../reference/softcode.md#fn-pemit) reports privately to the taker:

```text
@set Salvage Foreman/on_get = '''
if has_tag(target, 'objective') and not has_tag(target, 'counted'):
    # Stamp before counting: the tag is what makes a re-pickup, or a
    # second zone master seeing the same event, worth nothing.
    add_tag(target, 'counted')
    goal = V('goal', 5)
    n = get_attr(enactor, 'salvage_count', 0) + 1
    set_attr(enactor, 'salvage_count', n)
    pemit(enactor, f'Salvage relays recovered: {min(n, goal)}/{goal}')
    if n >= goal and not get_attr(enactor, 'salvage_done', 0):
        set_attr(enactor, 'salvage_done', 1)
        adjust_credits(enactor, 100)
        pemit(enactor, 'Objective complete! The Foreman wires you 100 credits.')
'''
```

There is no `if target is me:` line here on purpose, since a zone master is a
global witness. [`add_tag`](../reference/softcode.md#fn-add_tag) is what makes
the count monotonic, and
[`adjust_credits`](../reference/softcode.md#fn-adjust_credits) pays the reward
exactly once because `salvage_done` latches.

Scatter the objectives with one builder-softcode line,
[`create_obj`](../reference/softcode.md#fn-create_obj) inside a comprehension,
and add a decoy that should count for nothing:

```text
@eval [create_obj('salvage relay', ['thing', 'objective'], location=get('The Nexus')) for i in range(5)]
@create rusty wrench
drop rusty wrench
```

Swap `The Nexus` for your own zone room's name. Spreading the relays across
several rooms of the zone works just as well, because the master hears them
all.

## Try it

As Raven, standing among the salvage:

```text
> get rusty wrench
You pick up a rusty wrench.

> get salvage relay
Salvage relays recovered: 1/5
You pick up a salvage relay.

> get salvage relay
Salvage relays recovered: 2/5
You pick up a salvage relay.

> get salvage relay
Salvage relays recovered: 5/5
Objective complete! The Foreman wires you 100 credits.
You pick up a salvage relay.
```

Two results are worth confirming deliberately. The wrench pickup prints only
the ordinary pickup line, which proves the `objective` tag is doing the
filtering rather than "anything picked up in this zone". And the tally holds
when you give a relay back:

```text
> drop salvage relay
You drop a salvage relay.

> get salvage relay
You pick up a salvage relay.
```

No progress line, and `salvage_count` is still 5, because that relay already
carries `counted`.

## Going further

- **Named objectives, one master.** Tag relays `objective:relay` and crystals
  `objective:crystal`, then read
  [`tag_values(target, 'objective')`](../reference/softcode.md#fn-tag_values)
  to route each kind into its own counter, so one Foreman runs several
  collection quests at once.
- **Consume on count.** Put
  [`destroy_obj`](../reference/softcode.md#fn-destroy_obj) beside the
  `add_tag` call and the relays vanish as they are logged, which turns the
  build into a hand-them-in-on-touch variant with no inventory to manage.
- **Count what is in hand.** `ON_DROP` binds `target` the same way, so an
  `on_drop` that decrements turns the monotonic total into a live "relays
  currently carried" gauge from the same event data.
- **Audit the zone.** [`search_world`](../reference/softcode.md#fn-search_world)
  with `tag='objective'`, or
  [`contents`](../reference/softcode.md#fn-contents) filtered by `has_tag`,
  answers "how many relays are left out there" and "how many is this player
  holding" for a status verb.
- **Feed a quest line.** On completion, call the
  [Quest Warden](198_quest_framework.md)'s `advance` instead of paying
  directly, and the collection becomes one stage of a longer quest.
- **Live objective tracker.** A `$objective` verb, or a GMCP push through
  [`oob`](../reference/softcode.md#fn-oob), reads `salvage_count` into a client
  sidebar the instant a relay is grabbed.
