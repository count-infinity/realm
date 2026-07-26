# 030. Toll Gate

> Checklist item 30 ([now]): *on_check credit gate, transfer_credits, ON_PAYMENT*

**What you'll build:** A toll gate on the King's Highway. The keeper bars
the road until you pay 5 credits at the booth, your payment buys a one
minute pass, underpayment is counted and pushed back, and the booth's
owner can empty the strongbox whenever they like.

**Concepts:** a movement ward that reads world state (`on_check` plus
[`adata('exit')`](../reference/softcode.md#event-data-namespace)), the
built-in `pay` command and its
[`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks) reaction,
[`credits`](../reference/softcode.md#fn-credits) and
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits), and
the decision/mutation split where the ward only ever *reads* what the
payment already *wrote*.

## How it works

A toll gate is two machines that meet in the middle. The `pay` command
moves the credits and fires the booth's `ON_PAYMENT`, a reaction with
full softcode power that stamps a timed pass onto the booth. A separate
ward on the road reads that stamp and decides whether to block the walk.
This section covers why the two halves are separate, where the ward
sits, and how the reaction learns the amount.

### Why payment and passage are separate machines

An [`on_check`](../design/action-phases.md) ward runs in the read-only
decision pass: it sees the world *before* the effect and may
[`block()`](../reference/softcode.md#event-data-namespace) a walk, but it
cannot take your money. So the toll is split. Money arrives through the
built-in `pay`, which propagates an `event:payment` action and runs any
`ON_PAYMENT` reaction on the target; a reaction sees the world *after*
the effect and has the full write vocabulary, so it can stamp a pass and
refund coins. Money in through `pay` and out through
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits) is the
shape of every paid machine in REALM, as in the
[slot machine](001_slot_machine.md) and the
[vending machine](002_vending_machine.md).

### Where the ward sits

The gating action for a walk targets the *rooms*, not the exit (the exit
is a bystander to its own traversal), so the ward lives on Market Road,
not on the toll gate itself. It keys to this one exit with
`adata('exit') == get('toll gate')`. Because
[`get('toll gate')`](../reference/softcode.md#fn-get) resolves the local
outbound face and the return face is a different exit object,
only the outbound walk is tolled and every other road out of the room
stays free.

### How the reaction reads the amount

`ON_PAYMENT` sees post-state: by the time it fires, the credits have
already moved onto the booth, so
[`adata('amount')`](../reference/softcode.md#event-data-namespace) is
exactly what this payer handed over, and that one read is the whole
bookkeeping problem. An underpayer gets exact change back with
`transfer_credits(me, enactor, paid)`, which works because the coins are
already sitting on the booth and a script controls its own object's
balance. The hook opens with
[`if target is me:`](../reference/softcode.md#guard-on-target) because
`ON_PAYMENT` fires on *every* object in the room, so without the guard,
paying the newsstand next to the booth would run the booth's hook too.

### The stamp is a deadline, not a flag

On full fare the hook writes
[`set_attr`](../reference/softcode.md#fn-set_attr)`(me, 'pass_' +
enactor.id, `[`now()`](../reference/softcode.md#fn-now)` + 60)`: a
per-payer pass that expires by arithmetic. The ward compares `now()`
against it, so there is no cleanup job and no consumable state a
read-only ward could not spend anyway. A time-window pass is the
ward-friendly shape of "one crossing."

### Collecting is an owner check

`$collect till` compares `enactor` against
[`owner(me)`](../reference/softcode.md#fn-owner), softcode's own
ownership test with no admin flag needed, then empties the booth into the
owner's pocket with `transfer_credits`. The booth's balance is the only
copy of the take, so emptying it is just emptying it.

## Build it

First the shell: the road, the highway beyond the gate (both faces named
`toll gate`, and only the outbound side is tolled), the booth dropped on
the road, and its fee.

```text
@dig Market Road
@teleport me = Market Road
@dig The King's Highway = toll gate, toll gate
@create toll booth
drop toll booth
@set toll booth/fee = 5
```

The payment side reads the amount off the action, stamps a pass on full
fare, and returns exact change on a short count. It is a `'''` heredoc
block: open the `@set` line with a trailing `'''`, write the body as
ordinary indented softcode, and close with a line of just `'''`.

```text
@set toll booth/on_payment = '''
if target is me:  # ON_PAYMENT fires on every object in the room, so guard it
    fee = V('fee', 5)
    paid = adata('amount', 0)  # what THIS payer handed over
    if paid >= fee:
        set_attr(me, 'pass_' + enactor.id, now() + 60)  # a per-payer deadline
        pemit(enactor, 'The keeper stamps your wrist: paid, good for a minute.')
    else:
        transfer_credits(me, enactor, paid)  # coins already landed here; refund them
        pemit(enactor, f'The keeper counts {paid} and pushes it back: the toll is {fee}.')
'''
```

The owner's tap: a `$collect` command that refuses anyone but the owner,
then pours the whole balance out. Nothing else needs zeroing, because the
booth's own balance is the take.

```text
@set toll booth/cmd_collect = $collect till: pemit(enactor, 'The strongbox is not yours to empty.') if enactor != owner(me) else (pemit(enactor, 'You empty the strongbox: ' + str(credits(me)) + ' credits.'), transfer_credits(me, enactor, credits(me)))
```

Finally the ward on the road. It fires on the outbound walk, blocks it
while the payer has no live pass, quotes the fee, and tells the traveler
exactly what to type. It reads `booth` by name because the room, not the
booth, is the executor here.

```text
@set here/on_check = '''
booth = get('toll booth')
fee = get_attr(booth, 'fee', 5)
# adata('exit') is THIS exit; get('toll gate') is the local outbound face
if has_atag('movement') and adata('exit') == get('toll gate') and now() > get_attr(booth, 'pass_' + actor.id, 0):
    block('The keeper bars the way: the toll is ' + str(fee) + ' credits. (pay ' + str(fee) + ' to toll booth)')
'''
```

## Try it

With 12 credits in your pocket:

```text
toll gate               -> The keeper bars the way: the toll is 5 credits.
                           (pay 5 to toll booth)
pay 3 to toll booth     -> The keeper counts 3 and pushes it back: the toll is 5.
pay 5 to toll booth     -> The keeper stamps your wrist: paid, good for a minute.
toll gate               -> you're on the King's Highway
toll gate               -> back to Market Road; the return face is never tolled
```

Wait out the minute and the gate bars you again: the stamp expired by
arithmetic, and nothing had to run to clear it. Then, standing where the
booth is as its owner:

```text
collect till            -> You empty the strongbox: 5 credits.
```

Anyone else typing it gets `The strongbox is not yours to empty.`

## Going further

- **Toll both ways.** Put the mirror-image ward on the Highway. The same
  booth stamp works from either side, so one payment still buys the round
  trip within the minute. For separate stamps, prefix the pass attribute
  per side.
- **Frequent-traveler pass.** Sell a `toll pass` item and let the ward
  wave through anyone carrying one
  (`any(get_attr(o, 'toll_exempt', 0) for o in contents(actor))`), the
  [keycard door](026_keycard_door.md) trick meeting the toll ward.
- **A bribeable guard.** Replace the booth with the
  [guarded exit](031_guarded_exit.md)'s NPC and have *his* `ON_PAYMENT`
  raise his disposition instead of stamping wrists: a bribe is just a
  payment someone was waiting for.
- **Dynamic pricing.** The ward already reads `fee` at decision time, so
  a zone master's `ON_TICK` can surge-price the rush hour.
- **Actions without a payload.** A payment carries its `amount`, but some
  actions carry nothing to read. When there is no `adata` to read, keep a
  last-known total on the object and derive the change as
  `credits(me)` minus that total, re-stamping the total after each use.
