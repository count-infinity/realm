# 001. Slot Machine

> Checklist item 1 ([now]): *$-commands, rand()/switch() tables, transfer_credits, ON_PAYMENT*

**What you'll build:** A one-armed bandit. Typing `pay 10 to slot machine`
stakes a pull, `pull` spins a weighted payout table, and the machine pays
winners out of its own credit balance, with the odds tilted 15% in the
house's favor.

**Concepts:** [`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks),
which turns money arriving into an event; the
[event data namespace](../reference/softcode.md#event-data-namespace),
where `adata('amount')` reads *how much* was paid straight off the
action; [`transfer_credits()`](../reference/softcode.md#fn-transfer_credits)
and the authority rules that govern it; a
[`rand()`](../reference/softcode.md#fn-rand) plus
[`switch()`](../reference/softcode.md#fn-switch) payout table with
house-edge arithmetic; per-player state held in computed attribute keys;
[`pemit`](../reference/softcode.md#fn-pemit) and
[`oemit`](../reference/softcode.md#fn-oemit) for the difference between
telling the player and telling the room; and a live `[[...]]`
description.

Build the [magic 8-ball](005_magic_8ball.md) first. This tutorial assumes
you already know `@create`, `@set`, and the `$pattern:code` trigger, and
it adds an economy on top of them.

## How it works

The finished machine is two scripts that never call each other. One of
them runs when money arrives, the other runs when the lever is pulled,
and the only thing connecting them is a note that the first leaves behind
for the second to find. Everything below is in service of that shape, and
it comes down to four questions: how the money gets in, what the machine
learns when it does, how it knows the money was meant for it, and how the
odds are set.

### Why the player has to hand you the money

A script runs with the authority of the object it lives on, which means
the machine can spend its own credits freely but can never reach into a
player's pocket. Written from the machine, `transfer_credits(me, enactor,
50)` pays a winner and works, while `transfer_credits(enactor, me, 10)`
tries to take from the player and fails by design.

Since the machine cannot take, the player must give, and the built-in
`pay` command is where that consent lives. Paying an object propagates an
`event:payment` action to it, and any
[`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks) attribute on
that object runs in response. Money therefore comes in through `pay` and
goes out through
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits), which
is the shape of every paid machine in REALM.

### What the machine learns from the payment

An `ON_PAYMENT` script runs after the credits have already landed, and it
is handed the action that triggered it, so it never has to guess how much
arrived. Every propagated action is an `Action`, a single object carrying
the actor, the target, a type string, and a payload. (For a full account
of what an `Action` is and how it reaches your object, see
[Action Propagation](../architecture/events.md), and for a guided tour of
the whole event system, see the [event bus tour](245_event_bus_tour.md).)

The names your script can read off that action are the
[event data namespace](../reference/softcode.md#event-data-namespace):

| name | what it is |
|------|------------|
| `adata(key, default)` | the action's payload, which here holds `adata('amount')` |
| `target` | what the action was aimed at, meaning this machine |
| `atype` | the action type string, here `'event:payment'` |
| `actor` | who acted, the same object as `enactor` |

So `paid = adata('amount')` gives you the wager exactly, with nothing to
reconstruct.

### How the machine knows the payment was for it

An `ON_PAYMENT` hook fires on every object in the room rather than only
on the one that was paid. If a vending machine stands beside your slot
machine, then paying the vending machine also runs the slot machine's
hook, and without a guard that would arm a free pull. The guard is an
`if` statement wrapping the entire body of the script:

```text
if target is me: <everything the hook does>
```

Because everything after the colon sits inside the guard, a payment made
to something else runs none of it. Two rules go with this pattern:

1. **The `if` has to come first.** A compound statement cannot follow a
   semicolon, so `k = ...; if target is me: ...` is a syntax error. Put
   the guard at the front, then do the work inside it.
2. **There is no `return`.** Scripts run at module scope, where a bare
   `return` is invalid, so wrap the body in the guard rather than trying
   to bail out early.

For the general rule and the full list of events it applies to, see
[Guard on `target`](../reference/softcode.md#guard-on-target).

### How one payment becomes exactly one pull

The two scripts are separate commands typed at different moments, so the
stake has to be written down somewhere in between. The machine stores it
under a key computed per player, `'stake_' + enactor.id`, which keeps
every gambler's stake separate on the one shared cabinet. Paying arms a
stake, and pulling refuses when the stake is zero and consumes it when it
spins.

### How the odds are set

A single `rand(1, 100)` roll is sorted into a tier, and
[`switch()`](../reference/softcode.md#fn-switch) maps that tier to both a
prize and a line of reel art:

| roll | weight | reels | prize (on a 10 cr stake) |
|------|-------:|-------|-------------------------:|
| 1 | 1% | `[ NOVA : NOVA : NOVA ]` | 250 |
| 2 to 5 | 4% | `[ BELL : BELL : BELL ]` | 50 |
| 6 to 15 | 10% | `[ STAR : STAR : ---- ]` | 20 |
| 16 to 35 | 20% | `[ STAR : ---- : ---- ]` | 10 (push) |
| 36 to 100 | 65% | `[ ---- : ---- : ---- ]` | 0 |

The expected return on every 10 credits wagered is `(1*250 + 4*50 +
10*20 + 20*10) / 100 = 8.5`, an 85% return that leaves the house a 15%
edge. Recompute this whenever you tune the table, because it is
disturbingly easy to build a slot machine that loses money; the showcase
test suite pins this exact table below break-even for that reason. That
edge is also what makes the machine useful as a *currency sink*: credits
enter your world through loot and wages, and sinks like this one drain
them back out before the economy inflates.

## Build it

Start with the cabinet itself. Its credit balance, which slot-machine
people call the hopper, is readable at a glance because `[[...]]` blocks
inside a description are evaluated per viewer at the moment the
description is rendered:

```text
@create slot machine
drop slot machine
@desc slot machine = A one-armed bandit in scuffed chrome, three reels asleep behind smeared glass. [[result = f'The hopper holds {credits(me)} credits.']]
@set slot machine/cost = 10
```

Next comes the wager intake, which runs in five steps: guard on `target`
so a neighbour's payment is ignored, look up the price, read the amount
off the action, compute this player's stake key, and finally either arm a
stake and refund any overpayment or refund the whole thing with an
explanation.

Two small helpers appear here for the first time.
[`V`](../reference/softcode.md#fn-v) reads an attribute off `me`, the
object the script is running as, so `V('cost', 10)` is exactly
`get_attr(me, 'cost', 10)` written more briefly. `incr(k)` bumps a
numeric attribute on `me` by one and
[`decr`](../reference/softcode.md#fn-decr) is its mirror, which is tidier
than reading a value, adding to it, and writing it back by hand. The
`(do_this, do_that) if ok else (other)` tuple is the standard way to
write a branch on one line, and because its elements evaluate left to
right it reads like a small transaction:

```text
@set slot machine/on_payment = if target is me: cost = V('cost', 10); paid = adata('amount'); k = 'stake_' + enactor.id; (incr(k), transfer_credits(me, enactor, paid - cost), pemit(enactor, 'Clunk. The lever unlocks: type pull.')) if paid >= cost else (transfer_credits(me, enactor, paid), pemit(enactor, f'A pull costs {cost} credits. Coins returned.'))
```

The lever is the longer of the two scripts, so it helps to read it as a
sequence before reading it as a line. It looks up the stake and refuses
immediately if there is none, rolls once, sorts the roll into a tier,
uses `switch()` twice to turn that tier into a prize and a line of reel
art, and then commits the spin by consuming the stake, telling the room
what it sees, showing the player the reels, and paying out if anything
was won. Note the division of labour in the messaging:
[`oemit`](../reference/softcode.md#fn-oemit) sends to everyone in the
room except the player, while [`pemit`](../reference/softcode.md#fn-pemit)
sends privately to the player alone, which is why the room hears the
lever but only the gambler sees the reels.

```text
@set slot machine/cmd_pull = $pull: k = 'stake_' + enactor.id; staked = V(k, 0); pemit(enactor, 'The lever will not budge. Stake a pull first: pay 10 to slot machine.') if not staked else None; roll = rand(1, 100); tier = 1 if roll <= 1 else (2 if roll <= 5 else (3 if roll <= 15 else (4 if roll <= 35 else 5))); prize = switch(tier, 1, 250, 2, 50, 3, 20, 4, 10, 0); reels = switch(tier, 1, '[ NOVA : NOVA : NOVA ]', 2, '[ BELL : BELL : BELL ]', 3, '[ STAR : STAR : ---- ]', 4, '[ STAR : ---- : ---- ]', '[ ---- : ---- : ---- ]'); (decr(k), oemit(enactor, f'{name(enactor)} pulls the lever. The reels clatter.'), pemit(enactor, reels), (transfer_credits(me, enactor, prize), pemit(enactor, f'Payout! {prize} credits rattle into the tray.')) if prize else pemit(enactor, 'The reels settle on nothing. The house smiles.')) if staked else None
```

Notice that neither script keeps a running total of the machine's money,
because neither one needs to. The payment event reports what the machine
was just paid, and [`credits(me)`](../reference/softcode.md#fn-credits)
reports what it currently holds whenever the machine wants to know.

Finally, stock the machine with money to pay out of, since a machine that
cannot cover a jackpot will fail its payout silently. One `@eval` does
it, and minting onto the machine is allowed here because you own it:

```text
@eval m = get('slot machine'); adjust_credits(m, 500); result = credits(m)
```

## Try it

Give yourself some pocket money first:

```text
@eval adjust_credits(me, 120); result = credits(me)
```

Then play, checking each response as you go:

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

> look slot machine
A one-armed bandit in scuffed chrome, three reels asleep behind smeared glass.
The hopper holds 500 credits.
```

The reel line and the line under it are the only part that varies, since
they depend on the roll; a losing spin prints `[ ---- : ---- : ---- ]`
followed by `The reels settle on nothing. The house smiles.` instead.
Everyone else standing in the room sees none of that, only `Bilda pulls
the lever. The reels clatter.`, which is `oemit` and `pemit` doing their
separate jobs.

Two things are worth confirming deliberately. The 3-credit payment came
straight back, so your balance is untouched by an underpayment. And the
hopper figure in the description is the machine's lifetime net take,
which is the number to watch when you tune the payout table on a live
game.

## Going further

- **Progressive jackpot.** On tier 1, pay out `credits(me) - 100` instead
  of a flat 250. The machine then hands over everything it is holding
  except a 100-credit reserve, so the jackpot becomes whatever players
  have fed in since the last big win: it grows with every losing pull and
  empties when somebody finally hits NOVA. Holding back that 100 keeps
  the machine solvent enough to cover small prizes in the minutes after a
  jackpot, so it never needs re-seeding by hand.
- **A spinning delay.** Calling
  [`wait(2, 'trigger me/do_payout')`](../reference/softcode.md#fn-wait)
  makes the reels appear to spin for two seconds. Move the payout into a
  `do_payout` attribute and fire it with that one-shot timer. Be aware
  that waits are held in memory, so a reboot mid-spin eats the stake; for
  anything that must survive a restart, use
  [`expire()`](../reference/softcode.md#fn-expire) instead.
- **Loose and tight cabinets.** Run `@clone slot machine` and edit the
  clone's `cmd_pull` bands to give a room several machines with different
  personalities. Recompute the expected return every time you do.
- **Announce jackpots to the whole casino.** Tag the rooms into a zone and
  call [`act(here, f'{name(enactor)} hits the NOVA jackpot!',
  targeting='zone')`](../reference/softcode.md#fn-act), because a public
  win is the best advertising a casino has.
