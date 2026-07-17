# 001. Slot Machine

> Checklist item 1 — [now] — *$-commands, rand()/switch() tables, transfer_credits, ON_PAYMENT*

**What you'll build:** A one-armed bandit. `pay 10 to slot machine`
stakes a pull, `pull` spins a weighted payout table, and the machine
pays winners out of its own hopper — with the odds tilted 15% in the
house's favor.

**Concepts:** `ON_PAYMENT` (money as an event), the **event namespace**
(`adata('amount')` — reading *how much* was paid straight off the
action), `transfer_credits()` and softcode money authority, a
`rand()`+`switch()` payout table and house-edge arithmetic, per-player
state in attribute keys, `pemit`/`oemit` actor-vs-room messaging, a
living `[[...]]` description.

Build the [magic 8-ball](005_magic_8ball.md) first — this assumes you
know `@create`/`@set` and the `$pattern:code` trigger, and adds the
economy on top.

## How it works

**Money moves by consent, not by script fiat.** A script runs with its
object's authority: the machine can spend *its own* credits
(`transfer_credits(me, enactor, ...)`) but can never reach into a
player's pocket — `transfer_credits(enactor, me, ...)` fails, by
design. So the wager has to travel on the one command where a player
consents to hand money over: the built-in `pay`. Paying an object
propagates `event:payment`, and any `ON_PAYMENT` attribute on the
target fires. Money in via `pay`, money out via `transfer_credits` —
that's the shape of every paid machine in REALM.

**The event namespace.** An `ON_PAYMENT` script fires *after* the
credits have landed — but it is not left guessing how many. Every
`ON_<EVENT>` script is handed the action that fired it:

| name | what it is |
|------|------------|
| `adata(key, default)` | the action's payload — `adata('amount')` here |
| `target` | what the action was aimed at (this machine) |
| `atype` | the action type string (`'event:payment'`) |
| `actor` | who acted — the same object as `enactor` |

So `paid = adata('amount')` *is* the wager, exactly, with no
bookkeeping. (You will meet older softcode that instead keeps a
`ledger` attribute and reads the payment as
`credits(me) - V('ledger', 0)`, re-syncing the ledger after every
balance change. That's the **ledger idiom**, and it existed only
because the amount used to be unreadable — it reconstructed the number
from the one thing a script *could* see, its own balance. `adata` made
it unnecessary; reach for the payload, not the difference.)

`V(key, default)` in these scripts is just the shorthand for reading an
attribute off `me` — you'll use it constantly.

**One stake, one pull.** A valid payment arms exactly one pull, stored
per player under a computed key — `'stake_' + enactor.id` — the same
per-player-attribute idiom the tutorial descriptions use for memoized
rolls. `pull` refuses when your stake is 0 and consumes it when it
spins.

**The payout table.** One `rand(1, 100)` roll is banded into a tier,
and `switch()` maps tiers to prizes and reel art:

| roll      | weight | reels                    | prize (on a 10 cr stake) |
|-----------|-------:|--------------------------|-------------------------:|
| 1         |     1% | `[ NOVA : NOVA : NOVA ]` | 250 |
| 2–5       |     4% | `[ BELL : BELL : BELL ]` | 50  |
| 6–15      |    10% | `[ STAR : STAR : ---- ]` | 20  |
| 16–35     |    20% | `[ STAR : ---- : ---- ]` | 10 (push) |
| 36–100    |    65% | `[ ---- : ---- : ---- ]` | 0   |

Expected return per 10 wagered: `(1·250 + 4·50 + 10·20 + 20·10) / 100
= 8.5` — an 85% return, a 15% house edge. Recompute this whenever you
tune the table; it is disturbingly easy to build a slot machine that
loses money. (The showcase test suite pins this exact table below
break-even.) That edge is what makes the machine a *currency sink*:
credits enter your world through loot and pay, and sinks drain them
back out before the economy inflates.

## Build it

The cabinet, with a hopper you can read at a glance — `[[...]]` blocks
in a description run per viewer at render time, so the description
*is* the bookkeeping display:

```text
@create slot machine
drop slot machine
@desc slot machine = A one-armed bandit in scuffed chrome, three reels asleep behind smeared glass. [[result = f'The hopper holds {credits(me)} credits.']]
@set slot machine/cost = 10
```

The wager intake. Read the amount off the action, then branch — arm a
stake and refund any change, or refund everything with an explanation.
`incr(k)` arms the stake: it bumps a numeric attribute on `me` by one
(`decr` is its mirror), which beats reading, adding and writing back by
hand. The `(do_this, do_that) if ok else (other)` tuple is the standard
one-line branch: elements evaluate left to right, so it reads like a
tiny transaction:

```text
@set slot machine/on_payment = cost = V('cost', 10); paid = adata('amount') if target is me else 0; k = 'stake_' + enactor.id; (incr(k), transfer_credits(me, enactor, paid - cost), pemit(enactor, 'Clunk. The lever unlocks: type pull.')) if paid >= cost else (transfer_credits(me, enactor, paid), pemit(enactor, f'A pull costs {cost} credits. Coins returned.'))
```

The lever. Roll, band into a tier, `switch()` twice (prize, reel art),
then either refuse (no stake) or commit the whole spin — consume the
stake, show the room you playing (`oemit` excludes you), show you the
reels (`pemit` is private), and pay out if you won:

```text
@set slot machine/cmd_pull = $pull: k = 'stake_' + enactor.id; staked = V(k, 0); pemit(enactor, 'The lever will not budge. Stake a pull first: pay 10 to slot machine.') if not staked else None; roll = rand(1, 100); tier = 1 if roll <= 1 else (2 if roll <= 5 else (3 if roll <= 15 else (4 if roll <= 35 else 5))); prize = switch(tier, 1, 250, 2, 50, 3, 20, 4, 10, 0); reels = switch(tier, 1, '[ NOVA : NOVA : NOVA ]', 2, '[ BELL : BELL : BELL ]', 3, '[ STAR : STAR : ---- ]', 4, '[ STAR : ---- : ---- ]', '[ ---- : ---- : ---- ]'); (decr(k), oemit(enactor, f'{name(enactor)} pulls the lever. The reels clatter.'), pemit(enactor, reels), (transfer_credits(me, enactor, prize), pemit(enactor, f'Payout! {prize} credits rattle into the tray.')) if prize else pemit(enactor, 'The reels settle on nothing. The house smiles.')) if staked else None
```

Note what *isn't* in either script: bookkeeping. Nothing tracks the
machine's balance, because nothing needs to — the payment tells the
machine what it was paid, and `credits(me)` tells it what it holds
whenever it wants to know.

Finally, the float. A machine that can't cover a jackpot fails its
payout silently — seed the hopper in one `@eval` (you own the machine,
so minting onto it is allowed):

```text
@eval m = get('slot machine'); adjust_credits(m, 500); result = credits(m)
```

## Try it

Give yourself pocket money, then play:

```text
@eval adjust_credits(me, 120); result = credits(me)
credits
pull
pay 10 to slot machine
pull
credits
pay 3 to slot machine
look slot machine
```

Expected beats: the first `pull` answers `The lever will not budge.
Stake a pull first: pay 10 to slot machine.`; the payment answers
`Clunk. The lever unlocks: type pull.`; the second `pull` prints a reel
line and either a payout or `The reels settle on nothing. The house
smiles.` — while everyone else in the room sees `Bilda pulls the lever.
The reels clatter.`. The 3-credit payment bounces with `A pull costs 10
credits. Coins returned.` and your balance is untouched. `look slot
machine` reads the hopper — the machine's lifetime net take, the number
to watch when you tune the table on a live game.

## Going further

- **Progressive jackpot:** on tier 1, pay out `credits(me) - 100`
  instead of a flat 250 — the hopper itself becomes the prize, and the
  machine self-balances.
- **A spinning delay:** `wait(2, 'trigger me/do_payout')` makes the
  reels "spin" for two seconds — move the payout into a `do_payout`
  attribute and fire it with the one-shot timer. (Waits are in-memory:
  a reboot mid-spin eats the stake — for anything that must survive,
  use `expire()`.)
- **Loose and tight cabinets:** `@clone slot machine`, then edit the
  clone's `cmd_pull` bands. Recompute the expected return every time.
- **Announce jackpots to the whole casino:** tag the rooms into a zone
  and `act(here, f'{name(enactor)} hits the NOVA jackpot!',
  targeting='zone')` — public wins are the best advertising a casino
  has.
