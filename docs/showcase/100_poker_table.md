# 100. Poker Table

> Checklist item 100 ([now]): *sandboxed-Python state machines, prompt() turns, hidden info*

**What you'll build:** a five-card showdown poker table for two or more
players. Players sit, deal, bet real credits into a pot, fold or call, and
reveal, with a hand evaluator that ranks pairs through four-of-a-kind and
splits ties.

**Concepts:** a phase state machine held in attributes (`lobby` to `betting`
and back), [`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks) as the only
way money enters the pot, secret hands built on the
[card deck](099_card_deck.md) pattern, a hand-scoring helper run through
[`eval_attr`](../reference/softcode.md#fn-eval_attr), and settlement that
conserves every credit.

## How it works

The finished table is one dropped object that holds the whole game: the seated
players and the current phase as data, each player's hidden hand in a
[`secret`](099_card_deck.md)-flagged attribute, and the pot in the table's own
credit balance. Builders type a handful of verbs at it, players pay it to bet,
and the same object settles the hand and resets itself. This section answers
three questions in turn: how one attribute decides which verb works, why money
can only arrive as a real payment, and how five cards become a comparable score.

### How does one attribute run the whole game?

A single `phase` attribute governs which verbs do anything. `$sit` and
`$deal cards` act only while `phase` is `lobby`; betting, `$fold`, and
`$showdown` act only while it is `betting`. Every verb re-derives its own guard
from attributes rather than trusting the caller, so the machine survives a
reboot and cannot be driven out of order. Each of these verbs is a
`$`-command, which fires only on the table it is set on, so none of them needs
a [`target`](../reference/softcode.md#guard-on-target) guard.

### Why is a bet a payment and not an argument?

A bet is not a verb argument, it is a real payment. `pay 10 to the poker table`
propagates an `event:payment` action and runs the table's
[`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks) hook with the payer as
`enactor`, the payee as `target`, and the stake carried in the action as
[`adata('amount')`](../reference/softcode.md#event-data-namespace). The hook
adds the stake to the payer's `bets` entry and to the pot, and it refunds
anyone who is not in the hand. Raising is simply paying more.

Money moving in this direction is deliberate. A script runs with its object's
authority, so the table can pay a winner out of its own balance with
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits)`(me, ...)`,
but it can never reach into a player's wallet. That asymmetry is the house's
honesty, and the engine enforces it. Showdown is refused until every un-folded
player's stake matches and is above zero, so a raise forces the others to call
or fold, which is the whole game. Folding down to one player settles at once.

Unlike a `$`-command, `ON_PAYMENT` is a reaction to an action aimed elsewhere,
so it fires on every object in the room. The hook therefore opens with the
[`target` guard](../reference/softcode.md#guard-on-target), the one that bites,
covered where it is set below.

### How do five cards become a score?

A `score` helper turns five cards into one comparable list. It counts how many
copies of each rank the hand holds, reads the *shape* of those counts (`[4, 1]`
is four of a kind, `[3, 2]` is a full house, `[2, 2, 1]` is two pair), and then
tie-breaks by rank, most-copies-first: `sorted(vs, key=lambda v: (n[v], v),
reverse=True)` reads as "the pair before the kickers, high card first", which is
exactly how a player reads their own hand. Comparing two hands is then ordinary
Python list comparison, so `max()` finds the winner and equality splits the pot.
Straights and flushes are left as an exercise (see Going further); the shape
trick carries every pair-based hand.

## Build it

Create the table, drop it in the room, and give it a description whose
[`[[...]]`](../reference/softcode.md#fn-v) block reads the pot fresh on every
look, so the felt always shows the true stake:

```text
@create the poker table
drop the poker table
@desc the poker table = Green felt, chip rails, a shaded lamp. [[result = 'The pot holds ' + str(V('pot', 0)) + ' credits.']]
```

Seal the hands ledger before a single card moves. The
[`secret`](099_card_deck.md) flag makes the attribute read back as `None` for
everyone but the table's controllers, while the table's own scripts, which run
as the table, keep full access:

```text
@set the poker table/hands = {}
@attr the poker table/hands = secret
```

`$sit` seats a player, but only during the lobby and only once. It appends the
player id to `players` and records the display name in `names`, so later
announcements can print a name without re-resolving an id:

```text
@set the poker table/cmd_sit = '''
$sit:
p = V('players', [])
n = V('names', {})
if V('phase', 'lobby') == 'lobby' and enactor.id not in p:
    set_attr(me, 'players', p + [enactor.id])
    n[enactor.id] = name(enactor)   # remember the name; ids are what we store
    set_attr(me, 'names', n)
    remit(here, name(enactor) + ' takes a seat at the poker table.')
    pemit(enactor, 'You are in. Someone type: deal cards.')
else:
    pemit(enactor, 'No seat for you: a hand is in play, or you are already seated.')
'''
```

`$deal cards` opens a hand once two or more players are seated. It builds a
52-card deck with a comprehension, draws it into a shuffled order with
[`rand`](../reference/softcode.md#fn-rand), deals five to each seat, resets the
per-hand state, and flips `phase` to `betting`. Each hand is whispered to its
owner alone with [`pemit`](../reference/softcode.md#fn-pemit) to
[`get`](../reference/softcode.md#fn-get)`('#' + pid)`, the object behind the
stored id, so the room never sees the faces:

```text
@set the poker table/cmd_deal = '''
$deal cards:
p = V('players', [])
if V('phase', 'lobby') == 'lobby' and enactor.id in p and len(p) >= 2:
    d = [r + s for s in ['s', 'h', 'd', 'c'] for r in ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']]
    sh = [d.pop(rand(0, len(d) - 1)) for i in range(len(d))]   # draw into a new order
    set_attr(me, 'hands', {pid: sh[i * 5:i * 5 + 5] for i, pid in enumerate(p)})
    set_attr(me, 'bets', {pid: 0 for pid in p})
    set_attr(me, 'folded', [])
    set_attr(me, 'phase', 'betting')
    remit(here, 'Five cards apiece, face down. Betting is open: pay the table to bet, fold to quit, showdown when stakes match.')
    for i, pid in enumerate(p):
        pemit(get('#' + pid), 'Your hand: ' + ' '.join(sh[i * 5:i * 5 + 5]))   # whispered to that seat only
else:
    pemit(enactor, 'Take a seat first, find an opponent, or finish the current hand.')
'''
```

The till takes bets in and sends strangers' money back. Because `ON_PAYMENT`
fires on every object in the room, the whole body sits under `if target is me`,
so a seated player buying a drink from a bartender next to the table does not
stake it by accident. The stake is read straight off the action with
[`adata`](../reference/softcode.md#event-data-namespace); a payment from someone
who is not in the hand is returned with
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits):

```text
@set the poker table/on_payment = '''
if target is me:   # ON_PAYMENT fires on EVERY object in the room, so guard it
    paid = adata('amount', 0)
    b = V('bets', {})
    live = paid > 0 and V('phase', 'lobby') == 'betting' and enactor.id in b and enactor.id not in V('folded', [])
    if live:
        b[enactor.id] = b[enactor.id] + paid
        set_attr(me, 'bets', b)
        set_attr(me, 'pot', V('pot', 0) + paid)
        remit(here, name(enactor) + ' pushes ' + str(paid) + ' into the pot -- staked ' + str(b[enactor.id]) + ' this hand.')
    elif paid > 0:
        transfer_credits(me, enactor, paid)   # the table pays only from its OWN balance
        pemit(enactor, 'The table returns your credits: no hand in play for you.')
'''
```

That guard is what makes the till safe. `enactor` is who paid and `target` is
who was paid, so without `if target is me` the hook would read a neighbouring
payment's `amount` and stake it against this table. The
[casino floor](108_casino_floor.md) puts several payables in one room and shows
the same failure at full scale; the rule is that every payment hook opens with
the guard.

`$fold` drops a player out of the hand, and if only one player is left it hands
the pot straight to them through the `settle` helper, no cards shown:

```text
@set the poker table/cmd_fold = '''
$fold:
f = V('folded', [])
p = V('players', [])
if V('phase') == 'betting' and enactor.id in p and enactor.id not in f:
    f = f + [enactor.id]
    set_attr(me, 'folded', f)
    remit(here, name(enactor) + ' folds.')
    live = [pid for pid in p if pid not in f]
    if len(live) == 1:
        eval_attr(me, 'settle', ' '.join(live))
'''
```

The evaluator scores a hand and its narrator names the category. `score` counts
rank copies with [`member`](../reference/softcode.md#fn-member) mapping each card
to a comparable rank value, then folds shape and kickers into one list; the
one-line `catname` maps a category number to English with
[`switch`](../reference/softcode.md#fn-switch):

```text
@set the poker table/score = '''
cs = arg0.split()
vs = sorted([member(c[:-1], '2 3 4 5 6 7 8 9 10 J Q K A') for c in cs], reverse=True)
n = {v: vs.count(v) for v in vs}
shape = sorted(n.values(), reverse=True)
cat = 7 if shape[0] == 4 else (6 if shape == [3, 2] else (3 if shape[0] == 3 else (2 if shape[:2] == [2, 2] else (1 if shape[0] == 2 else 0))))
result = [cat] + sorted(vs, key=lambda v: (n[v], v), reverse=True)
'''
@set the poker table/catname = result = switch(int(arg0), 7, 'four of a kind', 6, 'a full house', 3, 'three of a kind', 2, 'two pair', 1, 'a pair', 'high card')
```

`$showdown` reveals every live hand and crowns the best score. It refuses
unless the caller is still in the hand and every live stake matches and is above
zero, scores each hand with [`eval_attr`](../reference/softcode.md#fn-eval_attr),
finds the winner list with `max()`, announces the reveal, and hands the winners
to `settle`:

```text
@set the poker table/cmd_showdown = '''
$showdown:
p = V('players', [])
f = V('folded', [])
b = V('bets', {})
live = [pid for pid in p if pid not in f]
h = V('hands', {})
n = V('names', {})
ok = V('phase') == 'betting' and enactor.id in live and len(set(b[pid] for pid in live)) == 1 and b[live[0]] > 0
if ok:
    sc = {pid: eval_attr(me, 'score', ' '.join(h[pid])) for pid in live}
    best = max(sc.values())
    w = [pid for pid in live if sc[pid] == best]   # a list, so ties can split
    for pid in live:
        remit(here, n.get(pid, '?') + ' shows ' + ' '.join(h[pid]) + ' -- ' + eval_attr(me, 'catname', str(sc[pid][0])) + '.')
    eval_attr(me, 'settle', ' '.join(w))
else:
    pemit(enactor, 'Not yet -- betting still open (all live stakes must match and be above zero).')
'''
```

`settle` is the gavel, a helper that takes the space-separated winner ids. It
splits the pot evenly, pays each winner from the table's balance, announces the
result, and resets the machine to `lobby`. An odd chip that will not divide
stays on the felt for the next pot:

```text
@set the poker table/settle = '''
w = arg0.split()
pot = V('pot', 0)
share = pot // len(w)   # integer split; the remainder stays on the felt
n = V('names', {})
for pid in w:
    transfer_credits(me, get('#' + pid), share)
remit(here, 'The pot -- ' + str(pot) + ' credits -- goes to ' + ', '.join(n.get(pid, '?') for pid in w) + '.')
set_attr(me, 'pot', pot - share * len(w))
set_attr(me, 'phase', 'lobby')
set_attr(me, 'players', [])
set_attr(me, 'hands', {})
result = 1
'''
```

## Try it

Three players, each with pocket money (`@eval adjust_credits(me, 100)`):

```text
> sit                           (all three)
You are in. Someone type: deal cards.

> deal cards
Five cards apiece, face down. Betting is open: pay the table to bet, fold to quit, showdown when stakes match.
Your hand: 7h Kd 2s As 9c     (whispered to that seat only)

> pay 10 to the poker table
Kess pushes 10 into the pot -- staked 10 this hand.

> pay 10 to the poker table     (second player)
> pay 10 to the poker table     (third player)

> fold                          (third player thinks better of it)
Bob folds.

> showdown
Kess shows Ah As 2c 5d 9h -- a pair.
Bob shows Kh Qs 9c 5s 2d -- high card.
The pot -- 20 credits -- goes to Kess.
```

The dealt hand line varies with the shuffle, and only the seat it was dealt to
sees it. To raise, pay again before the showdown: the others must then match
your total or fold, and `showdown` refuses while stakes differ. Hole cards are
engine-private, so
`@eval result = get_attr(get('the poker table'), 'hands')` reads `None` for
anyone but the table's owner.

## Going further

- **Ante up:** have `$deal cards` refuse until every seated player's `bets`
  entry is at least an `ante` attribute, paid before the deal.
- **Straights and flushes:** extend `score` with
  `flush = len(set(c[-1] for c in cs)) == 1` and
  `run = vs == list(range(vs[0], vs[0] - 5, -1))`, then slot categories 4, 5,
  and 8 into the `cat` ladder.
- **Draw poker:** between the deal and the showdown, add a `$draw <cards>` verb
  that mucks named cards and deals replacements, since the deck remainder is
  still sitting in the dealt order.
- **A dealer NPC:** move `$deal cards` onto a croupier with a `script_ticker`
  that opens a fresh hand whenever the lobby has two seated players; the
  [casino floor](108_casino_floor.md) seats one.
