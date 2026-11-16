# 200. Collection counters

> Checklist item 200 ([now]): *a `collect` objective counted by the engine, tagged objectives*

**What you'll build:** a "salvage five relays" objective that tracks itself.
Scatter `objective`-tagged relays across the wreck field, take the job from
the Salvage Foreman, and the engine counts each relay the moment it is in
your hands, shows the running total, and pays out at five. There is no
turn-in step, because the world is already watching.

**Concepts:** a **`collect` objective** on the engine's
[quests](../guides/quests.md), matched by **tag**; a quest with **no giver**,
which completes the moment its objective is met; the **`quest_giver`**
behavior; and, for the curious, how a softcode counter would do the same
with a `custom` objective.

## How it works

A collection counter is one objective: `{"kind": "collect", "tag":
"objective", "count": 5}`. This section answers two questions: what
counts, and when the quest ends.

### What counts?

What you **hold**. A collect objective counts the matching items you carry
(in containers too), checked whenever you pick something up or are given
something. A relay tagged `objective` matches; the rusty wrench does not,
so picking it up prints only the ordinary line. The count is live: drop a
relay before the fifth and the journal reads one less, and picking it up
again counts it again, never twice. There is no `counted` tag to keep a
tally honest, because there is no tally, only what is in your hands.

### When does it end?

At once. "Salvage" has no `giver`, so meeting its only objective completes
it: the reward is paid on the spot. (With a `giver` it would be *ready*
instead, and the Foreman would take the relays back with `quest complete`,
taking them away too if the objective said `"consume": true`.) A finished
quest is finished: dropping and picking up relays afterwards does nothing.

## Build it

Stand in the room at the heart of the wreck field. Create the Foreman, who
offers the job:

```text
@create Salvage Foreman
@tag Salvage Foreman = npc
drop Salvage Foreman
@behavior Salvage Foreman = quest_giver, quests:["Salvage"]
```

The quest is the counter:

```text
@create Salvage
@tag Salvage = quest_def
@set Salvage/description = Recover five salvage relays from the wreck field.
@set Salvage/stages = [{"text": "Pick up five salvage relays.", "objectives": [{"kind": "collect", "tag": "objective", "count": 5, "text": "salvage relays recovered"}]}]
@set Salvage/rewards = {"credits": 100}
```

Scatter the objectives with one builder-softcode line,
[`create_obj`](../reference/softcode.md#fn-create_obj) inside a
comprehension, and add a decoy that should count for nothing:

```text
@eval [create_obj('salvage relay', ['thing', 'objective'], location=get('The Nexus')) for i in range(5)]
@create rusty wrench
drop rusty wrench
```

Swap `The Nexus` for your own room's name. Spreading the relays across
several rooms works just as well: the engine follows the player, not the
room.

## Try it

As Raven, standing among the salvage:

```text
> quest accept salvage
Quest accepted: Salvage.
Recover five salvage relays from the wreck field.
[Salvage] Stage 1: Pick up five salvage relays.

> get rusty wrench
You pick up a rusty wrench.

> get salvage relay
[Salvage] salvage relays recovered: 1/5
You pick up a salvage relay.

> get salvage relay
[Salvage] salvage relays recovered: 2/5
You pick up a salvage relay.

  ...

> get salvage relay
[Salvage] salvage relays recovered: 5/5
Quest complete: Salvage!
You receive 100 credits.
You pick up a salvage relay.
```

The wrench pickup prints only the ordinary line, which proves the
`objective` tag is doing the filtering rather than "anything picked up".
And the job stays done when you give a relay back:

```text
> drop salvage relay
You drop a salvage relay.

> get salvage relay
You pick up a salvage relay.
```

No progress line, and `credits` still reads 100: `quests done` lists
Salvage.

## Going further

- **Named objectives, one Foreman.** Tag relays `relay` and crystals
  `crystal`, and give the stage two collect objectives, each with its own
  `key` (`{"kind": "collect", "key": "relays", "tag": "relay", "count": 5}`,
  `{"kind": "collect", "key": "crystals", "tag": "crystal", "count": 3}`):
  the journal shows both, and the stage ends when both are met.
- **Count every pickup, not what is held.** A `custom` objective plus the
  old zone-master idea: `{"kind": "custom", "key": "relays", "count": 5}`,
  and an `ON_GET` on a zone master that stamps each relay `counted` and
  calls [`quest_advance(enactor, 'Salvage', 'relays')`](../reference/softcode.md#fn-quest_advance).
  Dropping then never lowers the count.
- **Hand them in.** Set `giver` to `Salvage Foreman` and `consume` on the
  objective: the Foreman takes the relays back when the job is handed in.
- **Repeat work.** `@set Salvage/repeatable = 3600` makes it an hourly job;
  a `spawner` refills the field ([063](063_shopkeeper.md) restocks the same
  way).
- **Audit the field.** [`search_world`](../reference/softcode.md#fn-search_world)
  with `tag='objective'` answers "how many relays are left out there".
