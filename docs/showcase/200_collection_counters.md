# 200. Collection counters

> Checklist item 200 — [now] — *zone-master ON_GET counting, tagged objectives*

**What you'll build:** a "salvage five relays" objective that tracks
itself — scatter `objective`-tagged relays across a zone, and the Salvage
Foreman (the zone master) counts each one the moment you pick it up,
announces your progress, and pays out at five. No turn-in, no click: the
world watches your hands.

**Concepts:** the **zone master as an `ON_GET` witness**; the event
payload gap and the **inventory-read** that works around it; a
**deferred tally** (`wait(0, ...)`) so the just-taken item has landed
before it's counted; a **monotonic count** via a `counted` tag so dropping
never un-does progress.

## How it works

Every pickup in the zone propagates a `get` action, and `ON_GET` fires on
everything that witnesses it — including the masters of the zone the room
belongs to (the same surveillance the [guard response](071_guard_response.md)
master uses for `ON_ATTACK`). So one `on_get` attribute on the Salvage
Foreman hears every relay taken anywhere in the salvage zone.

But an event trigger gets only `enactor` (who), never the item — the
payload gap the whole showcase keeps running into. So the Foreman can't be
told *what* was taken; it has to **read the taker's inventory** and see
what's new. Two subtleties make that honest:

1. **`ON_GET` fires before the item lands.** The pickup event propagates
   during the move's *check* pass, while the relay is still on the floor —
   so an inventory read inside `on_get` wouldn't see it yet. The fix is a
   **deferred tally**: `on_get` records the taker's id and schedules
   `wait(0, 'trigger me/tally')`, which runs after the pickup settles, when
   the relay is really in hand. (`wait(0)` is the "do this right after the
   current action" idiom; its handle isn't even needed here.)
2. **Count once, forever.** The tally counts `objective`-tagged items the
   taker holds that aren't yet tagged `counted`, then stamps `counted` on
   them. Progress lives in a single `salvage_count` on the player and only
   ever goes *up* — drop a relay and pick it up again and it won't
   re-count, because it's already marked. (The Foreman is admin-owned, so
   it may both tag the relay and write the player's counter — owner
   authority, the same rule the [quest framework](198_quest_framework.md)
   leans on.)

The `tally`/`count` split is there because a single tick can carry several
getters; `tally` drains the pending list and calls `count` once per taker.

## Build it

Stand in the room you want to be the salvage zone. Tag it into the zone,
raise the Foreman as the zone master, and set the goal:

```text
@zone here = salvage
@create Salvage Foreman
drop Salvage Foreman
@zone/master Salvage Foreman = salvage
@set Salvage Foreman/goal = 5
```

The witness and its deferred tally. `on_get` just remembers who and
schedules the count for the next beat; `tally` drains the queue:

```text
@set Salvage Foreman/on_get = set_attr(me, 'pending', (get_attr(me, 'pending') or []) + [enactor.id]); wait(0, 'trigger me/tally')
@set Salvage Foreman/tally = q = get_attr(me, 'pending') or []; set_attr(me, 'pending', []); [eval_attr(me, 'count', pid) for pid in q]
```

The counter itself — the objective read: count the taker's *uncounted*
objective items, stamp them, bump the total, announce, and pay out at the
goal:

```text
@set Salvage Foreman/count = p = get('#' + str(arg0)); fresh = [o for o in contents(p) if has_tag(o, 'objective') and not has_tag(o, 'counted')] if p else []; [add_tag(o, 'counted') for o in fresh]; n = get_attr(p, 'salvage_count', 0) + len(fresh); goal = get_attr(me, 'goal', 5); [(set_attr(p, 'salvage_count', n), pemit(p, 'Salvage relays recovered: ' + str(min(n, goal)) + '/' + str(goal))) for g in [bool(fresh)] if g]; [(set_attr(p, 'salvage_done', 1), adjust_credits(p, 100), pemit(p, 'Objective complete! The Foreman wires you 100 credits.')) for g in [n >= goal and not get_attr(p, 'salvage_done', 0)] if g]; result = 1
```

Scatter the objectives — five relays, seeded with one builder-softcode
line — plus a decoy that should *not* count:

```text
@eval [create_obj('salvage relay', ['thing', 'objective'], location=get('The Nexus')) for i in range(5)]
@create rusty wrench
@tag rusty wrench = thing
drop rusty wrench
```

(Swap `The Nexus` for your zone room's name, and spread the relays across
several rooms of the zone if you like — the master hears them all.)

## Try it

As Raven, standing among the salvage:

```text
get rusty wrench             -> (nothing; the counter ignores non-objectives)
get salvage relay            -> Salvage relays recovered: 1/5
get salvage relay            -> Salvage relays recovered: 2/5
...
get salvage relay            -> Salvage relays recovered: 5/5
                                Objective complete! The Foreman wires you 100 credits.
```

Pick up the wrench and nothing happens — only `objective` items count.
Drop a counted relay and grab it again and the tally holds steady: the
`counted` tag makes progress monotonic, so a player can't farm the same
relay twice.

## Going further

- **Named objectives, one master.** Tag relays `objective:relay` and
  crystals `objective:crystal` and count each namespace into its own
  counter — one Foreman, several collection quests
  (`tag_values(o, 'objective')`).
- **Consume on count.** Add `destroy_obj(o)` beside `add_tag(o, 'counted')`
  and the relays vanish as they're logged — a "hand them in on touch"
  variant with no turn-in at all.
- **Feed a quest line.** On completion, call the
  [Quest Warden](198_quest_framework.md)'s `advance` instead of paying
  directly — the collection becomes one stage of a longer quest.
- **Live objective tracker.** A `$objective` verb (or a GMCP `oob()` push)
  that reads `salvage_count` shows the count in a client sidebar, updated
  the instant a relay is grabbed.
