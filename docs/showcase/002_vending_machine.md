# 002. Vending Machine

> Checklist item 2 ([now]): *ON_PAYMENT, create_obj from prototype attrs, spawner vocabulary*

**What you'll build:** A vending machine with a browsable menu. Feed it
credits with `pay`, then `vend coffee`, and it spawns a fresh item into the
room's "tray", charges your machine credit, and tracks stock per selection.

**Concepts:** product *prototypes as attributes* (data describing an object
before it exists), [`create_obj`](../reference/softcode.md#fn-create_obj) as the
spawner vocabulary, banked per-player credit via
[`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks) plus the
[event data namespace](../reference/softcode.md#event-data-namespace), several
`$`-commands on one object, wildcard captures (`$vend *` gives `arg0`),
guard-style validation, and why this command cannot be called `buy`.

It builds on the [magic 8-ball](005_magic_8ball.md) for triggers and the
[slot machine](001_slot_machine.md) for payments and the event namespace.

## How it works

A vending machine is one object carrying two kinds of data: a small menu of
product *definitions* that never change, and per-machine *state* (stock and
each player's credit) that does. A `pay` banks credit through an `ON_PAYMENT`
hook, `browse` prints the menu, and `vend` runs a chain of guards that, when
they all pass, mints the product and charges you. This section explains each
piece and why it takes the form it does.

### Why store products as data, not objects

A product needs a name, a price, a weight, and a description. Store each as a
JSON dict in an `item_<selection>` attribute, and the machine can mint the real
object on demand with
[`create_obj`](../reference/softcode.md#fn-create_obj), so you never
hand-`@create` a can of coffee and the definition lives in exactly one place.
The rule of thumb: new *behavior* means a scripted object, but a new *flavor* of
a thing is just a prototype attribute. That is the spawner vocabulary in
miniature, and the `spawner` behavior and `@clone` industrialize the same idea.

### Definitions versus state

What a coffee *is* (`item_coffee`) is written once, whereas what changes per
machine is mutable state in its own attributes: `stock_coffee` counts down and
`credit_<player>` banks what each player has fed in. Two machines can carry the
same menu at different prices and run dry independently, and restocking is a
single `@set`.

### How the machine knows a payment was for it

The machine cannot take money from you, so instead you `pay` it, which is
consent, its [`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks) fires, and
[`adata('amount')`](../reference/softcode.md#event-data-namespace) is what you
fed in. Because `ON_PAYMENT` reaches every object in the room, the hook first
checks [`target is me`](../reference/softcode.md#guard-on-target) so a coin
handed to someone else never credits the machine. Unlike the [slot machine](001_slot_machine.md) it
does not demand exact change: everything you feed it accumulates as *your*
credit on *this* machine, spent selection by selection, so you can overpay now
and vend twice later.

### Why `vend`, not `buy`

Built-in commands dispatch before `$`-triggers, and `buy` is the built-in
shopkeeper command, so a `$buy *` trigger on the machine would never fire (you
would get `There's no merchant here.`). Naming object commands *around* the
builtins is a fact of softcode life, and `vend` and `browse` are unclaimed.
When you want a merchant with a face and haggling, use the `shopkeeper`
behavior and the real `buy`; this build is for furniture that sells things.

## Build it

The three scripts here are `'''` multi-line blocks (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs));
the menu is plain data.

The cabinet carries a per-viewer credit readout in its description, where
`viewer` is whoever is looking, so each player sees their own balance:

```text
@create vending machine
drop vending machine
@desc vending machine = A humming slab of scratched enamel and glass. Goods sleep in their spiral coils. [[result = f'The display reads CREDIT: {V("credit_" + viewer.id, 0)}.']]
```

The menu is an index list plus one prototype dict and one stock counter per
selection, and each prototype now carries the `desc` the dispensed item will
wear (`@set` parses JSON, so the lists and dicts store as real lists and dicts):

```text
@set vending machine/menu = ["coffee", "ration"]
@set vending machine/item_coffee = {"name": "bulb of cold coffee", "price": 25, "weight": 1, "desc": "A dented bulb, beaded with condensation and unpleasantly warm to the touch."}
@set vending machine/item_ration = {"name": "vacuum-sealed ration", "price": 40, "weight": 2, "desc": "A drab brick of vacuum-sealed calories, stamped with a use-by date long past."}
@set vending machine/stock_coffee = 5
@set vending machine/stock_ration = 2
```

Coin intake banks the payment as the payer's credit. The hook guards on
[`target is me`](../reference/softcode.md#guard-on-target) first, then
[`incr(k, adata('amount'))`](../reference/softcode.md#fn-incr) adds the amount
the action carries to the attribute *and* returns the new value, so a single
call does the read, the write, and the readout:

```text
@set vending machine/on_payment = '''
if target is me:  # ON_PAYMENT fires on every object in the room, so guard it
    k = 'credit_' + enactor.id
    bal = incr(k, adata('amount'))  # add the payment, and return the new balance
    pemit(enactor, f'The display blinks. CREDIT: {bal}. Type vend <selection>.')
'''
```

The menu browser is a loop: scripts are sandboxed Python, so a `for` over
`menu` prints one line per selection, joining each prototype's price and name
with the live stock count. Each line reaches the looker with
[`pemit`](../reference/softcode.md#fn-pemit):

```text
@set vending machine/cmd_browse = '''
$browse:
menu = V('menu', [])
pemit(enactor, 'Selections (pay first, then vend <selection>):')
for sel in menu:
    item = V('item_' + sel)
    pemit(enactor, f'  {sel} - {item["price"]} cr - {item["name"]} ({V("stock_" + sel, 0)} left)')
'''
```

Finally the vend itself, where `$vend *` captures the selection as `arg0`. The
script is a chain of *guards*: each failure case gets its own specific, numeric
message, and only the final `else` commits all four effects together. It charges
the credit with [`decr`](../reference/softcode.md#fn-decr), decrements the stock,
mints the item with [`create_obj`](../reference/softcode.md#fn-create_obj) (which
names it, writes its description, and stamps the prototype's weight in one call,
born in the room that serves as the tray), and announces the drop to everyone
present with [`remit`](../reference/softcode.md#fn-remit):

```text
@set vending machine/cmd_vend = '''
$vend *:
sel = trim(arg0).lower()  # normalize the wildcard capture: trim spaces, lowercase
item = V('item_' + sel)
k = 'credit_' + enactor.id
bal = V(k, 0)
left = V('stock_' + sel, 0)
if not item:
    pemit(enactor, 'The panel blinks: NO SUCH SELECTION. Try browse.')
elif left < 1:
    pemit(enactor, f'The {sel} coil is empty. SOLD OUT.')
elif bal < item['price']:
    pemit(enactor, f'CREDIT {bal} of {item["price"]}. Feed it: pay {item["price"] - bal} to vending machine.')
else:
    decr(k, item['price'])
    decr('stock_' + sel)
    create_obj(item['name'], description=item['desc'], attrs={'weight': item['weight']})  # mint into the room, the tray
    remit(here, f'The vending machine whirs and drops a {item["name"]} into the tray.')
'''
```

The `weight` attribute is not decorative, since it is exactly what the
[sack tutorial](014_basic_container.md) weighs next.

## Try it

```text
> @eval adjust_credits(me, 200); result = credits(me)
  200
> browse
  Selections (pay first, then vend <selection>):
    coffee - 25 cr - bulb of cold coffee (5 left)
    ration - 40 cr - vacuum-sealed ration (2 left)
> vend coffee
  CREDIT 0 of 25. Feed it: pay 25 to vending machine.
> pay 25 to vending machine
  The display blinks. CREDIT: 25. Type vend <selection>.
> look vending machine
  A humming slab of scratched enamel and glass. Goods sleep in their spiral coils.
  The display reads CREDIT: 25.
> vend coffee
  The vending machine whirs and drops a bulb of cold coffee into the tray.
> look bulb of cold coffee
  A dented bulb, beaded with condensation and unpleasantly warm to the touch.
> get bulb of cold coffee
  You pick up a bulb of cold coffee.
> vend gruel
  The panel blinks: NO SUCH SELECTION. Try browse.
```

The first `vend coffee` refuses with the exact shortfall, and after paying,
`look vending machine` shows *your* `CREDIT: 25` on the display because the
description reads `credit_<your id>`. The vended bulb now carries a real
description, so `look bulb of cold coffee` reads it back rather than showing a
bare name. Run `browse` again and coffee reads `(4 left)`. Pay 80 and `vend
ration` twice to watch the coil run dry: the third answers `The ration coil is
empty. SOLD OUT.`. Repricing or restocking a live machine is plain `@set`
surgery, as in `@set vending machine/stock_coffee = 99`.

## Going further

- **Restock on a timer:** attach `@behavior vending machine = script_ticker,
  interval:300` with an `on_tick` script that tops each `stock_<sel>` counter
  back up.
- **A coin return:** add `$refund`, which pays back
  `V('credit_' + enactor.id, 0)` with
  [`transfer_credits`](../reference/softcode.md#fn-transfer_credits) and then
  zeroes the credit.
- **Emptying the cash box:** the machine's own balance is the take, so a
  `$collect` command gated on `owner(me) == enactor` pays it out to the owner,
  or you can leave it and let `look` at the hopper brag for you.
- **Data-driven everything:** move the whole menu into one dict attribute and
  iterate it, then `@clone` the machine and edit only its data to open a second
  kiosk.
