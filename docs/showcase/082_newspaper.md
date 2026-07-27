# 082. Newspaper

> Checklist item 82 ([now]): *submission queue attrs, ticker publish, ON_PAYMENT kiosk vending, desc_extras pages*

**What you'll build:** The Gazette. Anyone files a story with
`submit <text>`, the press runs on a timer and rolls the queue into a
numbered issue, a paperboy hollers the headline count across the
market, and a kiosk sells physical copies (`pay 5 to kiosk`) whose
pages are readable with a plain `look`.

**Concepts:** a submission **queue attribute** (a list, like the
[bulletin board](076_bulletin_boards.md)'s posts) compiled into
immutable per-issue attributes (`issue_<n>`), `script_ticker` as the
press schedule, [`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks)
plus [`adata('amount')`](../reference/softcode.md#event-data-namespace)
for coin-op vending,
[`create_obj`](../reference/softcode.md#fn-create_obj) with
`desc_extras` to print objects with pages, and the mint-then-hand-over
pattern for putting goods in a buyer's hands.

## How it works

The Gazette is a pipeline. Submissions pile onto a `queue` list on the
bureau, a press ticker freezes that queue into a numbered edition and
blanks it, and a kiosk in the square prints a physical copy on demand.
This section answers where submissions accumulate, how the press
decides to publish, why the kiosk needs a `target` guard, and how a
printed copy becomes readable with a plain `look`.

### Where submissions go

`submit` appends one row to a `queue` list on the bureau:
[`escape`](../reference/softcode.md#fn-escape)`(text)` (because players
author the copy, so it is treated as text rather than markup) followed
by ` --` and the byline, written with
[`set_attr`](../reference/softcode.md#fn-set_attr). The bureau is the
market's zone master, so its `$submit` command fires from anywhere on
the zone: a stringer files from the square just as readily as from the
office.

### How the press decides to publish

The press is an `on_tick` on a slow `script_ticker`. It does nothing
while the queue is empty. When there is copy, it increments the issue
number, freezes the queue into a new `issue_<n>` attribute (one per
edition, so back-numbers stay readable forever), blanks the queue, and
sends a paperboy to [`remit`](../reference/softcode.md#fn-remit) every
market-zone room found with
[`zone_rooms`](../reference/softcode.md#fn-zone_rooms). Periodicity
falls out of the interval: the paper publishes when there is news,
checked on the press's schedule.

Note the shape of that counter. The new value is read up front as
[`V`](../reference/softcode.md#fn-v)`('issue', 0) + 1`, but the write
happens *inside* the `if q` branch. It looks like a textbook
[`incr`](../reference/softcode.md#fn-incr)`('issue')`, and it must not
be one, because `incr` writes unconditionally, so it would walk the
issue number forward on every quiet tick and the Gazette would jump
from No. 1 to No. 6 having printed nothing. A counter that only bumps
on one branch is a guarded write, and guarded writes stay longhand.
Reach for `incr` when the increment is the whole statement, not when it
is the payload of an `if`.

### Why the kiosk needs a target guard

`pay 5 to kiosk` is the builtin economy command. It moves the credits
and then propagates an `event:payment` action through the room, so the
kiosk's `ON_PAYMENT` hook fires with the sum in its payload, read as
[`adata`](../reference/softcode.md#event-data-namespace)`('amount')`.
That one read is the whole cash register: wrong amounts and too-early
customers are refunded with
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits), and
the kiosk's own [`credits`](../reference/softcode.md#fn-credits) balance
is never consulted at all. The alternative would be to keep a `ledger`
attribute mirroring the kiosk's last known balance and recover the sum
as `credits(me) - ledger`, re-stamping it after every branch so the
arithmetic could not drift. `adata('amount')` is told the number
directly, so there is no second copy of the truth to keep honest.

`ON_PAYMENT` fires on *every* object in the room, not only the one that
was paid, so the whole body sits under an
[`if target is me:`](../reference/softcode.md#guard-on-target) guard.
Without it, paying a vendor standing next to the kiosk would run the
kiosk's refund and its messages against someone else's coins. This is
the reactive-hook case: a `$`-command fires on its own object and needs
no guard, but an `ON_<EVENT>` hook is heard room-wide and must screen
out business that is not its own.

### How a copy becomes readable

A copy is a printed object. The kiosk mints the paper *in its own
hands* with `create_obj(..., location=me)`, because conjuring directly
into a stranger's pockets is refused by design, and then relocates it
to the buyer with
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj), the
[coat check](022_coat_check.md) hand-over. The pages are `desc_extras`
rows: a masthead line first, then one `['', line]` per story, the
[camera](008_camera.md)'s photograph trick. An empty condition (the
`''`) means the line shows to everyone who looks, so the builtin `look`
*is* the reading interface: no verbs to teach, and the object is a real
newspaper you can drop on a bar or give to a friend.

The whole sheet lives in `desc_extras`, masthead included, because
softcode `set_attr` writes db attributes and cannot touch the engine's
`description` slot that only `@desc` sets. `desc_extras` is the
softcode-reachable description surface (see the
[graffiti wall](081_graffiti.md), which writes the same surface on a
room). Each copy snapshots the issue at purchase by reading the
bureau's frozen `issue_<n>` with
[`get_attr`](../reference/softcode.md#fn-get_attr); that attribute is
the archive of record.

## Build it

Two rooms, the office and the market, zoned together so the bureau
reaches both:

```text
@dig The Gazette Office = office, out
office
@zone here = market
@dig Market Square = square, office
square
@zone here = market
office
```

The bureau, created in the office and promoted to the market's zone
master so `submit` works anywhere on the zone:

```text
@create Gazette Bureau
drop Gazette Bureau
@desc Gazette Bureau = Ink, brass, and a thundering press. SUBMIT <text> files a story for the next issue.
@zone/master Gazette Bureau = market
```

`submit` appends the escaped story and its byline to the `queue` list:

```text
@set Gazette Bureau/cmd_submit = '''
$submit *:
set_attr(me, 'queue', (V('queue') or []) + [f'{escape(arg0)} --{name(enactor)}'])
pemit(enactor, 'The desk editor spikes your copy for the next issue.')
'''
```

`publish` is the press run: bump the issue number, freeze the queue into
its own `issue_<n>` attribute, blank the queue, then send the paperboy
to every market room. The whole block is guarded by `if q`, so a quiet
tick prints nothing and the counter never moves:

```text
@set Gazette Bureau/publish = '''
q = V('queue') or []
if q:
    n = V('issue', 0) + 1  # bump only when there is copy; a guarded write stays longhand, never incr('issue')
    set_attr(me, 'issue', n)
    set_attr(me, 'issue_' + str(n), q)  # freeze this edition into its own attr so back-numbers stay readable
    set_attr(me, 'queue', [])
    for r in zone_rooms('market'):
        remit(r, f'A paperboy hollers: GAZETTE No. {n}! {len(q)} stories! Fresh at the kiosk!')
'''
```

The press schedule runs `publish` on a slow ticker:

```text
@set Gazette Bureau/on_tick = eval_attr(me, 'publish')
@behavior Gazette Bureau = script_ticker, interval:60
```

The kiosk, built in the square, with its cover price as a plain
attribute:

```text
square
@create news kiosk
drop news kiosk
@desc news kiosk = A tin shed papered with old front pages. PAY 5 TO KIOSK for the latest Gazette.
@set news kiosk/price = 5
```

The register is `on_payment`. Under the `target` guard it refunds early
and short-paying customers in full, and otherwise refunds only the
overpayment, mints a copy in its own hands, stamps the frozen issue onto
the copy's pages, and hands it over:

```text
@set news kiosk/on_payment = '''
if target is me:  # ON_PAYMENT is heard room-wide; only react to coins paid to the kiosk
    b = get('Gazette Bureau')
    paid = adata('amount', 0)
    cost = V('price', 5)
    n = get_attr(b, 'issue', 0)
    if not n:
        transfer_credits(me, enactor, paid)  # nothing printed yet: hand the coins straight back
        pemit(enactor, 'The vendor shrugs: nothing on the stand until the press runs. Coins returned.')
    elif paid < cost:
        transfer_credits(me, enactor, paid)
        pemit(enactor, f'The vendor taps the price card: {cost} credits. Coins returned.')
    else:
        if paid > cost:
            transfer_credits(me, enactor, paid - cost)  # refund only the overpayment
        p = create_obj(f'the Gazette No. {n}', ['thing', 'paper'], me)  # mint in the kiosk's hands, not the buyer's
        rows = get_attr(b, 'issue_' + str(n)) or []
        set_attr(p, 'desc_extras', [['', f'Cheap ink on cheaper paper. The masthead reads THE GAZETTE, No. {n}.']] + [['', row] for row in rows])
        teleport_obj(p, enactor)
        pemit(enactor, f'The vendor folds a Gazette No. {n} into your hands. LOOK gazette to read it.')
'''
```

## Try it

File copy, then let the press run (or wait out the minute):

```text
submit Dock fees to double, harbormaster blames pirates.
   -> The desk editor spikes your copy for the next issue.
(Kess, in the square) submit LOST: one glass eye, sentimental value.
```

On the next press tick, everyone on the market zone hears the paperboy
and the queue is spiked clean:

```text
   -> A paperboy hollers: GAZETTE No. 1! 2 stories! Fresh at the kiosk!
```

At the kiosk:

```text
pay 5 to news kiosk
   -> You pay news kiosk 5 credits.
   -> The vendor folds a Gazette No. 1 into your hands. LOOK gazette to read it.
look gazette
   -> Cheap ink on cheaper paper. The masthead reads THE GAZETTE, No. 1.
   -> Dock fees to double, harbormaster blames pirates. --Bilda
   -> LOST: one glass eye, sentimental value. --Kess
```

Underpay and the vendor taps the price card, coins refunded. Pay before
issue one exists and you get the shrug, coins refunded. New submissions
pile into the *next* edition, so a copy bought after the second press
run reads No. 2 while your old copy still reads No. 1. Printed paper
does not update, which is the charm.

## Going further

- **Back-numbers.** `pay` buys the latest, but a `$order <n>` verb
  reading `issue_<n>` sells the archive (charge double, since collectors
  pay).
- **An editor.** Route `submit` into a `pending` list and give the
  owner a `$spike <n>` / `$run <n>` pair. Editorial control is one
  list-move.
- **Subscriptions.** Keep a `subscribers` list on the bureau and have
  `publish` mint and `teleport_obj` one copy per subscriber. Each copy
  is a real object, so cap your print run.
- **Headlines on the PA.** The paperboy is a `remit` loop, so feed the
  first story's first sentence to the [station PA](078_pa_system.md)
  chime for a wire-service feel.
