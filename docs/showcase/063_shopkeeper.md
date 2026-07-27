# 063. Shopkeeper

> Checklist item 63 ([now]): *shopkeeper behavior, list/buy/sell/pay, spawner restock*

**What you'll build:** a merchant NPC on the engine's native `shopkeeper`
behavior, with live inventory as stock and disposition-bent prices, plus the
missing part the behavior leaves to you: a softcode restock heartbeat that
keeps the shelves full, and an `ON_PAYMENT` tip jar that turns money into
goodwill.

**Concepts:** the `shopkeeper` behavior and its `list`/`buy`/`sell`/`pay`
builtins; stock as inventory; disposition pricing;
[`script_ticker`](../reference/softcode.md#lifecycle-hooks) plus an `on_tick`
restock; [`eval_attr`](../reference/softcode.md#fn-eval_attr) function
attributes; the [`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks) hook.

## How it works

A shop in REALM is one behavior with a heartbeat bolted on. The
`shopkeeper` behavior turns an NPC into the room's merchant and prices its
wares; a `script_ticker` fires an `on_tick` script that refills what
customers carry off; and an `ON_PAYMENT` hook lets a tip bend the merchant's
mood. This section walks each piece and says why it takes the shape it does.
Where the [vending machine](002_vending_machine.md) is furniture that sells
things with a home-grown `$vend` command, this build wires up the real
`buy` and gives the seller a face.

### What the behavior gives you for free

`@behavior <npc> = shopkeeper` marks an NPC as the room's merchant, and the
`list`, `buy`, and `sell` builtins find it automatically. The keeper's stock
is literally its inventory: anything it carries (minus `no_sell`-tagged and
`wielded` items) is for sale. A ware costs the customer its `value` times the
keeper's `markup`, and the keeper buys your loot back at `value` times its
`buyback`. `buy` moves the credits with
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits) and then
hands the item across, so a purchase is one atomic exchange; `sell` runs the
same exchange in reverse.

Because the systems compose, price also bends with how the keeper feels about
you: 5% per point of
[`disposition`](../reference/softcode.md#fn-disposition) toward the customer,
capped at plus or minus 15% (the disposition is clamped to plus or minus 3).
A friendly keeper charges less and pays more, so persuading the merchant is
worth real credits. That is why the tip jar below matters.

The keeper refuses cleanly at both edges. If you cannot cover the price,
`buy` reports the exact shortfall and no item moves. If the item is not on the
shelf it is not in the keeper's wares, so `buy` answers that the keeper is not
selling it. And a keeper pays buybacks out of its own purse, so a shop with an
empty till answers `sell` with "can't afford that right now": a merchant that
never sells anything eventually cannot buy.

### Why the shelves need a heartbeat

The one thing the behavior does not do is refill itself. Sold stock walks out
in customers' packs and never returns, so we give the keeper a pulse. The
`script_ticker` behavior runs the NPC's `on_tick` softcode on a cadence, and
that tick calls a `restock` function attribute with
[`eval_attr`](../reference/softcode.md#fn-eval_attr), which evaluates the
attribute as a subroutine and returns its `result`. The routine walks a
`stocklist` data attribute, counts how many of each ware the keeper still
[carries](../reference/softcode.md#fn-contents), and
[mints](../reference/softcode.md#fn-create_obj) the shortfall straight into
the keeper's own inventory, because stock is inventory. Minting only the
shortfall makes the routine idempotent: when the shelf is already full the
count matches the plan and nothing is created.

`eval_attr` runs the routine as the caller, so inside `restock` the name `me`
resolves to the keeper, exactly as it does in `on_tick`. That is why the
routine can read and write the keeper's own inventory with a bare `me`.

### Why not the spawner behavior?

The capability audit suggests the `spawner` behavior for restock, but its
liveness check is deletion-based: it treats an id that still resolves in the
identity map as alive. An item *sold* to a player is relocated, not deleted,
so its id still resolves and a spawner would never see the vacancy. The
`script_ticker` plus `on_tick` plus `create_obj` route below is the working
softcode answer; `spawner` stays right for populations that die rather than
move, such as guards or vermin.

### How the keeper knows a payment was for it

The `pay` builtin moves credits and then propagates `event:payment`, so any
witness's `ON_PAYMENT` softcode fires. The keeper's hook thanks the payer and
shifts disposition, so a 10-credit tip measurably lowers every price on the
list. The catch is that `ON_PAYMENT` reaches *every* object in the room, not
only the one that was paid, so the hook has to check
[`target is me`](../reference/softcode.md#guard-on-target) before it reacts.
Skip that guard and a second merchant in the same market thanks a customer for
coins that went to a rival and pockets the goodwill anyway. Items
[64](064_bartender.md) and [67](067_dialogue_tree_npc.md) share a tavern and
lean on exactly this guard, and read the amount with
[`adata('amount')`](../reference/softcode.md#event-data-namespace).

## Build it

The merchant sits on the native behavior, here in Market Square from the arc
prologue, though any room works:

```text
@create Trader Vex
@tag Trader Vex = npc
drop Trader Vex
@behavior Trader Vex = shopkeeper, markup:1.3, buyback:0.4
```

Give the keeper its opening stock. Each item is priced by its own `value`, and
`give` hands it straight into the keeper's inventory, which is the shelf:

```text
@create a stimpack
@set a stimpack/value = 20
give a stimpack to Trader Vex
@create a ration bar
@set a ration bar/value = 5
give a ration bar to Trader Vex
```

Store the restock plan as data. `@set` parses JSON, so this saves as a real
list of rows, each `[name, keep, value]`: keep three stimpacks at value 20 and
five ration bars at value 5.

```text
@set Trader Vex/stocklist = [["a stimpack", 3, 20], ["a ration bar", 5, 5]]
```

Write the restock routine as a function attribute. For each row it counts how
many the keeper still carries and mints the difference into the keeper's
inventory, stamping each fresh item with its `value`, and sets `result` so the
caller can tell whether anything landed:

```text
@set Trader Vex/restock = '''
result = 0
for nm, keep, value in V('stocklist', []):
    have = len([o for o in contents(me) if name(o) == nm])
    for j in range(keep - have):  # an empty range when the shelf is full, so re-running is safe
        set_attr(create_obj(nm, location=me), 'value', value)
        result = 1
'''
```

Add the heartbeat: every 8 beats the `script_ticker` runs `on_tick`, which is
a single call into the routine, so it stays one line:

```text
@behavior Trader Vex = script_ticker, interval:8
@set Trader Vex/on_tick = eval_attr(me, 'restock')
```

Finally the tip jar. The hook guards on `target is me` first, since
`ON_PAYMENT` fires on every object in the room, then thanks the payer and
nudges disposition up by one:

```text
@set Trader Vex/ON_PAYMENT = '''
if target is me:  # ON_PAYMENT fires on every object in the room, so gate on the target
    say(f'Much obliged, {name(enactor)}.')
    adjust_disposition(me, enactor, 1)
'''
```

## Try it

```text
@eval adjust_credits(me, 100)
list                        -> a stimpack — 26 credits (20 x 1.3)
buy stimpack                -> yours, 26 credits poorer
@tr Trader Vex/on_tick      -> (or wait ~30s) shelves refill to plan
list                        -> three stimpacks, five ration bars
pay 10 to Trader Vex        -> "Much obliged, Vala."
list                        -> a stimpack — 25 credits (the 5% smile)
sell stimpack               -> 8 credits back (20 x 0.4; goodwill lifts the buyback, though it rounds to 8 here)
```

The first `list` shows the single opening stimpack at 26 (its value 20 times
the 1.3 markup). After you buy it and fire `on_tick`, the restock routine
tops the shelves back up to the plan. The `pay` fires the tip jar, which
thanks you and lifts disposition, so the next `list` prices the stimpack at 25
(a 5% discount). The keeper pays buybacks out of the purse your purchases have
been filling, so a shop that never sells anything eventually cannot buy.

## Going further

- **Gradual restock.** Cap the inner loop at one item per beat by replacing
  `range(keep - have)` with `range(min(1, keep - have))`, so scarcity is
  visible and players learn the rhythm.
- **Restock flavor.** End `restock` with a line that speaks only when
  something actually landed: `say('Fresh stock, straight off the freighter!') if result else None`.
- **Market-linked pricing.** Once the commodity board (tutorial 092) exists,
  have the tick re-price stock with `set_attr(o, 'value', ...)` from the
  board's current index.
- **A choosier tip jar.** Gate the hook on `adata('amount', 0) >= 10` so small
  change buys no goodwill, and [`remove_tag`](../reference/softcode.md#fn-remove_tag)`(me, 'hostile')`
  when a tip clears the bar, so paying off a hostile keeper opens the shop.
