# 198. Quest framework

> Checklist item 198 ([now]): *the `quests` feature: a `quest_def` with stages, the journal, a giver, completion hooks and a quest lock*

**What you'll build:** the Quest Warden and "The Cinder Road", a two-stage
quest on the engine's [quests](../guides/quests.md). A player takes it from
the Warden, finds the toll ledger, brings it back and is paid; the journal
keeps their place, the Warden thanks them out loud, and a gate opens only to
those who have finished it.

**Concepts:** a quest as **data** (a `quest_def` object), **stages** of
**objectives** the engine tracks itself, the **giver** who offers it and
takes it back, the **journal** (`quests`), a **completion hook**
(`ON_QUESTCOMPLETE`), and [`quest_state`](../reference/softcode.md#fn-quest_state)
in a **lock expression**.

## How it works

A quest is engine data, not a script you write by hand. The `quests`
feature (MUD_PLAN step 15) keeps each player's progress, watches the world
for what their objectives ask for, and pays the rewards; a builder only
writes down what the quest is. This section answers three questions: what a
quest is made of, how the engine notices progress, and how the rest of the
world reacts to it.

### What is a quest made of?

A `quest_def` object. Its `stages` are an ordered list, and each stage is a
line of text and a list of **objectives**: `kill`, `collect`, `deliver`,
`visit`, `talk`, `use`, or `custom` for one only softcode moves. The
Cinder Road has two stages: *use* the toll ledger where it lies (searching
the ruin), then *collect* it and bring it home. `giver` names the NPC who
offers the quest and takes it back; `rewards` says what the player gets.
Adding a second quest is making a second object; no code changes.

Progress lives on the player, in a `quests` attribute (`{"the cinder road":
{"stage": 2, ...}}`), and a finished quest moves to `quests_done`. Both
show in `@examine`, and both survive a reboot.

### How does the engine notice progress?

It watches the events the world already has. Using the ledger fires
`item:on_use`; picking it up fires `item:on_get`; the quests feature reads
both and counts them for whoever is on a stage that asks for them. Nothing
on the ledger needs a script, and nothing needs the `if target is me:` guard
a softcode counter would (the engine compares the event's own target).

When the last stage is met, a quest with a giver is **ready**: the player
hands it in with `quest complete` at the Warden, and only then is it done
and paid. The `consume` flag on the collect objective takes the ledger at
that moment.

### How does the world react?

Through the quest's events. Taking, advancing, completing and failing a
quest fire `QUESTACCEPT`, `QUESTADVANCE`, `QUESTCOMPLETE` and `QUESTFAIL`;
when it happens at the giver, the giver is the event's target, so the
Warden's own `ON_QUESTCOMPLETE` can speak. And anything with a lock can ask
[`quest_state(caller, 'The Cinder Road')`](../reference/softcode.md#fn-quest_state),
which answers a stage number, `'ready'` or `'done'`.

## Build it

Create the Warden and the ledger beside it (in a full world the ledger
would lie in the burned waystation):

```text
@create Quest Warden
@tag Quest Warden = npc
drop Quest Warden
@create toll ledger
drop toll ledger
```

Now the quest. Make the object, tag it `quest_def`, and set what it is:

```text
@create The Cinder Road
@tag The Cinder Road = quest_def
@set The Cinder Road/description = The waystation burned, and the toll ledger with it, or so they say.
@set The Cinder Road/giver = Quest Warden
@set The Cinder Road/stages = [{"text": "Search the burned waystation for the toll ledger.", "objectives": [{"kind": "use", "name": "toll ledger", "text": "search the toll ledger"}]}, {"text": "Bring the toll ledger to the Quest Warden.", "objectives": [{"kind": "collect", "name": "toll ledger", "consume": true}]}]
@set The Cinder Road/rewards = {"credits": 50}
```

The Warden thanks whoever hands it in, and a gate north opens only to
those who have:

```text
@set Quest Warden/on_questcomplete = if target is me: say('The Cinder Road is open again. Well done.')
@dig The Toll Road = gate, back
@lock gate = quest_state(caller, 'The Cinder Road') == 'done'
```

## Try it

Play a round as Raven, standing in the room with the Warden and the ledger.
The `(!)` beside the Warden says they have a quest for you:

```text
> look
  ...
  Quest Warden (!)
  a toll ledger

> quest list
Quest Warden offers:
  The Cinder Road - The waystation burned, and the toll ledger with it, or so they say.
(quest accept <name> to take one)

> quest accept cinder
Quest accepted: The Cinder Road.
The waystation burned, and the toll ledger with it, or so they say.
[The Cinder Road] Stage 1: Search the burned waystation for the toll ledger.

> quests
Your quests:
  The Cinder Road (stage 1 of 2)
    Search the burned waystation for the toll ledger.
      search the toll ledger: 0/1

> use toll ledger
[The Cinder Road] search the toll ledger: 1/1
[The Cinder Road] Stage 2: Bring the toll ledger to the Quest Warden.
You use the toll ledger.

> get toll ledger
[The Cinder Road] collect toll ledger: 1/1
[The Cinder Road] Done. Return to Quest Warden (quest complete The Cinder Road).
You pick up a toll ledger.

> gate
You can't go gate — it's locked.

> quest complete
Quest complete: The Cinder Road!
You receive 50 credits.
Quest Warden says, "The Cinder Road is open again. Well done."

> gate
You leave gate.
```

The ledger is gone (the collect objective consumed it), `credits` reads 50,
and `quests done` lists The Cinder Road. Before the hand-in the gate
refused: `quest_state` was `'ready'`, not `'done'`.

The refusals are worth a look too. `quest accept dragons` answers "Nobody
here offers that quest. (quest list)", taking it twice answers "You are already on The
Cinder Road.", and `quest complete` with nothing finished answers "You have
no quest ready to hand in."

## Going further

- **Any hook advances.** A `custom` objective counts only when softcode
  says so: `{"kind": "custom", "key": "boss"}` and, on the boss,
  `@set boss/on_death = if target is me and actor: quest_advance(actor,
  'The Cinder Road', 'boss')`. The object running it must belong to a
  builder ([`quest_advance`](../reference/softcode.md#fn-quest_advance) is
  a builder's tool).
- **Prerequisites.** `@set Next Quest/accept_lock = quest_state(caller,
  'The Cinder Road') == 'done'` chains quests into a line; the lock is any
  expression over the player (`level`, a class, a tag).
- **Abandon.** `quest abandon cinder` drops it, fires `QUESTFAIL` with
  `adata('reason') == 'abandoned'`, and the quest may be taken again.
- **Other rewards.** `rewards` also takes `award` (experience or
  character points, through the game system), `items` (prototypes to
  clone), an `achievement` and `tags`.
- **Repeatable work.** `@set The Cinder Road/repeatable = 3600` lets it be
  taken again an hour after it was finished.
