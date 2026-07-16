# 089. Auction house

> Checklist item 89 — [now] — *auction state attrs, escrow inventory, on_tick settlement*

**What you'll build:** an auction kiosk with timed listings, double-sided
escrow (items in the kiosk's inventory, bids in its credit balance),
anti-sniping deadline extension, automatic settlement on a heartbeat, and
an audit history.

**Concepts:** a state machine in attribute data (`lot_<n>` dicts); storing
*ids*, not object references; escrow via `move_to` into the master's own
inventory and `transfer_credits` into its balance; sniping windows with
`now()`; `on_tick` settlement through an `eval_attr` routine; graceful
degradation when objects vanish.

## How it works

Each listing is one dict in one attribute on **the Auction Kiosk**:

```text
lot_3 = {'seller': <id>, 'seller_name': 'Vala', 'item': <id>,
         'item_name': 'crystal skull', 'min': 10, 'bid': 20,
         'bidder': <id>, 'bidder_name': 'Cass', 'ends': <epoch>}
```

Note what's *stored*: ids and scalars. At settlement time the ids are
re-resolved with `get('#' + id)`; if a bidder or item has been destroyed
since, the lookup returns None and the branch degrades gracefully instead
of crashing on a dead reference.

The design keystone is **escrow on both sides**:

- Listing an item `move_to`s it *into the kiosk* — you can't sell the
  sword you're still swinging. The kiosk is admin-owned, so its script
  has the authority to take the enactor's item (they asked, by typing the
  command).
- Bidding moves the credits *immediately* into the kiosk's balance.
  Getting outbid refunds you on the spot. Consequence: settlement can
  never bounce — the winning bid is already in the house when the timer
  runs out.

**Sniping protection:** a bid landing inside the last `snipe` seconds
pushes `ends` out to `now() + snipe`. Last-second sniping just converts
the endgame into open bidding rounds.

**Timed settlement** is the arc's standard heartbeat: `script_ticker`
fires `on_tick`, which sweeps every open lot past its deadline and hands
each to a `settle` function attribute — deliver item to winner and
escrowed credits to seller (or walk the item home unsold), announce the
gavel, archive a history row, delete the lot. Deadlines are compared with
`now() >= ends`, so a due lot settles on the *next* tick — auctions don't
need to end on the second, they need to end reliably.

## Build it

The kiosk and its timing knobs (seconds):

```text
@create the Auction Kiosk
drop the Auction Kiosk
@set the Auction Kiosk/duration = 120
@set the Auction Kiosk/snipe = 30
```

`auction <item> for <min>` — escrow the item, open the lot, bump the
counter, announce. The item must be in your inventory and is matched by
its exact name. The `for g, lst in [[ok, item]] if g ...` opener is the
arc's comprehension-binding trick; `for n in [get_attr(me, 'next_lot', 1)]`
binds the lot number once for the three places it's used:

```text
@set the Auction Kiosk/cmd_auction = $auction * for *:item = [o for o in contents(enactor) if name(o).lower() == arg0.strip().lower()]; ok = bool(item) and int(arg1) > 0; [(move_to(o, me), set_attr(me, 'lot_' + str(n), {'seller': enactor.id, 'seller_name': name(enactor), 'item': o.id, 'item_name': name(o), 'min': int(arg1), 'bid': 0, 'bidder': '', 'bidder_name': '', 'ends': now() + get_attr(me, 'duration', 120)}), set_attr(me, 'next_lot', n + 1), remit(here, name(enactor) + ' lists ' + name(o) + ' as lot #' + str(n) + ' (min ' + str(int(arg1)) + ').')) for g, lst in [[ok, item]] if g for o in [lst[0]] for n in [get_attr(me, 'next_lot', 1)]]; pemit(enactor, 'Listed.' if ok else 'You are not carrying that, or the minimum is bad.')
```

`auctions` — the open book, walked by lot number (closed lots read as
None and are skipped):

```text
@set the Auction Kiosk/cmd_auctions = $auctions:pemit(enactor, 'Open lots:'); [pemit(enactor, '  #' + str(i) + ' ' + lot['item_name'] + ' — min ' + str(lot['min']) + ', bid ' + (str(lot['bid']) + ' by ' + lot['bidder_name'] if lot['bidder'] else 'none') + ', ' + str(max(0, int(lot['ends'] - now()))) + 's left') for i in range(1, get_attr(me, 'next_lot', 1)) for lot in [get_attr(me, 'lot_' + str(i))] if lot]
```

`bid <lot> <amount>` — where most of the rules live. Floor = current bid
+ 1 (or the minimum); sellers can't bid on their own lots; the transfer
*is* the validity check for affordability; the outbid party is refunded
and told; `dict(l, bid=a, ...)` rewrites the lot in one read-modify-write,
extending the deadline if the bid landed inside the sniping window:

```text
@set the Auction Kiosk/cmd_bid = $bid * *:lot = get_attr(me, 'lot_' + arg0.strip()); amt = int(arg1); low = (lot['bid'] + 1 if lot['bidder'] else lot['min']) if lot else 0; ok = bool(lot) and lot['seller'] != enactor.id and amt >= low and transfer_credits(enactor, me, amt); [(transfer_credits(me, get('#' + l['bidder']), l['bid']) if l['bidder'] else None, pemit(get('#' + l['bidder']), 'You are outbid on lot #' + arg0.strip() + '; ' + str(l['bid']) + ' credits refunded.') if l['bidder'] else None, set_attr(me, 'lot_' + arg0.strip(), dict(l, bid=a, bidder=enactor.id, bidder_name=name(enactor), ends=(now() + get_attr(me, 'snipe', 30) if l['ends'] - now() < get_attr(me, 'snipe', 30) else l['ends']))), remit(here, name(enactor) + ' bids ' + str(a) + ' on lot #' + arg0.strip() + '.')) for g, l, a in [[ok, lot, amt]] if g]; pemit(enactor, 'Bid placed.' if ok else 'No such lot, your own lot, or bid below ' + str(low) + '.')
```

`settle` — the gavel, as a function attribute taking the lot number.
Re-resolve everything from ids; winner branch pays the seller from escrow
and delivers; no-winner branch walks the item home; either way archive to
`history` (capped at 20) and delete the lot:

```text
@set the Auction Kiosk/settle = lot = get_attr(me, 'lot_' + arg0); w = get('#' + lot['bidder']) if lot['bidder'] else None; s = get('#' + lot['seller']); it = get('#' + lot['item']); r = (move_to(it, w), transfer_credits(me, s, lot['bid']), remit(here, 'The gavel falls: ' + lot['item_name'] + ' goes to ' + lot['bidder_name'] + ' for ' + str(lot['bid']) + ' credits.')) if w else (move_to(it, s) if it and s else None, remit(here, lot['item_name'] + ' finds no buyer and returns to ' + lot['seller_name'] + '.')); set_attr(me, 'history', (get_attr(me, 'history', []) + [lot['item_name'] + ' -> ' + (lot['bidder_name'] or 'unsold') + ' at ' + str(lot['bid'])])[-20:]); del_attr(me, 'lot_' + arg0); result = 1
```

`cancel <lot>` — seller only, and only before the first bid:

```text
@set the Auction Kiosk/cmd_cancel = $cancel *:lot = get_attr(me, 'lot_' + arg0.strip()); ok = bool(lot) and lot['seller'] == enactor.id and not lot['bidder']; [(move_to(get('#' + l['item']), enactor), del_attr(me, 'lot_' + arg0.strip()), remit(here, name(enactor) + ' withdraws lot #' + arg0.strip() + '.')) for g, l in [[ok, lot]] if g]; pemit(enactor, 'Listing withdrawn.' if ok else 'Not your lot, already bid on, or no such lot.')
```

The heartbeat — sweep due lots every 4 ticks:

```text
@behavior the Auction Kiosk = script_ticker, interval:4
@set the Auction Kiosk/on_tick = [eval_attr(me, 'settle', i) for i in range(1, get_attr(me, 'next_lot', 1)) for lot in [get_attr(me, 'lot_' + str(i))] if lot and now() >= lot['ends']]
```

## Try it

```text
@create plasma torch
auction plasma torch for 50     -> "Vala lists plasma torch as lot #1 (min 50)."
auctions                        -> #1 plasma torch — min 50, bid none, 119s left
```

As Bob: `bid 1 60` — 60 credits leave his wallet instantly. As Cass:
`bid 1 75` — Bob's 60 come straight back ("You are outbid on lot #1...").
Bob tries `bid 1 70`: refused, "bid below 76". Bid again inside the last
30 seconds and watch `auctions` show the clock jump. When the deadline
passes, the next tick calls it:

```text
The gavel falls: plasma torch goes to Cass for 75 credits.
```

To watch settlement without waiting: `@set the Auction Kiosk/duration = 0`
before listing, then `@tr the Auction Kiosk/on_tick` — the lot is due the
moment it opens. Sellers back out with `cancel <lot>` (only before bids).

## Going further

- **House cut.** Settle with `transfer_credits(me, s, lot['bid'] * 95 //
  100)` and leave the remainder in the kiosk — auction houses are
  excellent credit sinks.
- **Buyout.** A `'buyout'` key in the lot; `bid` at or above it rewrites
  `ends` to `now()` and lets the next tick settle immediately.
- **One-shot timers instead of a sweep.** Give each lot a companion
  "gavel token" object with `expire(token, duration)` and an `ON_EXPIRE`
  of `eval_attr(get('the Auction Kiosk'), 'settle', '<n>')` — persistent,
  per-lot timers; the sweep version wins here only because sniping keeps
  moving the deadline.
- **Reserve prices.** A `'reserve'` above `min`: settlement checks
  `lot['bid'] >= lot['reserve']` and otherwise runs the unsold branch —
  bids escrow as usual, the seller just keeps the floor hidden.
