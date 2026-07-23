# 001. Slot Machine

> Checklist item 1 ([now]): *$-commands, rand()/switch() tables, transfer_credits, ON_PAYMENT*

**What you'll build:** A one-armed bandit. `pay 10 to slot machine` stakes a
pull, `pull` spins a weighted payout table, and the machine pays winners out of
its own credit balance, with the odds tilted 15% in the house's favor.

**Concepts:** [`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks), the
[event data namespace](../reference/softcode.md#event-data-namespace),
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits),
a [`rand`](../reference/softcode.md#fn-rand) plus
[`switch`](../reference/softcode.md#fn-switch) payout table,
[`pemit`](../reference/softcode.md#fn-pemit) versus
[`oemit`](../reference/softcode.md#fn-oemit), and a live `[[...]]` description.

Build the [magic 8-ball](005_magic_8ball.md) first for `@create`, `@set`, and
the `$pattern:code` trigger.

## How it works

A script runs with its object's authority, so the machine can spend its own
credits but can never take from a player, and `transfer_credits(enactor, me, 10)`
fails by design. The wager has to arrive through the built-in `pay` instead,
which propagates an `event:payment` action and runs any
[`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks) hook on the target.
Money in through `pay` and out through
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits) is the shape
of every paid machine in REALM.

The hook reads the amount straight off the action with `adata('amount')`, one of
the names in the
[event data namespace](../reference/softcode.md#event-data-namespace). It also
has to open with `if target is me:`, because an `ON_PAYMENT` fires on every
object in the room, and unguarded it would arm a free pull whenever somebody
paid the vending machine standing next to it. See
[Guard on `target`](../reference/softcode.md#guard-on-target).

Paying and pulling are separate moments, so the stake is written to a per-player
key on the machine, `'stake_' + enactor.id`. Paying arms it and pulling spends
it.

One `rand(1, 100)` roll sorts into a tier, and
[`switch()`](../reference/softcode.md#fn-switch) maps that tier to both a prize
and a line of reel art:

| roll | weight | reels | prize (on a 10 cr stake) |
|------|-------:|-------|-------------------------:|
| 1 | 1% | `[ NOVA : NOVA : NOVA ]` | 250 |
| 2 to 5 | 4% | `[ BELL : BELL : BELL ]` | 50 |
| 6 to 15 | 10% | `[ STAR : STAR : ---- ]` | 20 |
| 16 to 35 | 20% | `[ STAR : ---- : ---- ]` | 10 (push) |
| 36 to 100 | 65% | `[ ---- : ---- : ---- ]` | 0 |

Expected return per 10 wagered is `(1*250 + 4*50 + 10*20 + 20*10) / 100 = 8.5`,
an 85% return that leaves a 15% house edge. Recompute this whenever you retune
the table, because it is easy to build a slot machine that loses money. That
edge is also what makes the machine a currency sink.

## Build it

Each script below is a `'''` multi-line block: open a line with a trailing
`'''`, write the body, close with a line of just `'''`. The logic reads as
ordinary indented Python instead of a semicolon one-liner (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)),
and you can even leave `#` comments in it.

**The cabinet.** Create the machine and give it a living face. The `[[...]]`
block in the description runs per viewer at look time, so the hopper figure is
read fresh from [`credits(me)`](../reference/softcode.md#fn-credits) on every
look and never goes stale:

```text
@create slot machine
drop slot machine
@desc slot machine = A one-armed bandit in scuffed chrome, three reels asleep behind smeared glass. [[result = f'The hopper holds {credits(me)} credits.']]
```

**Take the wager.** Set the price, then the `ON_PAYMENT` hook that fires when
someone `pay`s the machine. It reads the stake off the action with
[`adata('amount')`](../reference/softcode.md#event-data-namespace), arms a pull
when the money covers the cost, and refunds otherwise:

```text
@set slot machine/cost = 10
@set slot machine/on_payment = '''
if target is me:  # ON_PAYMENT fires on EVERY object in the room, so guard it
    cost = V('cost', 10)
    paid = adata('amount')
    k = 'stake_' + enactor.id  # per-player, so two gamblers never share a lever
    if paid >= cost:
        incr(k)
        transfer_credits(me, enactor, paid - cost)  # refund any overpay
        pemit(enactor, 'Clunk. The lever unlocks: type pull.')
    else:
        transfer_credits(me, enactor, paid)  # underpaid: refund it all, no pull
        pemit(enactor, f'A pull costs {cost} credits. Coins returned.')
'''
```

That first line is the one to never forget: an `ON_PAYMENT` hook fires on
*every* object in the room, so without `if target is me:` the machine would arm
a free pull whenever someone paid the vending machine next to it (see
[Guard on `target`](../reference/softcode.md#guard-on-target)). The stake is
written to a per-player key, `'stake_' + enactor.id`, so paying arms it and
pulling spends it. [`V('cost', 10)`](../reference/softcode.md#fn-v) is shorthand
for `get_attr(me, 'cost', 10)`, and [`incr`](../reference/softcode.md#fn-incr)
bumps that key by one.

**Spin the reels.** The `$pull` command refuses without a stake, rolls once,
sorts the roll into a weighted tier, and maps the tier to both a prize and a
line of reel art with [`switch()`](../reference/softcode.md#fn-switch):

```text
@set slot machine/cmd_pull = '''
$pull:
k = 'stake_' + enactor.id
staked = V(k, 0)
if not staked:
    pemit(enactor, 'The lever will not budge. Stake a pull first: pay 10 to slot machine.')
else:
    roll = rand(1, 100)
    tier = 1 if roll <= 1 else (2 if roll <= 5 else (3 if roll <= 15 else (4 if roll <= 35 else 5)))
    prize = switch(tier, 1, 250, 2, 50, 3, 20, 4, 10, 0)  # trailing arg is the default: a loss
    reels = switch(tier, 1, '[ NOVA : NOVA : NOVA ]', 2, '[ BELL : BELL : BELL ]', 3, '[ STAR : STAR : ---- ]', 4, '[ STAR : ---- : ---- ]', '[ ---- : ---- : ---- ]')
    decr(k)
    oemit(enactor, f'{name(enactor)} pulls the lever. The reels clatter.')  # the whole room
    pemit(enactor, reels)  # only the puller sees the reels
    if prize:
        transfer_credits(me, enactor, prize)
        pemit(enactor, f'Payout! {prize} credits rattle into the tray.')
    else:
        pemit(enactor, 'The reels settle on nothing. The house smiles.')
'''
```

[`decr`](../reference/softcode.md#fn-decr) spends the stake, then
[`oemit`](../reference/softcode.md#fn-oemit) tells the room while
[`pemit`](../reference/softcode.md#fn-pemit) tells only the gambler, which is
why everyone hears the lever but only the player sees the reels. Neither script
tracks the machine's balance, because
[`credits(me)`](../reference/softcode.md#fn-credits) always knows it.

**Stock the hopper.** A machine that cannot cover a jackpot fails its payout
silently, so seed it with a reserve before anyone plays:

```text
@eval m = get('slot machine'); adjust_credits(m, 500); result = credits(m)
```

## Try it

Give yourself pocket money with `@eval adjust_credits(me, 120)`, then play:

```text
> pull
The lever will not budge. Stake a pull first: pay 10 to slot machine.

> pay 10 to slot machine
Clunk. The lever unlocks: type pull.

> pull
[ STAR : ---- : ---- ]
Payout! 10 credits rattle into the tray.

> pay 3 to slot machine
A pull costs 10 credits. Coins returned.
```

Only the reel line and the line under it vary, since they follow the roll; a
loss prints `[ ---- : ---- : ---- ]` and `The reels settle on nothing. The house
smiles.` Everyone else in the room sees just `Bilda pulls the lever. The reels
clatter.`, which is `oemit` and `pemit` doing their separate jobs. `look slot
machine` reads the hopper, the number to watch when you retune the table.

## Going further

- **Progressive jackpot.** On tier 1, pay `credits(me) - 100` instead of a flat
  250. The jackpot becomes whatever players have fed in since the last big win,
  and the 100-credit reserve keeps the machine solvent afterwards.
- **A spinning delay.** Move the payout into a `do_payout` attribute and fire it
  with [`wait(2, 'trigger me/do_payout')`](../reference/softcode.md#fn-wait).
  Waits die on reboot, so use [`expire()`](../reference/softcode.md#fn-expire)
  for anything that must survive one.
- **Loose and tight cabinets.** `@clone slot machine` and edit the clone's
  `cmd_pull` bands. Recompute the expected return each time.
- **Announce jackpots.** Tag the rooms into a zone and call
  [`act(here, f'{name(enactor)} hits the NOVA jackpot!', targeting='zone')`](../reference/softcode.md#fn-act).
