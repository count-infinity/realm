# 091. Lottery

> Checklist item 91 — [now] — *ticket items, on_tick drawings, pot transfers*

**What you'll build:** a lottery terminal selling numbered physical
tickets; a scheduled drawing picks a serial and pays the whole pot to
whoever *holds the genuine ticket* — tradeable stubs, forgery-proof by
construction, rollover when the winning stub went in a bin.

**Concepts:** the ticket pattern (022) meets money: bearer tokens whose
serials are **recorded at mint time** in a ledger of object *ids*, so a
forged lookalike can never win; the create-at-self + `teleport_obj`
delivery idiom; pot escrow on the terminal with a `pot` attribute as the
claimable ledger; deadline arithmetic + `script_ticker` for the draw;
`rand()` as the drum.

## How it works

**Tickets are objects; truth is the ledger.** `lotto buy` moves the
price into the terminal (the pot escrows where the drawing runs — payout
can never bounce), mints `lottery ticket <n>`, and — the load-bearing
line — records `stub_<n> = '#<object-id>'` on the terminal. The stamped
`serial` on the ticket is *decoration for humans*; the drawing never
reads it. When the drum picks serial `w`, the terminal resolves its own
`stub_<w>` row to an exact object id and asks `loc()` who holds that
object. A player can fabricate a thing *named* "lottery ticket 3" with a
forged `serial` attribute, and it changes nothing: it was never minted,
so no ledger row points at it. Anti-forgery here isn't detection — the
fake is simply unreachable by the draw.

**Bearer semantics fall out for free.** Because the winner is "whoever
holds the genuine object," tickets are tradeable, giftable, stealable —
a stolen ticket *wins*, which is a plot, not a bug. If the drawn stub
isn't in a player's hands (dropped in a room, binned), there is no
winner and the pot **rolls over** to the next round; every round's
tickets are retired either way, so old stubs can't haunt later drawings.

**Delivery uses the two-step idiom.** `create_obj` refuses to conjure
objects directly into another player's pockets, so the terminal mints
each ticket *in its own hopper* and `teleport_obj`s it to the buyer —
handing over what you hold is always yours to do.

**The draw is scheduled, not instant.** The first sale of a round stamps
`draw_at = now() + round`; the `script_ticker` heartbeat compares
`now() >= draw_at` and runs the `draw` routine on the next pulse — the
auction-house rule again: drawings need to happen *reliably*, not on the
exact second.

## Build it

The terminal and its knobs (price per ticket, round length in seconds):

```text
@dig The Lucky Star Lounge
@teleport The Lucky Star Lounge
@create the lottery terminal
drop the lottery terminal
@set the lottery terminal/price = 10
@set the lottery terminal/round = 120
```

`lotto buy` — pay in, mint, record, deliver, and arm the round clock if
this is the round's first ticket:

```text
@set the lottery terminal/cmd_buy = $lotto buy:price = V('price', 10); ok = transfer_credits(enactor, me, price); [(incr('pot', p), set_attr(me, 'stub_' + str(n), '#' + t.id), set_attr(t, 'serial', n), teleport_obj(t, enactor), set_attr(me, 'draw_at', V('draw_at', 0) or now() + V('round', 120)), remit(here, f"{name(enactor)} buys lottery ticket {n}. The pot stands at {V('pot', 0)} credits.")) for g, p in [[ok, price]] if g for n in [incr('sold')] for t in [create_obj(f'lottery ticket {n}', tags=['thing', 'lottery_ticket'], location=me)]]; pemit(enactor, 'The terminal blinks: insufficient credits.') if not ok else None
```

`lotto` — the board:

```text
@set the lottery terminal/cmd_status = $lotto:pemit(enactor, f"Pot: {V('pot', 0)} credits across {V('sold', 0)} tickets. Draw in {max(0, int(V('draw_at', now()) - now()))}s.")
```

The drawing, as a function attribute. Pick a serial, resolve it through
the ledger to the genuine object, pay whoever holds it (or roll the pot
over), then retire every genuine ticket and reset the round:

```text
@set the lottery terminal/draw = n = V('sold', 0); w = rand(1, n) if n else 0; t = get(V('stub_' + str(w))) if w else None; holder = loc(t) if t is not None else None; win = holder is not None and has_tag(holder, 'player'); pot = V('pot', 0); (transfer_credits(me, holder, pot), set_attr(me, 'pot', 0), remit(here, f'The drum rattles: ticket {w} wins! {name(holder)} collects {pot} credits.')) if win else remit(here, f'The drum rattles: ticket {w} wins... and no one holds it. The pot rolls over.'); [destroy_obj(x) for i in range(1, n + 1) for x in [get(V('stub_' + str(i)))] if x is not None]; [del_attr(me, 'stub_' + str(i)) for i in range(1, n + 1)]; set_attr(me, 'sold', 0); del_attr(me, 'draw_at'); result = 1
```

And the heartbeat that calls it when the clock runs out:

```text
@behavior the lottery terminal = script_ticker, interval:30
@set the lottery terminal/on_tick = eval_attr(me, 'draw') if V('sold', 0) and now() >= V('draw_at', 0) else None
```

## Try it

```text
lotto buy       -> "Bob buys lottery ticket 1. The pot stands at 10 credits."
lotto buy       -> (as Cass) ticket 2; the pot stands at 20
lotto           -> Pot: 20 credits across 2 tickets. Draw in 87s.
```

Tickets are real: `give lottery ticket 1 to Cass` moves your chance with
the paper. When `draw_at` passes, the next tick rolls the drum:

```text
The drum rattles: ticket 2 wins! Cass collects 20 credits.
```

To watch it now: `@tr the lottery terminal/draw`. Try to cheat: have a
confederate hold a home-made "lottery ticket 1" with a `serial`
attribute — the drum picks serial 1, the *ledger* resolves to the minted
object in your rival's pack, and the fake never even gets looked at.
Drop the only sold ticket on the floor before the draw and the pot rolls
over into the next round.

## Going further

- **House cut.** Pay out `pot * 9 // 10` and burn the rest with
  `adjust_credits(me, -pot // 10)` — a lottery is the politest credit
  sink ever invented.
- **Multi-buy.** `$lotto buy *` looping `int(arg0)` mints in one
  transaction — the ledger rows and the pot arithmetic don't change.
- **Winner wasn't watching.** The payout already reaches an absent
  holder (`transfer_credits` doesn't care where they stand); add
  `pemit(holder, ...)` so a winner across the map hears the good news —
  the bank-wire pattern from tutorial 087.
- **Syndicate tickets.** Let a *container* hold tickets and split the
  prize across everyone tagged on it — `loc(t)` gives the box, the box's
  `members` attribute gives the shares.
