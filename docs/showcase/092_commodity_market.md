# 092. Commodity market

> Checklist item 92 ([now]): *on_tick price drift, rand events, $market tables*

**What you'll build:** a commodity exchange board whose prices drift with
supply and random news events, and move when players trade against it, because
trades and the simulation push the same variable.

**Concepts:** a one-variable price simulation (supply) in a dict attribute;
mean-reversion with `rand()` noise on a ticker; random news shocks with `remit`
headlines; a `$market` table rendered with softcode string functions; trades
minting physical cargo-lot objects; the bid/ask spread as a credit sink.

## How it works

The finished board holds one `goods` dictionary, one entry per commodity, and
everything else reads or writes that single structure. A ticker nudges the
prices on a cadence, three `$`-commands let players read the board and trade
against it, and both the ticker and the trades move the *same* `supply` number,
which is what ties the simulation to the players. This section answers three
questions: how a price is stored and drifted, why a trade moves the price, and
how the cargo a buyer receives is actually minted.

### What a price is, and how it drifts

Each commodity is one dict inside `goods`:

```text
"water_ice": {"name": "Water Ice", "base_price": 12,
              "base_supply": 200, "price": 12, "supply": 200}
```

The simulation is deliberately one idea: price chases supply. On each drift
pass, per commodity:

1. Supply relaxes about 5% back toward `base_supply` (background production and
   consumption, so a shock fades instead of compounding), with an `or ±1` so
   integer rounding cannot stall one unit short.
2. Price drifts 25% of the way toward the fair value
   `base_price * base_supply / supply`, times a small `rand(97, 103) / 100`
   noise, then clamped to `[0.2x, 5x]` of base.

Separately, on a 1-in-10 roll each cadence, a news event first multiplies one
commodity's supply by 0.5 or 1.5 and shouts a headline into the room.

### Why a trade moves the price

Because supply is the only lever, player trades plug straight into the model:
buying subtracts supply, selling adds it. Corner Water Ice and its price
genuinely rises on the next drift, for everyone, since the board is shared
state.

The exchange buys back at 90% of list (`floor(price * 0.9)`), so a round trip
costs you the spread. That spread is the market maker's built-in credit sink,
and profit requires actually riding a price swing.

The trade verbs are `market buy` and `market sell` rather than bare `buy` and
`sell` because builtins dispatch before `$`-triggers, so a shopkeeper's `buy`
would swallow the command. Multi-word `$`-patterns make the collision moot.

### How the cargo is minted, and the mint-authority trap

Trades are physical: buying mints a sealed cargo lot object carrying
`commodity` and `units` attributes, so it is haulable, droppable, stealable,
and auctionable (see the [auction house](089_auction_house.md)). Selling a lot
melts its units back into supply.

Minting has one authority rule worth stating plainly. The board runs
[`create_obj`](../reference/softcode.md#fn-create_obj), and
`create_obj(..., location=<player>)` is refused, returning `None`, unless the
board controls that player. An admin-owned board slips past this by delegation,
but a board owned by an ordinary builder does not, so the buyer would pay and
receive nothing. The portable pattern is to mint the lot into the room (the
board's own location, which the board always controls) and then
[`move_to`](../reference/softcode.md#fn-move_to) it to the buyer, because
`move_to` needs authority over the *lot*, which the board owns, not over the
buyer.

## Build it

The board needs a float so it can pay when players sell, plus its goods table
as JSON data. Create it, drop it into the room, seed its reserve with
[`adjust_credits`](../reference/softcode.md#fn-adjust_credits), and stamp the
two commodities:

```text
@create the Commodity Board
drop the Commodity Board
@eval adjust_credits(get('the Commodity Board'), 10000)
@set the Commodity Board/goods = {"water_ice": {"name": "Water Ice", "base_price": 12, "base_supply": 200, "price": 12, "supply": 200}, "helium3": {"name": "Helium-3", "base_price": 60, "base_supply": 100, "price": 60, "supply": 100}}
```

The board itself is the `$market` command. It prints a header, then one
fixed-width row per commodity, sorted, with buy at `ceil(price)` and sell at
`floor(price * 0.9)` so the spread shows in plain sight. Each column is padded
with [`left`](../reference/softcode.md#fn-left) over a
[`repeat`](../reference/softcode.md#fn-repeat) of spaces, and each row reaches
the reader with [`pemit`](../reference/softcode.md#fn-pemit):

```text
@set the Commodity Board/cmd_market = '''
$market:
g = V('goods', {})
pemit(enactor, 'Commodity        buy  sell  supply')
for cid in sorted(g):
    c = g[cid]
    pemit(enactor, f"{left(c['name'] + repeat(' ', 16), 16)} {ceil(c['price'])}  {floor(c['price'] * 0.9)}  {c['supply']}")
'''
```

Buying charges the credits, dents the supply, mints the cargo lot into the
room, and then hands it to the buyer. Each failure has its own message, and
every side effect sits inside the final `else`, so a buyer who cannot afford the
cost is neither charged nor handed a lot.
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits) doubles as
the affordability test, returning False when the wallet is short:

```text
@set the Commodity Board/cmd_buy = '''
$market buy * *:
units = int(arg0)
cid = arg1.strip().lower()
g = V('goods', {})
if cid not in g:
    pemit(enactor, 'No such commodity on the board.')
elif not 0 < units <= g[cid]['supply']:
    pemit(enactor, 'Not that many units are on the market.')
else:
    cost = ceil(g[cid]['price']) * units
    if not transfer_credits(enactor, me, cost):
        pemit(enactor, 'Not enough credits.')
    else:
        g[cid]['supply'] = g[cid]['supply'] - units
        set_attr(me, 'goods', g)
        lot = create_obj(f"a sealed cargo lot ({g[cid]['name']})", tags=['thing', 'cargo'])  # mint into the room, never location=enactor
        set_attr(lot, 'commodity', cid)
        set_attr(lot, 'units', units)
        move_to(lot, enactor)  # then hand it over: the board controls the lot, not the buyer
        pemit(enactor, f"You buy {units} units of {g[cid]['name']} for {cost} credits.")
'''
```

Selling finds a carried cargo lot of that commodity, pays the spread price out
of the board's float, melts the units back into supply, and destroys the lot
with [`destroy_obj`](../reference/softcode.md#fn-destroy_obj). The lot is found
by scanning the seller's [`contents`](../reference/softcode.md#fn-contents) for
the `cargo` tag (with [`has_tag`](../reference/softcode.md#fn-has_tag)) and a
matching `commodity` attribute read via
[`get_attr`](../reference/softcode.md#fn-get_attr):

```text
@set the Commodity Board/cmd_sell = '''
$market sell *:
cid = arg0.strip().lower()
g = V('goods', {})
lots = [o for o in contents(enactor) if has_tag(o, 'cargo') and get_attr(o, 'commodity') == cid]
if not lots or cid not in g:
    pemit(enactor, 'You carry no such cargo lot.')
else:
    units = get_attr(lots[0], 'units', 0)
    pay = floor(g[cid]['price'] * 0.9) * units
    if not transfer_credits(me, enactor, pay):
        pemit(enactor, 'The exchange cannot cover that just now.')
    else:
        g[cid]['supply'] = g[cid]['supply'] + units
        set_attr(me, 'goods', g)
        destroy_obj(lots[0])
        pemit(enactor, f"The exchange pays {pay} credits for {units} units of {g[cid]['name']}.")
'''
```

The simulation is a function attribute, `drift`, that the ticker calls. It
walks each commodity, relaxes supply toward base first, then takes the
drift-noise-clamp price step:

```text
@set the Commodity Board/drift = '''
g = V('goods', {})
for cid, c in g.items():
    if c['supply'] != c['base_supply']:
        c['supply'] = c['supply'] + (int((c['base_supply'] - c['supply']) * 0.05) or (1 if c['base_supply'] > c['supply'] else -1))
    fair = c['base_price'] * c['base_supply'] / max(c['supply'], 1)
    stepped = c['price'] + (fair - c['price']) * 0.25
    c['price'] = round(min(max(stepped * rand(97, 103) / 100.0, c['base_price'] * 0.2), c['base_price'] * 5), 2)
set_attr(me, 'goods', g)
result = 1
'''
```

The news shock picks one commodity, halves or half-agains its supply, and
headlines the room with [`remit`](../reference/softcode.md#fn-remit):

```text
@set the Commodity Board/news = '''
g = V('goods', {})
cid = sorted(g)[rand(0, len(g) - 1)]
raid = rand(0, 1) == 1
g[cid]['supply'] = max(1, int(g[cid]['supply'] * (0.5 if raid else 1.5)))
set_attr(me, 'goods', g)
if raid:
    remit(here, f"[Market] Pirate raids choke off {g[cid]['name']} shipments!")
else:
    remit(here, f"[Market] A glut freighter floods the docks with {g[cid]['name']}!")
result = 1
'''
```

Finally the pulse. A `script_ticker` behavior runs the board's `on_tick` every
8 beats, and `on_tick` maybe fires the news, then always drifts through
[`eval_attr`](../reference/softcode.md#fn-eval_attr). The ticker runs only on
the board it is attached to, so `on_tick` needs no `target` guard, unlike a
reactive `ON_<EVENT>` hook, which fires on every object in the room:

```text
@behavior the Commodity Board = script_ticker, interval:8
@set the Commodity Board/on_tick = '''
if rand(1, 10) == 1:
    eval_attr(me, 'news')
eval_attr(me, 'drift')
'''
```

## Try it

Give yourself a stake, read the board, and trade against it. The prices below
are the seeded start; the `->` notes describe what each command does:

```text
@eval adjust_credits(me, 1000)
market
    Commodity        buy  sell  supply
    Helium-3         60  54  100
    Water Ice        12  10  200
market buy 50 water_ice         -> 600 credits; supply drops to 150
@tr the Commodity Board/drift   -> run one price step (or just wait a tick)
market                          -> Water Ice already climbing (about 13)
market sell water_ice           -> the spread takes its cut
@tr the Commodity Board/news    -> "[Market] Pirate raids choke off ..."
market                          -> try to buy the spike
```

Leave the room open for a few minutes and the board plays by itself: headlines
land, prices spike, and prices decay back toward base as supply relaxes.

## Going further

- **Trade routes.** A second board in another zone with different `base_supply`
  per commodity lets a player buy cheap dockside, haul the cargo lot (it is a
  real object with real weight if you gave it one in the [currency
  tutorial](086_currency.md) style), and sell high in the outer ring.
- **Price history sparkline.** Have `drift` append each price to a `hist_<cid>`
  list capped at `[-20:]`, then render `▁▂▄▆█` buckets on the board.
- **Market-crash hooks.** In `drift`, when a price hits its clamp floor,
  `act(me, ...)` a custom `event:market_crash`, so any `ON_MARKET_CRASH`
  softcode in the room can react (quest boards, panicked NPCs).
- **Futures through the bank.** Combine with the [bank
  accounts](087_bank_accounts.md) build: lock today's price in a ledger
  attribute, then settle the difference against the account N ticks later.
