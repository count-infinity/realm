# 091. Lottery

> Checklist item 91 ([now]): *ticket items, on_tick drawings, pot transfers*

**What you'll build:** a lottery terminal selling numbered physical tickets,
where a scheduled drawing picks a serial and pays the whole pot to whoever
*holds the genuine ticket*. The tickets are tradeable, forgery-proof by
construction, and the pot rolls over when the winning stub ends up in a bin.

**Concepts:** the ticket pattern from the [coat check](022_coat_check.md)
meets money. Tickets are bearer objects whose serials are recorded at mint
time in a ledger of object *ids*, so a forged lookalike can never win. The
build uses the create-at-self plus
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj) delivery idiom, pot
escrow on the terminal with a `pot` attribute, deadline arithmetic plus a
[`script_ticker`](../reference/softcode.md#lifecycle-hooks) for the draw, and
[`rand`](../reference/softcode.md#fn-rand) as the drum. It is the
[slot machine](001_slot_machine.md) grown a scheduled winner and a shared pot.

## How it works

The finished terminal does three things: it sells a ticket and escrows the
price, it keeps a private ledger tying each serial to one exact object, and on
a timer it rolls a serial and pays whoever holds that object. This section
answers why the ledger holds object ids rather than serials, how a stolen
ticket still wins, and why the draw is a heartbeat rather than an instant.

### Why the ledger records object ids, not serials

`lotto buy` pulls the price into the terminal with
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits), so the pot
escrows where the drawing runs and a payout can never bounce. It then
[mints](../reference/softcode.md#fn-create_obj) `lottery ticket <n>` and, on
the load-bearing line, records `stub_<n> = '#<object-id>'` on the terminal with
[`set_attr`](../reference/softcode.md#fn-set_attr). The `serial` stamped on the
ticket is decoration for humans, since the drawing never reads it. When the
drum picks serial `w`, the terminal resolves its own `stub_<w>` row to an exact
object id with [`get`](../reference/softcode.md#fn-get) and asks
[`loc`](../reference/softcode.md#fn-loc) who holds that object. A player can
fabricate a thing *named* "lottery ticket 3" with a forged `serial`, and it
changes nothing, because it was never minted and so no ledger row points at it.
Anti-forgery here is not detection: the fake is simply unreachable by the draw.

### Why a stolen ticket wins

Because the winner is whoever holds the genuine object, tickets are tradeable,
giftable, and stealable, and a stolen ticket *wins*, which is a plot rather
than a bug. If the drawn stub is not in a player's hands (dropped in a room or
binned), there is no winner and the pot rolls over to the next round. Every
round's tickets are retired either way, so old stubs cannot haunt later
drawings.

### How the ticket reaches the buyer

[`create_obj`](../reference/softcode.md#fn-create_obj) places a new thing at
its executor's location by default, so the terminal mints each ticket in its
own inventory and then hands it over with
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj), which moves an
object the terminal controls straight to the buyer. Minting at self and then
delivering keeps the two concerns separate: the ledger row is written against
the object the terminal just made, before it leaves the terminal's hands.

### Why the draw is a heartbeat, not an instant

The first sale of a round stamps `draw_at = now() + round`, and the
[`script_ticker`](../reference/softcode.md#lifecycle-hooks) heartbeat compares
`now() >= draw_at` and runs the `draw` routine on the next pulse. This is the
auction-house rule: a drawing needs to happen *reliably*, not on the exact
second. Nothing in this build reacts to a room-wide event, so there is no
`ON_<EVENT>` hook and nothing that needs an `if target is me:` guard. The money
arrives through the terminal's own `$lotto buy` command, not through the `pay`
builtin, which is why no `ON_PAYMENT` hook appears here.

## Build it

Dig the room, create the terminal, and give it its two knobs: the price per
ticket and the round length in seconds.

```text
@dig The Lucky Star Lounge
@teleport The Lucky Star Lounge
@create the lottery terminal
drop the lottery terminal
@set the lottery terminal/price = 10
@set the lottery terminal/round = 120
```

The `$lotto buy` command pays in, mints, records, delivers, and arms the round
clock on the round's first ticket. It runs as a `'''` block: the money comes in
first, and only if that clears does a ticket get minted and recorded.

```text
@set the lottery terminal/cmd_buy = '''
$lotto buy:
price = V('price', 10)
ok = transfer_credits(enactor, me, price)  # the terminal pulls the fee under its owner's authority
if not ok:
    pemit(enactor, 'The terminal blinks: insufficient credits.')
else:
    incr('pot', price)
    n = incr('sold')
    t = create_obj(f'lottery ticket {n}', tags=['thing', 'lottery_ticket'], location=me)
    set_attr(me, 'stub_' + str(n), '#' + t.id)  # the ledger row: serial n maps to one exact object id
    set_attr(t, 'serial', n)
    teleport_obj(t, enactor)  # minted in the terminal, now handed to the buyer
    set_attr(me, 'draw_at', V('draw_at', 0) or now() + V('round', 120))  # first sale arms the clock; later sales keep it
    remit(here, f"{name(enactor)} buys lottery ticket {n}. The pot stands at {V('pot', 0)} credits.")
'''
```

The bare `lotto` command reads the board. It is a single
[`pemit`](../reference/softcode.md#fn-pemit), so it stays on one line.

```text
@set the lottery terminal/cmd_status = $lotto:pemit(enactor, f"Pot: {V('pot', 0)} credits across {V('sold', 0)} tickets. Draw in {max(0, int(V('draw_at', now()) - now()))}s.")
```

The drawing is a function attribute. It picks a serial with
[`rand`](../reference/softcode.md#fn-rand), resolves it through the ledger to
the genuine object, pays whoever holds it or rolls the pot over, then retires
every genuine ticket and resets the round.

```text
@set the lottery terminal/draw = '''
n = V('sold', 0)
w = rand(1, n) if n else 0  # the drum: a serial in 1..n, each ticket equally likely
t = get(V('stub_' + str(w))) if w else None
holder = loc(t) if t is not None else None
win = holder is not None and has_tag(holder, 'player')  # the winner must be a player actually holding it
pot = V('pot', 0)
if win:
    transfer_credits(me, holder, pot)
    set_attr(me, 'pot', 0)
    remit(here, f'The drum rattles: ticket {w} wins! {name(holder)} collects {pot} credits.')
else:
    remit(here, f'The drum rattles: ticket {w} wins... and no one holds it. The pot rolls over.')
for i in range(1, n + 1):
    x = get(V('stub_' + str(i)))
    if x is not None:
        destroy_obj(x)  # retire every genuine ticket; a forgery has no ledger row, so it is left alone
    del_attr(me, 'stub_' + str(i))
set_attr(me, 'sold', 0)
del_attr(me, 'draw_at')
result = 1
'''
```

Finally the heartbeat that calls the draw when the clock runs out. The
[`script_ticker`](../reference/softcode.md#lifecycle-hooks) fires `on_tick` on a
cadence, and the tick is a single
[`eval_attr`](../reference/softcode.md#fn-eval_attr) into `draw`, so it stays
one line. The guard on the front means the ticker checks the clock and does not
draw early.

```text
@behavior the lottery terminal = script_ticker, interval:30
@set the lottery terminal/on_tick = eval_attr(me, 'draw') if V('sold', 0) and now() >= V('draw_at', 0) else None
```

## Try it

Fund yourself, then buy a ticket or two and read the board:

```text
> lotto buy
Bob buys lottery ticket 1. The pot stands at 10 credits.

> lotto buy
Cass buys lottery ticket 2. The pot stands at 20 credits.

> lotto
Pot: 20 credits across 2 tickets. Draw in 87s.
```

Tickets are real objects, so `give lottery ticket 1 to Cass` moves your chance
along with the paper. When `draw_at` passes, the next tick rolls the drum. The
winning serial varies with the roll; this is one representative outcome:

```text
The drum rattles: ticket 2 wins! Cass collects 20 credits.
```

To watch it now without waiting on the clock, fire the routine directly with
`@tr the lottery terminal/draw`. To try cheating, have a confederate hold a
home-made "lottery ticket 1" with a forged `serial`: the drum picks serial 1,
the ledger resolves to the minted object in your rival's pack, and the fake is
never even looked at. Drop the only sold ticket on the floor before the draw
and the pot rolls over into the next round.

## Going further

- **House cut.** Pay out `pot * 9 // 10` and burn the rest with
  `adjust_credits(me, -pot // 10)`, which makes the lottery a tidy credit sink.
- **Multi-buy.** A `$lotto buy *` that loops `int(arg0)` mints in one
  transaction, and the ledger rows and pot arithmetic do not change.
- **Winner wasn't watching.** The payout already reaches an absent holder,
  since [`transfer_credits`](../reference/softcode.md#fn-transfer_credits) does
  not care where they stand. Add a
  [`pemit`](../reference/softcode.md#fn-pemit)`(holder, ...)` so a winner across
  the map hears the good news, the bank-wire pattern from the
  [bank accounts](087_bank_accounts.md) build.
- **Syndicate tickets.** Let a *container* hold tickets and split the prize
  across everyone tagged on it: [`loc`](../reference/softcode.md#fn-loc)`(t)`
  gives the box, and the box's `members` attribute gives the shares.
