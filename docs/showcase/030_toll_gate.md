# 030. Toll Gate

> Checklist item 30 — now — *on_check credit gate, transfer_credits, ON_PAYMENT*

**What you'll build:** A toll gate on the King's Highway: the keeper
bars the way until you pay 5 credits at the booth, your payment buys a
minute's stamp, underpayment is counted and pushed back — and the
booth's owner can empty the strongbox whenever they like.

**Concepts:** a movement ward reading world state (`on_check` +
`adata('exit')`), the built-in `pay` command and `ON_PAYMENT` trigger,
reading an action's payload from a reaction (`adata('amount')`),
`credits()`/`transfer_credits()`, and the decision/mutation split: the
ward only ever *reads* what the payment already *wrote*.

## How it works

**Ward and payment are separate machines.** An `on_check` ward runs in
the read-only decision pass — it can `block()` a walk but cannot take
your money. So the toll is two pieces that meet in the middle: the
`pay` command moves the credits and fires the booth's `ON_PAYMENT`
(a *reaction*, full softcode power), which writes a timestamped pass
onto the booth; the **ward on the road** reads that pass and decides.
Ward placement matters: the gating action for a walk targets the
*rooms*, not the exit, so the ward sits on Market Road and keys itself
to this one exit with `adata('exit') == get('toll gate')` — every
other road out stays free.

**The stamp is a deadline, not a flag.** `ON_PAYMENT` writes
`pass_<payer-id> = now() + 60`: a pass that *expires by arithmetic*.
The ward compares `now()` against it — no cleanup job, no consumable
state a read-only ward couldn't consume anyway. Time-window passes are
the ward-friendly shape of "one crossing."

**The action tells you what happened.** `ON_PAYMENT` is a *reaction*,
and reactions are handed the action's payload: `adata('amount')` is
what this payer just handed over. That one read is the whole
bookkeeping problem — `paid = adata('amount', 0)`, branch on it.
Underpayers get exact change back via
`transfer_credits(me, enactor, paid)`: the money has already landed on
the booth when the trigger fires, and the executor (the booth)
controls itself, so it may refund from its own balance.

**The till-delta this replaced** (and when you'd still reach for it).
Until the engine bound action data into event triggers, `ON_PAYMENT`
could see *that* it was paid but not *how much* — so this tutorial
reconstructed the amount by watching its own balance: keep a `till`
attribute of the last-known total and derive
`paid = credits(me) - till`, re-stamping `till` after every branch.
It is an honest technique and worth knowing, because it is the general
shape of **reconstructing state you cannot observe** — some actions
still carry no payload, and a delta against your own last-known value
is how you recover one. But it is no longer the right tool *here*, and
the cost it was paying is worth naming: `till` is a shadow of a number
the engine already knows, so every other script that touches the
booth's money has to remember to keep the shadow honest. (The old
`$collect till` had to re-zero `till` for exactly that reason — a
coupling that vanishes below.) Reach for a delta when there is no
payload; read the payload when there is one.

**Collection is authority.** `$collect till` compares `enactor ==
owner(me)` — softcode's owner check, no admin flag needed — then
`transfer_credits` empties the booth into the owner's pocket.

## Build it

The road, the highway beyond the gate (both faces named `toll gate` —
we'll only toll the outbound side), and the booth:

```text
@dig Market Road
@teleport me = Market Road
@dig The King's Highway = toll gate, toll gate
@create toll booth
drop toll booth
@set toll booth/fee = 5
```

The payment side — read the amount off the action, stamp on success,
exact change on a short count:

```text
@set toll booth/on_payment = fee = V('fee', 5); paid = adata('amount', 0) if target is me else 0; (set_attr(me, 'pass_' + enactor.id, now() + 60), pemit(enactor, 'The keeper stamps your wrist: paid, good for a minute.')) if paid >= fee else (transfer_credits(me, enactor, paid), pemit(enactor, f'The keeper counts {paid} and pushes it back: the toll is {fee}.'))
```

The owner's tap. Note what *isn't* here: no `till` to re-zero. The
booth's balance is the only copy of the number, so emptying it is just
emptying it:

```text
@set toll booth/cmd_collect = $collect till: pemit(enactor, 'The strongbox is not yours to empty.') if enactor != owner(me) else (pemit(enactor, 'You empty the strongbox: ' + str(credits(me)) + ' credits.'), transfer_credits(me, enactor, credits(me)))
```

And the ward on the road — blocks the *gate*, quotes the fee, and tells
the traveler exactly what to type:

```text
@set here/on_check = booth = get('toll booth'); fee = get_attr(booth, 'fee', 5); block('The keeper bars the way: the toll is ' + str(fee) + ' credits. (pay ' + str(fee) + ' to toll booth)') if has_atag('movement') and adata('exit') == get('toll gate') and now() > get_attr(booth, 'pass_' + actor.id, 0) else None
```

## Try it

With 12 credits in your pocket:

```text
toll gate               -> The keeper bars the way: the toll is 5 credits.
                           (pay 5 to toll booth)
pay 3 to toll booth     -> The keeper counts 3 and pushes it back: the toll is 5.
pay 5 to toll booth     -> The keeper stamps your wrist: paid, good for a minute.
toll gate               -> you're on the King's Highway
toll gate               -> and back -- the return face was never tolled
```

Wait out the minute and the gate bars you again — the stamp expired by
arithmetic, nothing ran. Then, as the builder:

```text
collect till            -> You empty the strongbox: 5 credits.
```

(Anyone else typing it gets `The strongbox is not yours to empty.`)

## Engine gaps

- ~~`ON_PAYMENT` softcode cannot read the amount paid~~ — **FIXED
  2026-07-17**: event triggers now bind `adata()`, so `adata('amount')`
  returns it directly, and the build above uses it. The till-delta that
  used to stand in for it is described under "How it works" — it
  remains the technique for actions that genuinely carry no payload,
  but a payment is no longer one of them.
- As with the other traversal items: the audit's "exit `on_check`"
  ward actually lives on the room (the exit is a bystander to the
  gating action), keyed by `adata('exit')`.

## Going further

- **Toll both ways** — put the mirror-image ward on the Highway; the
  same booth stamp works from either side, so one payment still buys
  the round trip within the minute. Separate stamps? Prefix the attr
  per side.
- **Frequent-traveler pass** — sell a `toll pass` item and let the ward
  wave through anyone carrying it (`any(get_attr(o, 'toll_exempt', 0)
  for o in contents(actor))`) — the [keycard door](026_keycard_door.md)
  trick meeting the toll ward.
- **A bribeable guard** — replace the booth with the
  [guarded exit](031_guarded_exit.md)'s NPC and have *his*
  `ON_PAYMENT` bump `adjust_disposition` instead of stamping wrists:
  bribes are just payments someone was waiting for.
- **Dynamic pricing** — the ward already reads `fee` at decision time;
  a zone master's `ON_TICK` can surge-price rush hour.
