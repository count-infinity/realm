# 088. Player-run shop stalls

> Checklist item 88 ([now]): *delegated vendor attrs, on_tick rent, escrow*

**What you'll build:** a rentable market stall. Any player can rent it,
stock it from their own pack, set their own prices, and collect the
takings, while the market charges rent on a heartbeat and repossesses the
pitch when the takings cannot cover it.

**Concepts:** delegated authority (the `$`-verbs on an admin-owned stall
run with the stall owner's authority no matter who types them, so the
script itself is the security policy); escrow via
[`move_to`](../reference/softcode.md#fn-move_to) into the stall's
inventory; an `earnings` attribute that tracks the renter's claim on the
stall's real credit balance; [`script_ticker`](../reference/softcode.md#lifecycle-hooks)
rent on `on_tick`; eviction via
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj) to an absent
player.

## How it works

The stall is one admin-built object carrying a handful of state attributes
(who rents it, what they have earned, when rent is next due) and a family
of `$`-verbs a player types to run the shop. The interesting question is
not the selling but who is allowed to do what to an object they do not
own, so this section starts there, then covers where the money sits and
how goods move on and off the shelf.

### Who is allowed to do what

Because an admin builds the stall, every `$`-verb on it executes as the
stall with the admin's authority, no matter who types the command. That
authority is what lets `stall stock` take an item out of a player's pack,
`stall buy` debit a stranger's wallet, and the rent tick reach anywhere it
needs to. The renter never gains authority over the stall; they gain only
the permissions the script chooses to grant them, so every mutating verb
opens with the same gate,
[`enactor`](../reference/softcode.md#fn-v)`.id == V('renter')`. The
enactor is untrusted input, the executor's owner is the power, and the
script is the policy. A `use` lock could bar players from the stall's
verbs wholesale, but it is per-object, not per-verb, so the split between
renter-only verbs and public ones has to be decided inside the scripts.

### Where the money sits

The money model keeps one honest invariant. A buyer's
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits)`(enactor, me, price)`
lands on the stall's real balance, and an `earnings` attribute records how
much of that balance is the renter's claim. Rent never moves credits at
all: the tick just reduces `earnings` by the rent and leaves the credits
sitting on the stall. So at any moment the stall's balance equals
`earnings` plus every rent charged so far, and the market's income is
whatever the renter can no longer claim.

### How goods move on and off the shelf

Goods are escrowed. `stall stock` uses
[`move_to`](../reference/softcode.md#fn-move_to)`(item, me)` to pull the
item into the stall's inventory, the same pattern the
[auction house](089_auction_house.md) uses, since you cannot sell the
knife you are still holding. `stall buy` hands the item back out with
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj), which the stall
may do to its own contents. The price is an attribute stamped on the
escrowed item (`stall_price`), written by the admin-authority script at the
renter's request, because the renter could never `@set` it on an object
they do not own.

### When rent falls due

Rent is due by arithmetic (`now() >= paid_until`), swept by a
[`script_ticker`](../reference/softcode.md#lifecycle-hooks) `on_tick`. A
tick that finds the takings short does not extend credit: the goods and any
leftover earnings go back to the renter with
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj), which reaches
them wherever they stand, because an eviction should not wait for the
evicted. Note that `on_tick` fires only on the object whose ticker runs it,
so unlike a room-wide `ON_<EVENT>` hook it never needs a `target is me`
guard.

## Build it

The pitch and the stall, built as an admin because the whole delegation
model depends on the stall being admin-owned:

```text
@dig Stall Row
@teleport Stall Row
@create stall three
drop stall three
@set stall three/rent = 20
@set stall three/period = 300
```

`rent stall` is for anyone, if it is free. The first period is paid up
front into the stall (the market's opening take), and
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits) doubles
as the affordability check, since a renter who cannot cover the rent makes
`ok` false and nothing is claimed:

```text
@set stall three/cmd_rent = '''
$rent stall:
ok = not V('renter') and transfer_credits(enactor, me, V('rent', 20))
if ok:
    set_attr(me, 'renter', enactor.id)
    set_attr(me, 'renter_name', name(enactor))
    set_attr(me, 'paid_until', now() + V('period', 300))
    set_attr(me, 'earnings', 0)
    remit(here, f'{name(enactor)} rents stall three and shakes out the awning.')
    pemit(enactor, 'Stall three is yours. Stock it, price it, collect your takings.')
else:
    pemit(enactor, 'The stall is already let, or you cannot cover the rent.')
'''
```

`stall stock <item>` is renter only. The stall takes the named item from
the enactor's pack into escrow with
[`move_to`](../reference/softcode.md#fn-move_to) and stamps a starting
price from the item's `value`:

```text
@set stall three/cmd_stock = '''
$stall stock *:
itm = [o for o in contents(enactor) if name(o).lower() == arg0.strip().lower()]
ok = enactor.id == V('renter') and bool(itm)  # the stall runs with admin authority, so this gate is the only limit on the renter
if ok:
    o = itm[0]
    move_to(o, me)
    set_attr(o, 'stall_price', max(1, get_attr(o, 'value', 1)))
    pemit(enactor, f"{name(o)} goes on the shelf at {get_attr(o, 'stall_price', 1)} credits.")
else:
    pemit(enactor, 'Only the renter stocks this stall, and only from their own pack.')
'''
```

`stall price <item> = <credits>` is the verb that makes the shop
player-run: a mortal reprices goods on an object they do not own, because
the admin-authority script agrees to do it for them with
[`set_attr`](../reference/softcode.md#fn-set_attr). A non-renter and a bad
item or price get different messages:

```text
@set stall three/cmd_price = '''
$stall price * = *:
itm = [o for o in contents(me) if name(o).lower() == arg0.strip().lower()]
ok = enactor.id == V('renter') and bool(itm) and int(arg1) > 0
if ok:
    o = itm[0]
    set_attr(o, 'stall_price', int(arg1))
    remit(here, f"{V('renter_name', 'The stallholder')} chalks a new price: {name(o)} at {int(arg1)} credits.")
elif enactor.id != V('renter'):
    pemit(enactor, 'Only the renter sets prices here.')
else:
    pemit(enactor, 'No such item on the shelf, or a bad price.')
'''
```

`stall` is the public shelf, listing every escrowed item that carries a
`stall_price` with [`pemit`](../reference/softcode.md#fn-pemit):

```text
@set stall three/cmd_shelf = '''
$stall:
pemit(enactor, f"stall three, run by {V('renter_name', 'nobody (rent stall to claim it)')}:")
for o in contents(me):
    if has_attr(o, 'stall_price'):
        pemit(enactor, f"  {name(o)} - {get_attr(o, 'stall_price', 0)} credits")
'''
```

`stall buy <item>` is for any player but the renter. Payment comes first
(the transfer is the wallet check), then delivery out of escrow with
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj), then the
earnings ledger with [`incr`](../reference/softcode.md#fn-incr), then a
receipt to the renter wherever they are:

```text
@set stall three/cmd_buy = '''
$stall buy *:
itm = [o for o in contents(me) if has_attr(o, 'stall_price') and name(o).lower() == arg0.strip().lower()]
price = get_attr(itm[0], 'stall_price', 0) if itm else 0
ok = bool(itm) and enactor.id != V('renter') and transfer_credits(enactor, me, price)  # the renter cannot buy from their own shelf
if ok:
    o = itm[0]
    del_attr(o, 'stall_price')
    teleport_obj(o, enactor)
    incr('earnings', price)
    remit(here, f'{name(enactor)} buys {name(o)} for {price} credits.')
    pemit(get('#' + V('renter')), f'Your stall sells {name(o)} for {price} credits.')  # reach the renter by id, even in another room
else:
    pemit(enactor, 'Not on the shelf, or you cannot cover it.')
'''
```

`stall collect` lets the renter draw down their claim, moving `earnings`
off the stall's balance and back to their wallet:

```text
@set stall three/cmd_collect = '''
$stall collect:
e = V('earnings', 0)
ok = enactor.id == V('renter') and e > 0 and transfer_credits(me, enactor, e)
if ok:
    set_attr(me, 'earnings', 0)
    pemit(enactor, f'You pocket {e} credits in takings.')
else:
    pemit(enactor, 'No takings to collect, or this is not your stall.')
'''
```

Finally the rent heartbeat. When rent falls due it is docked from the
earnings ledger and the credits stay put, becoming the market's; if the
takings cannot cover it, the pitch is repossessed and the goods and any
leftover claim chase the renter home:

```text
@behavior stall three = script_ticker, interval:60
@set stall three/on_tick = '''
r = V('renter')
e = V('earnings', 0)
rent = V('rent', 20)
due = bool(r) and now() >= V('paid_until', 0)
if due and e >= rent:
    set_attr(me, 'earnings', e - rent)  # rent never moves credits, it only shrinks the renter's claim
    incr('paid_until', V('period', 300))
    pemit(get('#' + r), f'The market takes {rent} credits rent from your stall takings.')
elif due and e < rent:
    for o in contents(me):
        if has_attr(o, 'stall_price'):
            teleport_obj(o, get('#' + r))
            del_attr(o, 'stall_price')
    if e > 0:
        transfer_credits(me, get('#' + r), e)
    pemit(get('#' + r), 'Stall three is repossessed for unpaid rent; your goods and takings are returned.')
    del_attr(me, 'renter')
    del_attr(me, 'renter_name')
    set_attr(me, 'earnings', 0)
    remit(here, 'The market warden strips stall three: TO LET.')
'''
```

## Try it

As Bob, with 100 credits:

```text
> rent stall
  Bob rents stall three and shakes out the awning.
  Stall three is yours. Stock it, price it, collect your takings.
> stall stock a stimpack
  a stimpack goes on the shelf at 20 credits.
> stall price a stimpack = 35
  The stallholder chalks a new price: a stimpack at 35 credits.
> stall
  stall three, run by Bob:
    a stimpack - 35 credits
```

Now as Cass:

```text
> stall buy a stimpack
  Cass buys a stimpack for 35 credits.
> stall price a stimpack = 1
  Only the renter sets prices here.
```

Cass loses 35 credits, the stimpack lands in her pack, and Bob (in another
room, even) hears "Your stall sells a stimpack for 35 credits." His
`stall collect` then pockets 35. Cass typing `stall price` or `stall
stock` gets the renter-only refusal: the same object and the same verbs
answer differently because the enactor differs.

Rent day, driven by hand:

```text
> @eval set_attr(get('stall three'), 'paid_until', now() - 1)
> @tr stall three/on_tick
```

With takings on the ledger the rent is docked silently and Bob hears the
market take its cut. Run it again with an empty ledger and the awning comes
down: the goods and any leftover claim teleport back to Bob, and the room
hears the warden strip the pitch. Note that `@tr` fires a named attribute
like `on_tick` directly, but it cannot fire a `$`-verb such as `stall
buy`, which only real command input dispatches.

## Going further

- **A row of stalls.** A `$`-command search takes the first match in the
  room, so a second stall carrying the same `stall buy *` verb never fires.
  Give each pitch its own verb family (`stall2 buy *` and so on) or its own
  alcove room, since one stall per room is the classic market street.
- **Market cut on sales.** Dock `earnings` by 5% of each sale instead of,
  or on top of, flat rent, with the tax arithmetic living in one line of
  `cmd_buy`.
- **Vacation mode.** A `stall close` verb that hides the shelf (an
  `add_tag(me, 'shuttered')` that `stall buy` checks for) while rent still
  ticks, so absence costs the renter rather than crashing the shop.
- **The shopkeeper hybrid.** Park an `npc`-tagged assistant behind the
  counter on the engine's native `shopkeeper` behavior (tutorial
  [063](063_shopkeeper.md)) and let the stall's tick restock it from the
  renter's escrow, giving the native `list` and `buy` interface over
  player-owned goods.
```
