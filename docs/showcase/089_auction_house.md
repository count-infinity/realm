# 089. Auction house

> Checklist item 89 ([now]): *auction state attrs, escrow inventory, on_tick settlement*

**What you'll build:** an auction kiosk with timed listings, double-sided
escrow (items held in the kiosk's inventory, bids held in its credit balance),
anti-sniping deadline extension, automatic settlement on a heartbeat, and an
audit history.

**Concepts:** a state machine in attribute data (`lot_<n>` dicts); storing
*ids*, not object references; escrow via
[`move_to`](../reference/softcode.md#fn-move_to) into the master's own
inventory and [`transfer_credits`](../reference/softcode.md#fn-transfer_credits)
into its balance; a sniping window measured with
[`now()`](../reference/softcode.md#fn-now); heartbeat settlement through a
[`script_ticker`](../reference/softcode.md#lifecycle-hooks) `on_tick` and an
[`eval_attr`](../reference/softcode.md#fn-eval_attr) routine; graceful
degradation when objects vanish.

## How it works

The finished kiosk is one dropped object that holds everything: the open lots
as data, the escrowed items in its own inventory, and the escrowed bids in its
own credit balance. A builder lists an item, bidders raise each other, and a
heartbeat closes each lot when its clock runs out. This section answers three
questions in turn: where the state lives, why money and items are held by the
house, and how a lot closes on its own.

### Where does a listing live?

Each listing is one dict in one attribute on the kiosk, keyed by lot number:

```text
lot_3 = {'seller': <id>, 'seller_name': 'Vala', 'item': <id>,
         'item_name': 'crystal skull', 'min': 10, 'bid': 20,
         'bidder': <id>, 'bidder_name': 'Cass', 'ends': <epoch>}
```

Note what is stored: ids and scalars, never live object references. At
settlement the ids are re-resolved with
[`get`](../reference/softcode.md#fn-get)`('#' + id)`, and if a bidder or item
was destroyed since the bid, that lookup returns None and the branch degrades
quietly instead of failing on a dead reference. This is the same one-master
pattern the [bank](087_bank_accounts.md) uses, with the balances replaced by a
book of lots.

### Why does the house hold the money and the goods?

The design keystone is escrow on both sides, and it exists so that settlement
can never fail for lack of funds or goods.

Listing an item calls [`move_to`](../reference/softcode.md#fn-move_to) to pull
it out of the seller's hands and into the kiosk, so a seller cannot walk off
with an item that is already on the block. The kiosk is admin-owned, and a
script acts with its owner's authority, so the kiosk may relocate a player's
item into itself even though it does not own the item.

Bidding moves the credits into the kiosk's balance the instant the bid lands,
using [`transfer_credits`](../reference/softcode.md#fn-transfer_credits) out of
the bidder's wallet. Because the transfer either succeeds or fails on the spot,
the same call doubles as the affordability check: a bidder who cannot cover the
amount never becomes the high bidder. Getting outbid refunds the earlier bidder
immediately, so at any moment the house holds exactly one live bid. The
consequence is that when the timer runs out the winning credits are already in
the house, and settlement is a pure handover.

### How does a lot close on its own?

A bid that lands inside the last `snipe` seconds pushes `ends` out to
`now() + snipe`, so last-second sniping simply reopens the bidding for another
short round rather than stealing the lot in the final tick.

Closing runs on the arc's standard heartbeat. The
[`script_ticker`](../reference/softcode.md#lifecycle-hooks) behavior fires the
kiosk's `on_tick`, which sweeps every open lot and hands any that are past
their deadline to a `settle` function attribute through
[`eval_attr`](../reference/softcode.md#fn-eval_attr). Where the
[shopkeeper](063_shopkeeper.md) uses the same ticker to refill shelves, here it
closes auctions. Because `eval_attr` runs the routine as its caller and the
caller is the kiosk running `on_tick`, inside `settle` the name `me` is the
kiosk, so the routine reads and writes the kiosk's own data with a bare `me`.
Deadlines are compared with `now() >= ends`, so a due lot settles on the next
tick: an auction does not need to end on the exact second, it needs to end
reliably.

## Build it

Create the kiosk and drop it in the room, then set its two timing knobs in
seconds: how long a fresh listing runs, and how large the anti-snipe window is.

```text
@create the Auction Kiosk
drop the Auction Kiosk
@set the Auction Kiosk/duration = 120
@set the Auction Kiosk/snipe = 30
```

`auction <item> for <min>` escrows the item and opens a lot. It matches the
item by exact name in the seller's inventory, and gates the whole listing on
having a match and a positive minimum. The lot number comes from a `next_lot`
counter that [`incr`](../reference/softcode.md#fn-incr) bumps as each lot opens:

```text
@set the Auction Kiosk/cmd_auction = '''
$auction * for *:
matches = [o for o in contents(enactor) if name(o).lower() == arg0.strip().lower()]
ok = bool(matches) and int(arg1) > 0
if ok:
    item = matches[0]
    n = V('next_lot', 1)   # lot numbers start at 1, so an unset counter reads as 1
    move_to(item, me)
    set_attr(me, 'lot_' + str(n), {'seller': enactor.id, 'seller_name': name(enactor), 'item': item.id, 'item_name': name(item), 'min': int(arg1), 'bid': 0, 'bidder': '', 'bidder_name': '', 'ends': now() + V('duration', 120)})
    incr('next_lot', default=1)   # default=1 so the first bump lands on 2, matching the read
    remit(here, f'{name(enactor)} lists {name(item)} as lot #{n} (min {int(arg1)}).')
    pemit(enactor, 'Listed.')
else:
    pemit(enactor, 'You are not carrying that, or the minimum is bad.')
'''
```

`auctions` prints the open book, walking lot numbers and skipping any that have
already closed (a closed lot reads back as None):

```text
@set the Auction Kiosk/cmd_auctions = '''
$auctions:
pemit(enactor, 'Open lots:')
for i in range(1, V('next_lot', 1)):
    lot = V('lot_' + str(i))
    if lot:
        standing = str(lot['bid']) + ' by ' + lot['bidder_name'] if lot['bidder'] else 'none'
        left = max(0, int(lot['ends'] - now()))
        pemit(enactor, f"  #{i} {lot['item_name']} — min {lot['min']}, bid {standing}, {left}s left")
'''
```

`bid <lot> <amount>` is where the rules live. The floor is the current bid plus
one, or the minimum on a lot that has no bid yet; a seller may not bid on their
own lot; and the credit transfer is itself the affordability check, so a bid
only stands if the money actually moves. If it does, the previous high bidder
is refunded and told, and the lot is rewritten with the new bid, extending the
deadline when the bid arrived inside the snipe window:

```text
@set the Auction Kiosk/cmd_bid = '''
$bid * *:
lot = V('lot_' + arg0.strip())
amt = int(arg1)
low = (lot['bid'] + 1 if lot['bidder'] else lot['min']) if lot else 0
ok = bool(lot) and lot['seller'] != enactor.id and amt >= low and transfer_credits(enactor, me, amt)
if ok:
    if lot['bidder']:   # refund whoever we just outbid, straight from escrow
        transfer_credits(me, get('#' + lot['bidder']), lot['bid'])
        pemit(get('#' + lot['bidder']), f"You are outbid on lot #{arg0.strip()}; {lot['bid']} credits refunded.")
    ends = now() + V('snipe', 30) if lot['ends'] - now() < V('snipe', 30) else lot['ends']
    set_attr(me, 'lot_' + arg0.strip(), dict(lot, bid=amt, bidder=enactor.id, bidder_name=name(enactor), ends=ends))
    remit(here, f'{name(enactor)} bids {amt} on lot #{arg0.strip()}.')
    pemit(enactor, 'Bid placed.')
else:
    pemit(enactor, f'No such lot, your own lot, or bid below {low}.')
'''
```

`settle` is the gavel, written as a function attribute that takes the lot
number. It re-resolves seller, bidder, and item from their stored ids; a
winning lot pays the seller from escrow and delivers the item, while an unsold
lot walks the item home. Either way it appends one history row (capped at the
newest twenty) and deletes the lot:

```text
@set the Auction Kiosk/settle = '''
lot = V('lot_' + arg0)
w = get('#' + lot['bidder']) if lot['bidder'] else None   # None if the bidder was destroyed
s = get('#' + lot['seller'])
it = get('#' + lot['item'])
if w:
    move_to(it, w)
    transfer_credits(me, s, lot['bid'])
    remit(here, f"The gavel falls: {lot['item_name']} goes to {lot['bidder_name']} for {lot['bid']} credits.")
else:
    if it and s:
        move_to(it, s)
    remit(here, f"{lot['item_name']} finds no buyer and returns to {lot['seller_name']}.")
set_attr(me, 'history', (V('history', []) + [f"{lot['item_name']} -> {lot['bidder_name'] or 'unsold'} at {lot['bid']}"])[-20:])
del_attr(me, 'lot_' + arg0)
result = 1
'''
```

`cancel <lot>` lets the seller withdraw a lot, but only their own and only
before the first bid has escrowed money:

```text
@set the Auction Kiosk/cmd_cancel = '''
$cancel *:
lot = V('lot_' + arg0.strip())
ok = bool(lot) and lot['seller'] == enactor.id and not lot['bidder']
if ok:
    move_to(get('#' + lot['item']), enactor)
    del_attr(me, 'lot_' + arg0.strip())
    remit(here, f'{name(enactor)} withdraws lot #{arg0.strip()}.')
    pemit(enactor, 'Listing withdrawn.')
else:
    pemit(enactor, 'Not your lot, already bid on, or no such lot.')
'''
```

Finally the heartbeat. The `script_ticker` behavior runs `on_tick` every four
beats, and the tick is a single sweep that hands each due lot to `settle`. It
stays one line because it is one comprehension:

```text
@behavior the Auction Kiosk = script_ticker, interval:4
@set the Auction Kiosk/on_tick = [eval_attr(me, 'settle', i) for i in range(1, V('next_lot', 1)) for lot in [V('lot_' + str(i))] if lot and now() >= lot['ends']]
```

`on_tick` runs as the kiosk itself on a timer, so it is not a reactive
`ON_<EVENT>` hook and needs no `target` guard: nothing else in the room can
trigger it.

## Try it

```text
@create plasma torch
auction plasma torch for 50     -> "Vala lists plasma torch as lot #1 (min 50)."
auctions                        -> #1 plasma torch — min 50, bid none, 119s left
```

As Bob, `bid 1 60` moves 60 credits out of his wallet at once. As Cass,
`bid 1 75` sends Bob's 60 straight back, and he sees "You are outbid on lot
#1; 60 credits refunded." Bob then tries `bid 1 70` and is refused with "bid
below 76", because the floor is now the standing 75 plus one. Bid again inside
the last 30 seconds and `auctions` shows the clock jump outward. When the
deadline passes, the next tick closes it:

```text
The gavel falls: plasma torch goes to Cass for 75 credits.
```

To watch settlement without waiting, set `@set the Auction Kiosk/duration = 0`
before listing, then run `@tr the Auction Kiosk/on_tick`: the lot is already
due the moment it opens, and `@tr` fires the named `on_tick` attribute directly
with the kiosk as executor. Sellers back out with `cancel <lot>`, which works
only before the first bid.

## Going further

- **House cut.** Settle with `transfer_credits(me, s, lot['bid'] * 95 // 100)`
  and leave the remainder in the kiosk. An auction house is an excellent credit
  sink.
- **Buyout.** Add a `'buyout'` key to the lot; a `bid` at or above it rewrites
  `ends` to `now()` so the next tick settles immediately.
- **One-shot timers instead of a sweep.** Give each lot a companion gavel token
  object with [`expire`](../reference/softcode.md#fn-expire)`(token, duration)`
  and an [`ON_EXPIRE`](../reference/softcode.md#lifecycle-hooks) of
  `eval_attr(get('the Auction Kiosk'), 'settle', '<n>')`, for persistent per-lot
  timers. The sweep version wins here only because sniping keeps moving the
  deadline.
- **Reserve prices.** Add a `'reserve'` above `min`; settlement checks
  `lot['bid'] >= lot['reserve']` and otherwise runs the unsold branch, so bids
  escrow as usual while the seller keeps the floor hidden.
