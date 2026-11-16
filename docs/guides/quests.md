# Quests

A builder writes a quest down as data, and the engine tracks it: who has
it, how far along they are, and what they get. All of it is the `quests`
feature (MUD_PLAN step 15):

- **Quests as data**: `quest_def` objects, each an ordered list of
  **stages**, each stage a list of **objectives**.
- **Objectives the engine notices itself**: killing, collecting,
  delivering, visiting, talking, using; and `custom` ones softcode moves.
- **Givers**: an NPC offers a quest, shows `(!)` while it has one for you
  and `(?)` while it waits for your hand-in, and pays you when you bring
  it back.
- **The journal** (`quests`), the history (`quests done`) and `talk`.
- **Rewards** through what the game already has: the game system's award,
  money, items, achievements, tags.
- **Repeatable quests**, **time limits**, and quests done **once per
  account**.
- **Softcode**: read a player's progress anywhere (a lock too), and move it
  from any hook.

`quests` requires no other feature. It reaches `rules` (the award),
`economy` (credits), `achievements`, `companions` (a pet's kill is its
master's) and `social` (the party shares a kill) through their services; a
reward whose feature is absent is skipped with a WARNING naming the quest.
It is in `CLASSIC`.

## A quest built in the game

Mira's cellar is overrun, and her ring is down there. Two stages: go down
and kill three rats, then bring the ring back. Build it as staff, standing
in the taproom:

```text
@dig The Cellar = down, up
@create Mira
@tag Mira = npc
drop Mira
@create The Rat Cellar
@tag The Rat Cellar = quest_def
@set The Rat Cellar/description = Rats have overrun Mira's cellar, and her ring is down there somewhere.
@set The Rat Cellar/giver = Mira
@set The Rat Cellar/stages = [{"text": "Go down to the cellar and kill three rats.", "objectives": [{"kind": "visit", "name": "The Cellar"}, {"kind": "kill", "name": "rat", "count": 3}]}, {"text": "Find Mira's ring and bring it back to her.", "objectives": [{"kind": "collect", "name": "Mira's ring", "consume": true}]}]
@set The Rat Cellar/rewards = {"award": 50, "credits": 25}
@set The Rat Cellar/on_complete = pemit(enactor, 'Mira presses a free drink token into your hand.')
@set Mira/on_questaccept = if target is me: say('Mind the big one.')
down
@eval [create_obj('rat', ['npc'], location=get('The Cellar')) for i in range(3)]
@create Mira's ring
drop Mira's ring
up
```

The quest object stays in your inventory; it is data, and works wherever
it is. Its scripts (`on_complete` here) run as the quest object, with the
player as `enactor` and the quest object's owner's authority.

A player in the taproom:

```text
> look
  ...
  Mira (!)

> quest list
Mira offers:
  The Rat Cellar - Rats have overrun Mira's cellar, and her ring is down there somewhere.
(quest accept <name> to take one)

> quest accept rat
Quest accepted: The Rat Cellar.
Rats have overrun Mira's cellar, and her ring is down there somewhere.
[The Rat Cellar] Stage 1: Go down to the cellar and kill three rats.
Mira says, "Mind the big one."

> down
You leave down.
[The Rat Cellar] visit The Cellar: 1/1
  ...

> quests
Your quests:
  The Rat Cellar (stage 1 of 2)
    Go down to the cellar and kill three rats.
      visit The Cellar: 1/1
      kill rat: 0/3

  (three rats later)
[The Rat Cellar] kill rat: 3/3
[The Rat Cellar] Stage 2: Find Mira's ring and bring it back to her.

> get ring
[The Rat Cellar] collect Mira's ring: 1/1
[The Rat Cellar] Done. Return to Mira (quest complete The Rat Cellar).
You pick up Mira's ring.

> up
  ...
  Mira (?)

> quest complete
Quest complete: The Rat Cellar!
You gain 50 character points.
You receive 25 credits.
Mira presses a free drink token into your hand.
```

The ring is gone (`consume`), and `quests done` lists The Rat Cellar.
Under Merc the award is experience ("You gain 50 experience."). A door
that opens only to those who helped Mira:

```text
@lock pantry = quest_state(caller, 'The Rat Cellar') == 'done'
```

## The definition

A quest is an object tagged `quest_def`; its name is the quest's name
(players type any unique part of it: `quest accept rat`). Its attributes:

| Attribute | Meaning |
|---|---|
| `description` | shown when it is offered, accepted and in `quest <name>` |
| `giver` | the NPC that offers it and takes it back: a name (`"Mira"`), an `#id`, or a matcher dict (`{"tag": "innkeeper"}`); none for a quest taken anywhere, which completes the moment its last objective is met |
| `accept_lock` | a lock expression over the player (`caller`): `get_attr(caller, 'level', 1) >= 5`, `quest_state(caller, 'The Rat Cellar') == 'done'` |
| `stages` | an ordered list of `{"text": ..., "objectives": [...]}`; a stage ends when all its objectives are met |
| `rewards` | `award` (the game system's advancement, through `award`), `credits`, `items` (prototypes to clone), `achievement`, `tags` |
| `repeatable` | false (once only), or the seconds before it may be taken again (`0`: at once) |
| `time_limit` | seconds to finish it, or none |
| `scope` | `character` (the default) or `account`: done once for every character on the account |
| `on_accept`, `on_stage`, `on_complete`, `on_fail` | softcode run at each point, as the quest object, with the player as `enactor` and the event's data in `adata()` |

A definition is checked when definitions load (at boot, `@reload`, and
whenever a `quest_def` changes): an unknown objective kind or key, a quest
with no stages, a stage with no objectives, two objectives of a stage with
the same key, or a reward item naming no prototype is logged at WARNING,
naming the quest and what is wrong, and that quest is skipped until it is
fixed.

A **giver** is an NPC (tagged `npc`) or anything with the `quest_giver`
behavior. The behavior's `quests` parameter lists quests an object offers
without being their `giver`: a bounty board, or a clerk who hands out work
someone else pays for:

```text
@behavior clerk = quest_giver, quests:["Courier run"]
```

`quest list` shows what the givers in your room offer you (a quest whose
lock you fail is not shown); `quest accept` takes one offered here, or any
quest that has no giver.

## Objectives

Each objective is a dict with a `kind`, a `count` (1 unless given), an
optional `key` (by default its kind; two objectives of the same kind in a
stage need their own) and `text` (how the journal names it), and a
**matcher**: any of `id`, `name`, `tag` and `prototype_vnum`, all of which
must agree. A `name` matches as players' typing does (`rat` matches "a
fat rat"; no partial words in the middle).

| Kind | Counts | Example |
|---|---|---|
| `kill` | a death the player is credited with: their own kill, their companion's, or one by a member of their party in the room | `{"kind": "kill", "prototype_vnum": 3062, "count": 5}` |
| `collect` | what the player holds now (in containers too); `"consume": true` takes the items when the stage ends (at the hand-in, for the last stage of a quest with a giver) | `{"kind": "collect", "tag": "relay", "count": 5, "consume": true}` |
| `deliver` | an item given to an NPC; `to` names the recipient (a name, `#id` or matcher) | `{"kind": "deliver", "name": "sealed orders", "to": "Harbor Agent"}` |
| `visit` | arriving in a room | `{"kind": "visit", "tag": "shrine"}` |
| `talk` | `talk <npc>` | `{"kind": "talk", "name": "hermit"}` |
| `use` | `use` of an object (the thing used, or the item used on it) | `{"kind": "use", "id": "lever_room4"}` |
| `custom` | only softcode, through `quest_advance` | `{"kind": "custom", "key": "oath", "text": "swear the oath"}` |

The counts are kept per stage; when a stage ends, the next begins with
its text and its `on_stage` softcode. Finishing the last stage completes a
quest with no giver at once, and makes one with a giver **ready**: the
player hands it in with `quest complete` beside the giver, which checks
the last stage again (a `collect` item dropped since must be fetched
back).

## Players

| Command | |
|---|---|
| `quests` (`journal`) | your quests, each with its stage, its objectives and any time left |
| `quests done` | the quests you have finished |
| `quest list` | what the givers here offer you |
| `quest <name>` | one quest in detail: description, stage, counts, rewards |
| `quest accept <name>` | take it |
| `quest complete [<name>]` | hand it in to its giver (with no name, every finished quest this giver takes) |
| `quest abandon <name>` | give it up; it may be taken again |
| `talk <someone>` | talk to an NPC: their `ON_TALK` softcode answers, `talk` objectives count, and a giver tells you what it has for you |

`talk` with no name, or a name nobody here answers to, goes to the
world's softcode `$`-commands first, so an NPC's own `$talk` (a dialogue
tree, [067](../showcase/067_dialogue_tree_npc.md)) still works.

In room listings, `(!)` beside a giver means it has a quest you may take,
and `(?)` that it waits for one you have finished.

## Rewards

Paid on completion, each through what already exists:

- `award`: the `rules` service's `award`, so the game system decides what
  it is (experience under Merc, character points under GURPS and D20) and
  the award filters apply (hunger halves it, a clan takes its tax);
- `credits`: the `economy` service;
- `items`: a copy of each prototype (an object id, `"#rom_obj_3011"`, or
  the name of one object tagged `prototype`), in the player's hands;
- `achievement`: the `achievements` service's `grant`;
- `tags`: added to the character.

A reward whose feature is not in the world is skipped with a WARNING
naming the quest; the rest are paid.

## Repeating, time limits, accounts

`repeatable` is the cooldown in seconds: `3600` lets a quest be taken
again an hour after it was last finished. `time_limit` is seconds from
accepting to handing in; a reaper fails a quest past its deadline ("You
have run out of time"), with `on_fail` and `QUESTFAIL` (`reason`
`expired`). A character who logs out with the clock running finds the
quest failed when they log back in. A failed or abandoned quest may be
taken again at once.

`scope` `account` records the quest as done on the account
(`quests_done` there), so every character on it has done it; while one
character is on it, another may take it too. Character scope (the
default) records it on the character.

A character's progress is two attributes, visible in `@examine`:
`quests`, `{"the rat cellar": {"stage": 2, "counts": {}, "accepted": ...,
"deadline": null}}` (`stage` is `"ready"` while waiting to be handed in),
and `quests_done`, `{"the rat cellar": <when>}`.

## Softcode

`quest_state` and `quest_count` are read-only, and so are there in lock
expressions too, where the one trying is `caller`:

| Function | |
|---|---|
| `quest_state(obj, quest)` | None (never taken, or failed), the stage number (1 is the first), `'ready'` or `'done'` |
| `quest_count(obj, quest, key)` | how far `obj` is on the objective `key` of their current stage |
| `quest_offer(obj, quest)` | start the quest for `obj` as if they accepted it; False when they may not take it (builders; after the script) |
| `quest_advance(obj, quest, key, by=1)` | count toward the objective `key` of the current stage (builders; after the script) |
| `quest_complete(obj, quest)` | complete it now and pay its rewards (builders; after the script) |
| `quest_fail(obj, quest)` | end it unfinished, reason `failed` (builders; after the script) |

```text
@set altar/on_use = if target is me: quest_advance(enactor, 'The Oath', 'oath')
@set note/on_get = if target is me: quest_offer(enactor, 'The Lost Brother')
@lock gate = quest_state(caller, 'The Rat Cellar') == 'done'
```

The builder functions need the HARM entitlement, so the object running
them must belong to a builder; what they do lands when the script ends.

The events: `quest:on_accept` (`QUESTACCEPT`), `quest:on_advance`
(`QUESTADVANCE`; `adata('stage')` is the new stage number, or `'ready'`),
`quest:on_complete` (`QUESTCOMPLETE`) and `quest:on_fail` (`QUESTFAIL`;
`reason`: expired, abandoned or failed), each with `adata('quest')` and the
player as `enactor`. Accepting from a giver and handing in to one make the
giver the event's target, so the giver's own `ON_QUESTACCEPT` and
`ON_QUESTCOMPLETE` can answer (guard them with `if target is me:`);
otherwise the target is the quest object. `talk <npc>` fires
`quest:on_talk` (`TALK`) on the NPC.

A branching quest stays softcode ([201](../showcase/201_branching_quest.md)):
the branch is an attribute the player's choice sets, and a `custom`
objective puts the choice in the journal.

## The Midgaard quest

The Midgaard template ships one quest, `data/quests.json`, imported by its
`init_world`: in the Bakery, the baker offers "Fido trouble", five of the
beastly fidos for 250 experience and a loaf of bread, repeatable hourly.
(The converted area places no baker, so `init_world` makes one from its
prototype, with a loaf to sell.) A world made before
the quest existed does not have it (`init_world` runs on an empty
database only); build it with the commands above.

## Where it comes from

tbaMUD's autoquests (`src/quest.c`, `src/quest.h`) and CoffeeMud's
QuestMaker templates (`resources/quests/templates/*.quest`).

Taken: from tbaMUD, the questmaster who lists, gives and takes back quests
(`quest list`, `join`, `leave`, `progress`, `history` became `quest list`,
`accept`, `abandon`, `quests`, `quests done`); its objective types
(object find, room find, mob find, mob kill, object return became
`collect`, `visit`, `talk`, `kill`, `deliver`); the time limit, the
repeatable flag, the gold, experience and object rewards. From CoffeeMud,
the templates' criteria as a mask (here a lock expression), the duration,
"multiple" quests (a cooldown here), the collect, delivery, killer and
travel templates, a count of killables, and the win and accept speech
(here the giver's `ON_QUESTACCEPT`/`ON_QUESTCOMPLETE` and the quest's
softcode).

Changed: several stages, each with several objectives, where tbaMUD has
one objective per quest and chains quests by `next`/`prev` (here an
`accept_lock` on `quest_state`); a quest may be held alongside others
(tbaMUD allows one at a time); party and companion kills count.

Left out: tbaMUD's quest points and the penalty for quitting, "save a mob"
and "clear a room"; CoffeeMud's escort, protect, capture, dispel and
invasion templates, quests that start on a timer for the whole world
(auto, competitive, random and holiday quests), faction and quest-point
rewards. Each can be built with `custom` objectives and the hooks.
