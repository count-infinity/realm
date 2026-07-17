# 002. Vending Machine

> Checklist item 2 — [now] — *ON_PAYMENT, create_obj from prototype attrs, spawner vocabulary*

**What you'll build:** A vending machine with a browsable menu. Feed it
credits with `pay`, then `vend coffee` — it spawns a fresh item into
the room's "tray", charges your machine-credit, and tracks stock per
selection.

**Concepts:** Product *prototypes as attributes* (data describing an
object before it exists), `create_obj()` — the spawner vocabulary,
banked per-player credit via `ON_PAYMENT` + `adata('amount')`, multiple
`$`-commands on one object, wildcard captures (`$vend *` → `arg0`),
guard-style validation, and why this command couldn't be called `buy`.

Builds on the [magic 8-ball](005_magic_8ball.md) (triggers) and the
[slot machine](001_slot_machine.md) (payments and the event namespace).

## How it works

**Prototypes are just data.** A product needs a name, a price, a
weight. Store each as a JSON dict in an `item_<selection>` attribute
and the machine can *mint* the real object on demand with
`create_obj(name)` — no hand-`@create`ing every can of coffee, and the
definition lives in exactly one place. New behavior → a scripted
object; new *flavor* of a thing → a prototype attribute. That's the
spawner vocabulary in miniature (the `spawner` behavior and `@clone`
industrialize the same idea).

**Definitions vs. state.** What a coffee *is* (`item_coffee`) is set
once. What changes per machine is mutable state in its own attributes:
`stock_coffee` counts down, `credit_<player>` banks what you've fed
in. Two machines can carry the same menu at different prices and run
dry independently; restocking is one `@set`.

**Money in, the slot-machine way.** The machine can't take money from
you — you `pay` it (consent), its `ON_PAYMENT` fires, and
`adata('amount')` is what you fed in. Unlike the slot machine it
doesn't demand exact change: everything you feed it accumulates as
*your* credit on *this* machine, spent selection by selection. Overpay
now, vend twice later.

**Why `vend`, not `buy`?** Built-in commands dispatch before
`$`-triggers, and `buy` is the built-in shopkeeper command — a `$buy *`
trigger on the machine would never fire (you'd get `There's no merchant
here.`). Naming object commands *around* the builtins is a fact of
softcode life; `vend` and `browse` are unclaimed. (When you want a
merchant with a face and haggling, use the `shopkeeper` behavior and
the real `buy` — this build is for furniture that sells things.)

## Build it

The cabinet, with a per-viewer credit readout in the description
(`viewer` is whoever is looking — each player sees their own balance):

```text
@create vending machine
drop vending machine
@desc vending machine = A humming slab of scratched enamel and glass. Goods sleep in their spiral coils. [[result = f'The display reads CREDIT: {V("credit_" + viewer.id, 0)}.']]
```

The menu — an index list plus one prototype dict and one stock counter
per selection (`@set` parses JSON, so lists and dicts store as real
lists and dicts):

```text
@set vending machine/menu = ["coffee", "ration"]
@set vending machine/item_coffee = {"name": "bulb of cold coffee", "price": 25, "weight": 1}
@set vending machine/item_ration = {"name": "vacuum-sealed ration", "price": 40, "weight": 2}
@set vending machine/stock_coffee = 5
@set vending machine/stock_ration = 2
```

Coin intake — bank the payment as the payer's credit, in one line.
`incr(k, adata('amount'))` adds the amount the action carries to the
attribute *and* hands back the new value, so a single call does the
read, the write, and the readout:

```text
@set vending machine/on_payment = k = 'credit_' + enactor.id; bal = incr(k, adata('amount')) if target is me else None; pemit(enactor, f'The display blinks. CREDIT: {bal}. Type vend <selection>.') if bal else None
```

The menu browser — a loop (scripts are sandboxed Python, so a list
comprehension over `menu` prints one line per selection, joining the
prototype's price and name with the live stock count):

```text
@set vending machine/cmd_browse = $browse: menu = V('menu', []); pemit(enactor, 'Selections (pay first, then vend <selection>):'); [pemit(enactor, f'  {sel} - {V("item_" + sel)["price"]} cr - {V("item_" + sel)["name"]} ({V("stock_" + sel, 0)} left)') for sel in menu]
```

And the vend itself. `$vend *` captures the selection as `arg0`. The
script is a chain of *guards* — each failure case gets its own
specific, numeric message, and only when every check passes does the
final tuple commit all four effects together: charge the credit,
decrement stock, spawn the item (`create_obj` births it in the room —
the "tray"; `set_attr` immediately stamps the prototype's weight on
it), and announce to everyone:

```text
@set vending machine/cmd_vend = $vend *: sel = trim(arg0).lower(); item = V('item_' + sel); k = 'credit_' + enactor.id; bal = V(k, 0); left = V('stock_' + sel, 0); price = item['price'] if item else 0; ok = bool(item) and left > 0 and bal >= price; pemit(enactor, 'The panel blinks: NO SUCH SELECTION. Try browse.') if not item else None; pemit(enactor, f'The {sel} coil is empty. SOLD OUT.') if item and left < 1 else None; pemit(enactor, f'CREDIT {bal} of {price}. Feed it: pay {price - bal} to vending machine.') if item and left > 0 and bal < price else None; (decr(k, price), decr('stock_' + sel), set_attr(create_obj(item['name']), 'weight', item['weight']), remit(here, f'The vending machine whirs and drops a {item["name"]} into the tray.')) if ok else None
```

The `weight` attribute is not decorative — it's exactly what the
[sack tutorial](014_basic_container.md) weighs next.

## Try it

```text
@eval adjust_credits(me, 200); result = credits(me)
browse
vend coffee
pay 25 to vending machine
look vending machine
vend coffee
get bulb of cold coffee
vend gruel
```

Expected beats: `browse` lists `coffee - 25 cr - bulb of cold coffee
(5 left)`; the first `vend coffee` refuses with the exact shortfall —
`CREDIT 0 of 25. Feed it: pay 25 to vending machine.`; after paying,
`look vending machine` shows *your* `CREDIT: 25` on the display; the
second `vend coffee` whirs, drops a freshly minted bulb into the room,
and `get` picks it up; `vend gruel` blinks `NO SUCH SELECTION`. Run
`browse` again — coffee reads `(4 left)`. Pay 80 and `vend ration`
three times to watch the coil run dry: the third answers `The ration
coil is empty. SOLD OUT.`

Repricing or restocking a live machine is plain `@set` surgery:
`@set vending machine/stock_coffee = 99`.

## Engine gaps

- `create_obj()` can name and tag the spawned item and scripts can
  `set_attr` data onto it, but there is no softcode way to set the
  *render description* — `look` reads the engine-level description
  field (what `@desc` writes), not a `description` attribute, for
  things. Dispensed goods are name-only until a builder `@desc`es them
  or an engine hook lands.

## Going further

- **Restock on a timer:** `@behavior vending machine = script_ticker,
  interval:300` plus an `on_tick` script that tops each `stock_<sel>`
  counter back up.
- **A coin return:** add `$refund` — pay back
  `V('credit_' + enactor.id, 0)` with `transfer_credits`, then zero the
  credit.
- **Emptying the cash box:** the machine's own balance is the take;
  a `$collect` command gated on `owner(me) == enactor` pays it out to
  the owner — or leave it and let `look` at the hopper brag for you.
- **Data-driven everything:** move the whole menu into one dict
  attribute and iterate it — then `@clone` the machine and edit only
  data to open a second kiosk.
