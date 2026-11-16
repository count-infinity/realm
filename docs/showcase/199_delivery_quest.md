# 199. Delivery quest

> Checklist item 199 ([now]): *a `deliver` objective, a time limit, a failure state, a `quest_giver` behavior*

**What you'll build:** the simplest quest done properly. Postmaster Vane
hands you sealed orders and a five-minute clock; carry them across town to
the Harbor Agent in time and you are paid, run out of time and the orders
go stale: the Agent refuses them and pushes them back into your hands.

**Concepts:** the fetch/carry template as a **`deliver` objective** on the
engine's [quests](../guides/quests.md); a **`time_limit`** the engine
enforces; **`on_accept`** and **`on_fail`** softcode on the quest (minting
the orders, marking them stale); the **`quest_giver` behavior** on the NPC
who offers it; and reading
[`adata('item')`](../reference/softcode.md#event-data-namespace) in the
recipient's [`ON_RECEIVE`](../reference/softcode.md#lifecycle-hooks).

## How it works

A delivery quest is a triangle: a giver who issues the errand, a carrier
item that travels, and a recipient. The `quests` feature holds the errand
and its clock; the two NPCs and the orders only add colour. This section
answers three questions: who offers the quest, how the hand-over counts,
and what happens when the clock runs out.

### Who offers it?

Vane carries the `quest_giver` behavior, whose `quests` parameter lists
"Courier run", so `quest list` in the post office shows it and a `(!)`
marks Vane. The quest itself has no `giver`: a quest without one completes
the moment its last objective is met, so there is no walk back to Vane, and
it can also be taken with `quest accept` anywhere (the behavior is how
players find it). Its `on_accept` softcode mints the orders into the
courier's hands. Like every quest script it runs as the quest's definition
object, with the courier as `enactor`, and with its owner's authority: the
definition must belong to a builder to put objects in a player's
inventory.

### How does the hand-over count?

`give` fires `item:on_give`, naming the item and the recipient. The quest's
objective is `{"kind": "deliver", "tag": "orders", "to": "Harbor Agent"}`:
an item tagged `orders`, given to the Harbor Agent. Handing them to anyone
else counts nothing, and the quest stays open. The engine pays the 60
credits when it counts; the Agent's `ON_RECEIVE` only answers out loud and
takes the orders.

### What happens when the clock runs out?

`time_limit` is 300 seconds. A reaper fails any quest past its deadline
(for a courier who logged out, the moment they log back in), and `on_fail`
runs: here it tags the courier's orders `stale`. The quest is over, so
handing in stale orders counts nothing; the Agent sees the tag and pushes
them back. `repeatable` lets the courier take another run a minute after
finishing one; a failed run may be taken again at once.

## Build it

Stand in the post office. Dig the harbor across town, then create
Postmaster Vane and give them the `quest_giver` behavior:

```text
@dig The Harbor Office = harbor, back
@create Postmaster Vane
@tag Postmaster Vane = npc
drop Postmaster Vane
@behavior Postmaster Vane = quest_giver, quests:["Courier run"]
```

The quest: one stage, one `deliver` objective, a clock, a reward, the
orders minted on accepting and spoiled on failing:

```text
@create Courier run
@tag Courier run = quest_def
@set Courier run/description = Carry Vane's sealed orders to the Harbor Agent before they go stale.
@set Courier run/stages = [{"text": "Deliver the sealed orders to the Harbor Agent.", "objectives": [{"kind": "deliver", "tag": "orders", "to": "Harbor Agent", "text": "deliver the sealed orders"}]}]
@set Courier run/time_limit = 300
@set Courier run/repeatable = 60
@set Courier run/rewards = {"credits": 60}
@set Courier run/on_accept = create_obj('sealed orders', ['thing', 'orders'], location=enactor)
@set Courier run/on_fail = [add_tag(o, 'stale') for o in contents(enactor) if has_tag(o, 'orders')]
```

Walk to the harbor and create the recipient. Their `ON_RECEIVE` gates on
the target (the hook fires on every object in the room), reads the item off
the event, and takes fresh orders or pushes stale ones back:

```text
harbor
@create Harbor Agent
@tag Harbor Agent = npc
drop Harbor Agent
@set Harbor Agent/on_receive = '''
if target is me:
    orders = adata('item')
    courier = adata('giver')
    if orders and courier and has_tag(orders, 'orders'):
        if has_tag(orders, 'stale'):
            teleport_obj(orders, courier)
            say('These orders are stale. I cannot accept them.')
        else:
            destroy_obj(orders)
            say('The orders, at last. Sixty credits for your trouble.')
'''
back
```

## Try it

As Raven, standing in the post office:

```text
> quest list
Postmaster Vane offers:
  Courier run - Carry Vane's sealed orders to the Harbor Agent before they go stale.
(quest accept <name> to take one)

> quest accept courier
Quest accepted: Courier run.
Carry Vane's sealed orders to the Harbor Agent before they go stale.
[Courier run] Stage 1: Deliver the sealed orders to the Harbor Agent.
You have 5 minutes to finish it.

> quest accept courier
You are already on Courier run.

> harbor
You leave harbor.
...

> give sealed orders to Harbor Agent
[Courier run] deliver the sealed orders: 1/1
Quest complete: Courier run!
You receive 60 credits.
You give a sealed orders to Harbor Agent.
Harbor Agent says, "The orders, at last. Sixty credits for your trouble."
```

`credits` reads sixty higher and the orders are gone. `quests` shows the
journal empty again; `quests done` lists Courier run, and `quest accept
courier` answers "You may take Courier run again in 60 seconds."

Now the failure state. Take a fresh run and let five minutes pass:

```text
You have run out of time: Courier run has failed.

> give sealed orders to Harbor Agent
You give a sealed orders to Harbor Agent.
Harbor Agent says, "These orders are stale. I cannot accept them."
```

The orders are in your inventory again, tagged `stale`, and unpaid. The
target guard is worth testing too: with a bystander standing in the office,
`give sealed orders to <bystander>` gets you nothing at all, and `quests`
still shows the run open, because the objective names the Harbor Agent.

## Going further

- **A return leg.** Set `giver` to `Postmaster Vane` and the run is not
  done on delivery: it is *ready*, and Vane pays when you come back and
  `quest complete`.
- **Several drops.** Give the stage two `deliver` objectives, each with its
  own `key` (`{"kind": "deliver", "key": "harbor", ...}`, `{"kind":
  "deliver", "key": "mill", ...}`), and both must be made, in any order.
- **A chain.** A second stage after the first makes the courier carry the
  Agent's reply back; `on_stage` can mint it as `on_accept` minted the
  orders.
- **A slower clock in game time.** `time_limit` is real seconds; for "by
  nightfall" let an `on_dusk` hook on the post office call
  [`quest_fail`](../reference/softcode.md#fn-quest_fail) for whoever is
  still on the run.
