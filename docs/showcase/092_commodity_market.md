# 092. Commodity market

> Checklist item 92 — [now] — *on_tick price drift, rand events, $market tables*

**What you'll build:** a commodity exchange board whose prices drift with
supply and random news events — and move when players trade against it,
because trades and simulation push the same variable.

**Concepts:** a one-variable price simulation (supply) in a dict
attribute; mean-reversion with `rand()` noise on `on_tick`; random news
shocks with `remit` headlines; a `$market` table rendered with softcode
string functions; trades minting physical cargo-lot objects; the bid/ask
spread as a credit sink.

## How it works

The whole exchange is one `goods` dict on **the Commodity Board**, one
entry per commodity:

```text
"water_ice": {"name": "Water Ice", "base_price": 12,
              "base_supply": 200, "price": 12, "supply": 200}
```

The simulation is deliberately one idea: **price chases supply.** Each
tick, per commodity:

1. *Supply relaxes* ~5% back toward `base_supply` (background production
   and consumption — shocks fade instead of compounding), with an
   `or ±1` so integer rounding can't stall one unit short.
2. *Price drifts* 25% of the way toward the fair value
   `base_price * base_supply / supply`, times ±3% noise
   (`rand(97, 103) / 100`), clamped to `[0.2x, 5x]` of base.
3. With a 1-in-10 `rand` roll, a *news event* first multiplies one
   commodity's supply by 0.5 or 1.5 and shouts a headline into the room.

Because supply is the only lever, player trades plug straight into the
model: **buying subtracts supply, selling adds it.** Corner Water Ice and
the price genuinely rises next tick — for everyone.

Trades are physical: buying mints a sealed **cargo lot** object carrying
`commodity` and `units` attributes — haulable, droppable, stealable,
auctionable (tutorial 089). Selling a lot melts it back into supply. The
exchange buys at 90% of list (`floor(price * 0.9)`), so a round trip
costs you: the spread is the market maker's built-in credit sink, and
profit requires actually riding a price swing.

The trade verbs are `market buy` / `market sell` rather than bare
`buy`/`sell` because builtins dispatch before `$`-triggers — the
shopkeeper's `buy` would swallow the command. Multi-word `$`-patterns
make the collision moot.

## Build it

The board, its float (it must be able to pay when players sell), and the
goods table as JSON data:

```text
@create the Commodity Board
drop the Commodity Board
@eval adjust_credits(get('the Commodity Board'), 10000)
@set the Commodity Board/goods = {"water_ice": {"name": "Water Ice", "base_price": 12, "base_supply": 200, "price": 12, "supply": 200}, "helium3": {"name": "Helium-3", "base_price": 60, "base_supply": 100, "price": 60, "supply": 100}}
```

`market` — the board itself. Fixed-width columns from `left()` +
`repeat()` padding; buy at `ceil(price)`, sell at `floor(price * 0.9)` —
the spread in plain sight:

```text
@set the Commodity Board/cmd_market = $market:pemit(enactor, 'Commodity        buy  sell  supply'); [pemit(enactor, left(g['name'] + repeat(' ', 16), 16) + ' ' + str(ceil(g['price'])) + '  ' + str(floor(g['price'] * 0.9)) + '  ' + str(g['supply'])) for cid in sorted(get_attr(me, 'goods', {})) for g in [get_attr(me, 'goods', {})[cid]]]
```

`market buy <units> <commodity>` — charge, dent the supply, mint the
cargo lot into the buyer's pack. The chain of guarded statements
(`... if ok else None`) keeps every side effect behind one validity check;
`transfer_credits` doubles as the affordability test:

```text
@set the Commodity Board/cmd_buy = $market buy * *:g = get_attr(me, 'goods', {}); units = int(arg0); cid = arg1.strip().lower(); cost = ceil(g[cid]['price']) * units if cid in g else 0; ok = cid in g and 0 < units <= g[cid]['supply'] and transfer_credits(enactor, me, cost); upd = g[cid].update({'supply': g[cid]['supply'] - units}) if ok else None; save = set_attr(me, 'goods', g) if ok else None; lot = create_obj('a sealed cargo lot (' + g[cid]['name'] + ')', tags=['thing', 'cargo'], location=enactor) if ok else None; mark = (set_attr(lot, 'commodity', cid), set_attr(lot, 'units', units)) if ok else None; pemit(enactor, ('You buy ' + str(units) + ' units of ' + g[cid]['name'] + ' for ' + str(cost) + ' credits.') if ok else 'No such commodity, not enough supply, or not enough credits.')
```

`market sell <commodity>` — find a carried cargo lot of that commodity,
pay the spread price out of the board's float, melt the units back into
supply, destroy the lot:

```text
@set the Commodity Board/cmd_sell = $market sell *:g = get_attr(me, 'goods', {}); cid = arg0.strip().lower(); lots = [o for o in contents(enactor) if has_tag(o, 'cargo') and get_attr(o, 'commodity') == arg0.strip().lower()]; ok = bool(lots) and cid in g; units = get_attr(lots[0], 'units', 0) if ok else 0; pay = floor(g[cid]['price'] * 0.9) * units if ok else 0; paid = ok and transfer_credits(me, enactor, pay); upd = g[cid].update({'supply': g[cid]['supply'] + units}) if paid else None; save = set_attr(me, 'goods', g) if paid else None; junk = destroy_obj(lots[0]) if paid else None; pemit(enactor, ('The exchange pays ' + str(pay) + ' credits for ' + str(units) + ' units of ' + g[cid]['name'] + '.') if paid else 'You carry no such cargo lot, or the exchange cannot cover it.')
```

The simulation, as a function attribute. `.items()` hands the
comprehension each commodity dict to mutate in place — relaxation first,
then the drift-noise-clamp price step:

```text
@set the Commodity Board/drift = [(g.update({'supply': g['supply'] + (int((g['base_supply'] - g['supply']) * 0.05) or (1 if g['base_supply'] > g['supply'] else -1))}) if g['supply'] != g['base_supply'] else None, g.update({'price': round(min(max((g['price'] + (g['base_price'] * g['base_supply'] / max(g['supply'], 1) - g['price']) * 0.25) * rand(97, 103) / 100.0, g['base_price'] * 0.2), g['base_price'] * 5), 2)})) for cid, g in get_attr(me, 'goods', {}).items()]; set_attr(me, 'goods', get_attr(me, 'goods', {})); result = 1
```

The news shock — pick a commodity, halve or half-again its supply,
headline the room:

```text
@set the Commodity Board/news = g = get_attr(me, 'goods', {}); cid = sorted(g)[rand(0, len(g) - 1)]; raid = rand(0, 1) == 1; g[cid]['supply'] = max(1, int(g[cid]['supply'] * (0.5 if raid else 1.5))); set_attr(me, 'goods', g); remit(here, '[Market] ' + ('Pirate raids choke off ' + g[cid]['name'] + ' shipments!' if raid else 'A glut freighter floods the docks with ' + g[cid]['name'] + '!')); result = 1
```

The pulse — every 8 ticks: maybe news, always drift:

```text
@behavior the Commodity Board = script_ticker, interval:8
@set the Commodity Board/on_tick = eval_attr(me, 'news') if rand(1, 10) == 1 else None; eval_attr(me, 'drift')
```

## Try it

```text
@eval adjust_credits(me, 1000)
market
    Commodity        buy  sell  supply
    Helium-3         60  54  100
    Water Ice        12  10  200
market buy 50 water_ice         -> 600 credits; supply drops to 150
@tr the Commodity Board/drift   -> (or just wait a tick)
market                          -> Water Ice already climbing (~13)
market sell water_ice           -> the spread takes its cut
@tr the Commodity Board/news    -> "[Market] Pirate raids choke off ..."
market                          -> try to buy the spike
```

Leave the room open for a few minutes and the board plays by itself:
headlines land, prices spike and decay back toward base as supply
relaxes.

## Going further

- **Trade routes.** A second board in another zone with different
  `base_supply` per commodity — buy cheap dockside, haul the cargo lot
  (it's a real object with real weight, if you gave it one in tutorial
  086's style), sell high in the outer ring.
- **Price history sparkline.** Have `drift` append each price to a
  `hist_<cid>` list capped `[-20:]`, and render `▁▂▄▆█` buckets on the
  board.
- **Market-crash hooks.** In `drift`, when a price hits its clamp floor,
  `act(me, ...)` a custom `event:market_crash` — any `ON_MARKET_CRASH`
  softcode in the room can react (quest boards, panicked NPCs).
- **Futures through the bank.** Combine with tutorial 087: lock today's
  price in a ledger attribute, settle the difference against the account
  N ticks later.
