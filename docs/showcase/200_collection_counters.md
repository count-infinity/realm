# 200. Collection counters

> Checklist item 200 — [now] — *zone-master ON_GET counting, tagged objectives*

**What you'll build:** a "salvage five relays" objective that tracks
itself — scatter `objective`-tagged relays across a zone, and the Salvage
Foreman (the zone master) counts each one the moment you pick it up,
announces your progress, and pays out at five. No turn-in, no click: the
world watches your hands.

**Concepts:** the **zone master as an `ON_GET` witness**; reading
**`target`** — the event's own data — to know what was taken; a
**monotonic count** via a `counted` tag so dropping never un-does
progress.

## How it works

Every pickup in the zone propagates a `get` action, and `ON_GET` fires on
everything that witnesses it — including the masters of the zone the room
belongs to (the same surveillance the [guard response](071_guard_response.md)
master uses for `ON_ATTACK`). So one `on_get` attribute on the Salvage
Foreman hears every relay taken anywhere in the salvage zone.

And the Foreman is told *what* was taken: on a `get`, the item **is** the
action's `target` ([event bus tour](245_event_bus_tour.md) has the full
data namespace). So the witness reads the relay straight off the event —
no guessing, no searching:

1. **`target` names the relay.** `on_get` checks `has_tag(target,
   'objective')` and hands the relay to the counter. A pickup of anything
   else — a wrench, a lamp — fails the guard and costs nothing.
2. **Count once, forever.** The counter stamps `counted` on the relay
   before bumping the total, so progress lives in a single `salvage_count`
   on the player and only ever goes *up* — drop a relay and pick it up
   again and it won't re-count, because it's already marked. (The Foreman
   is admin-owned, so it may both tag the relay and write the player's
   counter — owner authority, the same rule the
   [quest framework](198_quest_framework.md) leans on.)

**Why there's no `wait(0)` here.** `ON_GET` fires *before* the item lands:
the two-pass propagation runs while the relay is still on the floor, so a
script that counted by reading `contents(enactor)` would see nothing and
would need a deferred `wait(0, 'trigger me/tally')` to re-read after the
pickup settled. Reading `target` sidesteps the timing entirely — the event
tells you what moved, so you never have to look where it moved *to*. The
whole pending-queue-and-drain apparatus disappears with it.

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

The witness. It reads the taken item off the event as `target`, and only
bothers the counter for an uncounted objective:

```text
@set Salvage Foreman/on_get = [eval_attr(me, 'count', enactor.id, target.id) for g in [has_tag(target, 'objective') and not has_tag(target, 'counted')] if g]
```

The counter itself — stamp the relay so it can never count twice, bump the
total, announce, and pay out at the goal:

```text
@set Salvage Foreman/count = p = get('#' + str(arg0)); relay = get('#' + str(arg1)); add_tag(relay, 'counted'); n = get_attr(p, 'salvage_count', 0) + 1; goal = V('goal', 5); set_attr(p, 'salvage_count', n); pemit(p, 'Salvage relays recovered: ' + str(min(n, goal)) + '/' + str(goal)); [(set_attr(p, 'salvage_done', 1), adjust_credits(p, 100), pemit(p, 'Objective complete! The Foreman wires you 100 credits.')) for g in [n >= goal and not get_attr(p, 'salvage_done', 0)] if g]; result = 1
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
  (`tag_values(target, 'objective')`).
- **Consume on count.** Add `destroy_obj(relay)` beside
  `add_tag(relay, 'counted')` and the relays vanish as they're logged — a
  "hand them in on touch" variant with no turn-in at all.
- **Count drops too.** `ON_DROP` binds `target` the same way, so an
  `on_drop` that decrements turns the monotonic counter into a live
  "relays currently in hand" gauge — a different quest shape from the same
  event data.
- **Feed a quest line.** On completion, call the
  [Quest Warden](198_quest_framework.md)'s `advance` instead of paying
  directly — the collection becomes one stage of a longer quest.
- **Live objective tracker.** A `$objective` verb (or a GMCP `oob()` push)
  that reads `salvage_count` shows the count in a client sidebar, updated
  the instant a relay is grabbed.
