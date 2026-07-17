# 063. Shopkeeper

> Checklist item 63 — [now] — *shopkeeper behavior, list/buy/sell/pay, spawner restock*

**What you'll build:** a merchant NPC on the engine's native `shopkeeper`
behavior — live inventory as stock, disposition-bent prices — plus the
missing 20%: a softcode restock heartbeat that keeps the shelves full, and
an `ON_PAYMENT` tip jar that turns money into goodwill.

**Concepts:** the `shopkeeper` behavior and the `list`/`buy`/`sell`/`pay`
builtins; stock = inventory; `script_ticker` + `on_tick`; `eval_attr`
function attributes; `ON_PAYMENT`; disposition pricing.

## How it works

The shop itself is **one behavior**. `@behavior <npc> = shopkeeper` marks
an NPC as the room's merchant; the `list`, `buy` and `sell` builtins find
it automatically. Its stock is *literally its inventory* — anything the
keeper carries (minus `no_sell`-tagged and wielded items) is for sale at
`value × markup`, and it buys your loot at `value × buyback`. Prices bend
±5% per point of the keeper's disposition toward the customer (capped
±15%): the social system and the economy are the same system.

What the engine doesn't do is *refill the shelves*. Sold stock walks out
in customers' packs and never comes back. So we give the keeper a
heartbeat: `script_ticker` runs the NPC's `on_tick` softcode on a cadence,
and the tick calls a `restock` function attribute that compares the shelf
against a `stocklist` data attribute and mints the difference with
`create_obj` — straight into the keeper's own inventory, because stock is
inventory.

The tip jar rides the payment event: the `pay` builtin propagates
`event:payment`, and any witness's `ON_PAYMENT` softcode fires. The
keeper's thanks the payer and shifts disposition — so a 10-credit tip
measurably lowers every price on the list. Vex has the room to himself,
so his hook can stay this short; note that *every* witness with an
`ON_PAYMENT` hears every payment in the room, so the moment a second
paid NPC moves in, gate on the action's own data — `target == me` is
"the coins are mine", and `adata('amount')` is how many (items
[64](064_bartender.md) and [67](067_dialogue_tree_npc.md) share a
tavern and do exactly that).

**Engine gaps:** the capability audit suggests the `spawner` behavior for
restock, but its liveness check is deletion-based (an ID that still
resolves in the identity map counts as alive) — an item *sold* to a player
is relocated, not deleted, so a spawner would never see the vacancy. The
`script_ticker` + `on_tick` + `create_obj` pattern below is the working
softcode route; `spawner` remains right for populations that die rather
than move (guards, vermin).

## Build it

The merchant, on the native behavior (in Market Square from the arc
prologue — any room works):

```text
@create Trader Vex
@tag Trader Vex = npc
drop Trader Vex
@behavior Trader Vex = shopkeeper, markup:1.3, buyback:0.4
```

Opening stock — priced by each item's `value`, handed straight into the
keeper's inventory:

```text
@create a stimpack
@set a stimpack/value = 20
give a stimpack to Trader Vex
@create a ration bar
@set a ration bar/value = 5
give a ration bar to Trader Vex
```

The restock plan as *data* (`@set` parses JSON): each row is
`[name, level, value]` — keep three stimpacks at value 20, five ration
bars at value 5:

```text
@set Trader Vex/stocklist = [["a stimpack", 3, 20], ["a ration bar", 5, 5]]
```

The restock routine as a function attribute: for each row, count how many
the keeper still carries and mint the shortfall (an empty `range` when the
shelf is full — restocking is naturally idempotent):

```text
@set Trader Vex/restock = [set_attr(create_obj(nm, location=me), 'value', v) for nm, k, v in V('stocklist', []) for j in range(k - len([o for o in contents(me) if name(o) == nm]))]; result = 1
```

The heartbeat — every 8 ticks, run it:

```text
@behavior Trader Vex = script_ticker, interval:8
@set Trader Vex/on_tick = eval_attr(me, 'restock')
```

And the tip jar:

```text
@set Trader Vex/ON_PAYMENT = say(f'Much obliged, {name(enactor)}.'); adjust_disposition(me, enactor, 1)
```

## Try it

```text
@eval adjust_credits(me, 100)
list                        -> a stimpack — 26 credits (20 × 1.3)
buy stimpack                -> yours, 26 credits poorer
@tr Trader Vex/on_tick      -> (or wait ~30s) shelves refill to plan
list                        -> three stimpacks, five ration bars
pay 10 to Trader Vex        -> "Much obliged, Vala."
list                        -> a stimpack — 25 credits (the 5% smile)
sell stimpack               -> 8 credits back (20 × 0.4, tilted by goodwill)
```

The keeper pays buybacks out of its own purse — which your purchases have
been filling. A shop that never sells anything eventually can't buy.

## Going further

- **Gradual restock.** Change the `range(...)` bound to `min(1, ...)` —
  one item per tick, so scarcity is visible and players learn the rhythm.
- **Restock flavor.** End `restock` with
  `say('Fresh stock, straight off the freighter!') if result else None` —
  only when something actually landed on the shelf.
- **Market-linked pricing.** Once the commodity board (tutorial 092)
  exists, have the tick re-price stock:
  `set_attr(o, 'value', ...)` from the board's current index.
- **A choosier tip jar.** The bribed-ogre pattern: gate the hook on
  `adata('amount', 0) >= 10` so small change buys no goodwill, and
  `remove_tag(me, 'hostile')` when a tip clears the bar.
