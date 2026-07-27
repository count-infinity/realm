# 105. NPC Races & Betting

> Checklist item 105 ([now]): *on_tick simulation, odds attrs, betting-book objects*

**What you'll build:** Bookie Barnum, who chalks odds on a three-runner
field, takes stakes through the `pay` builtin, pencils each bet into a book,
counts down to post time, calls the race one stride at a time, and pays
winners at their odds.

**Concepts:** a ticker-driven simulation (`script_ticker` plus
[`on_tick`](../reference/softcode.md#lifecycle-hooks) as the race clock),
odds stored as data an economy designer can retune, a two-step betting
book (an [`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks) hook arms
a stake and `$back` assigns it), a seeded credit balance so the book can
always pay, and [`eval_attr`](../reference/softcode.md#fn-eval_attr) helpers
that split one NPC's logic into readable pieces.

## How it works

Bookie Barnum is a single NPC whose brain is one ticker plus a handful of
attributes: a `field` of runners with their odds, a `book` of who backed
whom, and the live `positions` during a race. This section answers three
questions in turn: how one ticker runs the whole race, how a bet gets from a
player's credits into the book without either side trusting the other, and
how winners are paid.

### How one ticker runs the whole race, or does nothing

Barnum carries a `script_ticker` behavior, so his
[`on_tick`](../reference/softcode.md#lifecycle-hooks) fires on a fixed
cadence on Barnum himself and on nothing else. Because a ticker fires only
on its own object, the dispatcher needs no `target` guard. Each beat it does
one of three things: if a race is running it advances every runner one
stride, otherwise if the book holds bets it counts down to post time, and
otherwise it does nothing at all.

A stride moves each runner forward by
[`rand`](../reference/softcode.md#fn-rand)`(1, 9 - odds)`, so the odds
attribute is also the speed model: a 2-to-1 favorite strides up to 7 while
the 5-to-1 nag manages at most 4, which means the payout price and the win
chance come from the same number. The first runner to reach `distance` wins
on the spot.

### How a bet gets into the book safely

Betting is two consensual steps. `pay 10 to Bookie Barnum` propagates a
payment action and runs Barnum's
[`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks) hook, which reads
the stake with [`adata`](../reference/softcode.md#event-data-namespace)`('amount')`
and banks it as an armed stake, money in Barnum's balance but not yet on a
runner. Because an `ON_PAYMENT` fires on every object in the room, that hook
must open with `if target is me:`, or paying the hot-dog cart standing next
to him would arm a free bet (see
[Guard on `target`](../reference/softcode.md#guard-on-target)). Then
`back Comet` moves the armed stake into the `book`, keyed by the bettor's id,
and starts the post-time countdown. A payment made while the field is
running bounces straight back, so there is no past-posting. The book, the
field, and the live positions are all ordinary attributes, so
`@examine Bookie Barnum` shows the whole state.

### How winners are paid

A winner is paid stake times (odds + 1), the stake back plus the odds, out
of Barnum's own credit balance with
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits). Losing
stakes stay in his balance, and the spread between the true odds and the
chalked odds is the house margin. Like every paid machine in the economy
chapter (the [slot machine](001_slot_machine.md) is the smallest), a
bookmaker that cannot cover a payout fails quietly, so seed his balance
before the first race.

## Build it

Each script below is a `'''` multi-line block: open the `@set` line with a
trailing `'''`, write the body as ordinary indented softcode, and close with
a line of just `'''` (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)).

Create Barnum, tag him an NPC, drop him where he can work a crowd, and seed
his credit balance so he can cover a payout.
[`adjust_credits`](../reference/softcode.md#fn-adjust_credits) adds the
float and [`credits`](../reference/softcode.md#fn-credits) reads it back:

```text
@create Bookie Barnum
@tag Bookie Barnum = npc
drop Bookie Barnum
@desc Bookie Barnum = Loud coat, louder voice, a chalkboard of odds and a pocket that eats credits.
@eval m = get('Bookie Barnum'); adjust_credits(m, 1000); result = credits(m)
```

The field and the finish line are plain data. `field` maps each runner to
its odds, which double as its speed, and `distance` is the length of the
track. Write the field as JSON with double quotes, so the store keeps it as
a dictionary rather than a string:

```text
@set Bookie Barnum/field = {"Comet": 2, "Old Thunder": 3, "Rustbucket": 5}
@set Bookie Barnum/distance = 30
```

The `$odds` command chalks the board for whoever asks. It reads the field
with [`V`](../reference/softcode.md#fn-v) (which defaults a missing
attribute) and prints each runner at its price with
[`pemit`](../reference/softcode.md#fn-pemit), which sends privately to the
asker:

```text
@set Bookie Barnum/cmd_odds = '''
$odds:
f = V('field', {})
pemit(enactor, 'The chalkboard:')
for nm, od in sorted(f.items()):
    pemit(enactor, f'  {nm} -- {od}-to-1')
pemit(enactor, 'Pay me your stake, then: back <runner>.')
'''
```

Now the palm. The `ON_PAYMENT` hook reads the stake with `adata('amount')`,
arms it while the track is quiet with
[`set_attr`](../reference/softcode.md#fn-set_attr), and bounces it back with
`transfer_credits` while the field runs. The `if target is me:` guard is the
line to never drop, because the hook fires on every object in the room:

```text
@set Bookie Barnum/on_payment = '''
if target is me:  # ON_PAYMENT fires on EVERY object in the room, so guard it
    paid = adata('amount', 0)
    if paid > 0:
        k = 'stake_' + enactor.id  # per-player key, so two bettors never share a stake
        if not V('running', 0):
            set_attr(me, k, V(k, 0) + paid)
            pemit(enactor, f'Barnum palms your {paid} credits: now back a runner.')
        else:
            transfer_credits(me, enactor, paid)
            pemit(enactor, 'No bets while they run. Your credits, returned.')
'''
```

The `$back` command assigns an armed stake to a runner and starts the
countdown. It matches the runner name case-insensitively with
[`trim`](../reference/softcode.md#fn-trim), records the bet in the `book`
keyed by the bettor's id, clears the armed stake with
[`del_attr`](../reference/softcode.md#fn-del_attr), and announces the bet to
the room with [`remit`](../reference/softcode.md#fn-remit).
[`name`](../reference/softcode.md#fn-name) prints the bettor:

```text
@set Bookie Barnum/cmd_back = '''
$back *:
f = V('field', {})
picks = [nm for nm in f if nm.lower() == trim(arg0).lower()]
k = 'stake_' + enactor.id
st = V(k, 0)
if picks and st > 0 and not V('running', 0):
    runner = picks[0]
    bk = V('book', {})
    bk[enactor.id] = {'runner': runner, 'stake': st, 'name': name(enactor)}
    set_attr(me, 'book', bk)
    del_attr(me, k)  # spend the armed stake
    set_attr(me, 'post', V('post', 3))  # start the post-time countdown
    remit(here, f'{name(enactor)} backs {runner} for {st} at {f[runner]}-to-1.')
else:
    pemit(enactor, 'Pay your stake first, name a runner on the card, and bet before the off.')
'''
```

Attach the ticker and write the dispatcher. `interval:6` fires `on_tick`
every six world beats, and the body picks one of three helpers with
[`eval_attr`](../reference/softcode.md#fn-eval_attr), which runs another of
Barnum's attributes as a subroutine. Because the whole tick chain runs with
Barnum as the executor, `me` inside each helper is still Barnum, so a helper
reads and writes his attributes directly:

```text
@behavior Bookie Barnum = script_ticker, interval:6
@set Bookie Barnum/on_tick = '''
if V('running', 0):
    eval_attr(me, 'stride')
elif V('book', {}):
    eval_attr(me, 'countdown')
'''
```

The countdown helper counts `post` down and, at zero, throws the gate: it
flips `running` on, zeroes every runner's position, and lets the race begin.
[`decr`](../reference/softcode.md#fn-decr) drops the counter by one and
returns the new value:

```text
@set Bookie Barnum/countdown = '''
c = decr('post')
if c <= 0:
    set_attr(me, 'running', 1)
    set_attr(me, 'positions', {nm: 0 for nm in V('field', {})})
    remit(here, 'A bell! They are off!')
else:
    remit(here, f'Barnum bawls: post time in {c}!')
'''
```

The stride helper is the race call. Every runner advances by
`rand(1, 9 - odds)`, the leader is whoever is furthest along, and the first
past `distance` wins and triggers the payout. `eval_attr(me, 'payout', lead)`
passes the winner's name to the payout helper as its `arg0`:

```text
@set Bookie Barnum/stride = '''
f = V('field', {})
pos = V('positions', {})
upd = {}
for nm in pos:
    upd[nm] = pos[nm] + rand(1, 9 - min(f[nm], 7))  # clamp odds so a >=8 nag still gets rand(1, >=2)
set_attr(me, 'positions', upd)
lead = max(upd, key=upd.get)
if upd[lead] >= V('distance', 30):
    remit(here, f'{lead} takes the wire! {lead} wins!')
    eval_attr(me, 'payout', lead)
else:
    remit(here, f'{lead} leads at the {upd[lead]} mark.')
'''
```

The payout helper pays everyone who backed the winner at stake times
(odds + 1), from Barnum's balance, then wipes the race state.
[`get`](../reference/softcode.md#fn-get)`('#' + pid)` turns a stored player
id back into the player object:

```text
@set Bookie Barnum/payout = '''
f = V('field', {})
bk = V('book', {})
for pid, b in bk.items():
    if b['runner'] == arg0:  # arg0 is the winner's name, from the stride helper
        winner = get('#' + pid)
        prize = b['stake'] * (f[arg0] + 1)
        transfer_credits(me, winner, prize)
        pemit(winner, f'Barnum counts out {prize} credits. Pleasure doing business.')
set_attr(me, 'running', 0)
set_attr(me, 'book', {})
del_attr(me, 'positions')
del_attr(me, 'post')
'''
```

## Try it

Give yourself pocket money with `@eval adjust_credits(me, 50)`, then play.
The post-time and stride lines come from the ticker, one per beat; you can
force a beat by hand with `@tr Bookie Barnum/on_tick`. Only the stride lines
vary with the die, and here the roll runs Comet a clean race:

```text
> odds
The chalkboard:
  Comet -- 2-to-1
  Old Thunder -- 3-to-1
  Rustbucket -- 5-to-1
Pay me your stake, then: back <runner>.

> pay 10 to Bookie Barnum
Barnum palms your 10 credits: now back a runner.

> back comet
Bob backs Comet for 10 at 2-to-1.

(then, one line per beat)
Barnum bawls: post time in 2!
Barnum bawls: post time in 1!
A bell! They are off!
Comet leads at the 7 mark.
Comet leads at the 14 mark.
Comet takes the wire! Comet wins!
Barnum counts out 30 credits. Pleasure doing business.

> pay 5 to Bookie Barnum      (while they run)
No bets while they run. Your credits, returned.
```

Back a loser and the stake simply stays in Barnum's balance, which along
with the gap between the true odds and the chalked odds is how he affords
the coat.

## Going further

- **A fair-odds audit:** with speeds `rand(1, 9 - odds)` the favorite wins
  more often than 2-to-1 pays, so Barnum keeps an overround like every real
  book. Retune `field` and force a few hundred races with
  `@tr Bookie Barnum/on_tick` in a loop to measure it.
- **Race cards:** rotate `field` from a `cards` list each time the payout
  helper clears the book, so every night runs a fresh program, all data.
- **The photo finish:** when two runners pass `distance` on the same beat,
  the sort winner takes it as written; split the payout across
  `[nm for nm in upd if upd[nm] >= V('distance', 30)]` for a dead heat.
- **Announce zone-wide:** swap the `remit` calls for
  [`act`](../reference/softcode.md#fn-act)`(here, ..., targeting='zone')` so
  the whole fairground hears the call, the same trick the
  [slot machine](001_slot_machine.md) uses for a jackpot.
