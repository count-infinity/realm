# 100. Poker Table

> Checklist item 100 — [now] — *sandboxed-Python state machines, prompt() turns, hidden info*

**What you'll build:** A five-card showdown poker table for two or more
players: sit, deal, bet real credits into a pot, fold or call, and
reveal — with a hand evaluator that ranks pairs through four-of-a-kind
and splits ties.

**Concepts:** a phase state machine in attributes (`lobby` → `betting`
→ back to `lobby`), `ON_PAYMENT` as the *only* way money enters the pot,
secret hands (the [card deck](099_card_deck.md) pattern), a hand-scoring
helper via `eval_attr()`, and settlement that conserves every credit.

## How it works

**The phase machine.** One `phase` attribute governs which verbs work:
`$sit` and `$deal cards` only in `lobby`; paying, `$fold` and
`$showdown` only in `betting`. Every verb re-derives its guard from
attributes, so the machine survives reboots and never trusts the
caller.

**Money moves by consent.** Bets aren't a verb argument — they're real
payments. `pay 10 to the poker table` fires `ON_PAYMENT` with the payer
as `enactor`, the payee as `target`, and the stake as `adata('amount')`;
the hook adds it to your `bets` entry and the `pot`, and *refunds anyone
who isn't in the hand*. Raising is just paying more. The table can pay
winners out
(`transfer_credits(me, ...)` — its own balance) but can never reach
into a pocket; that asymmetry is the house's honesty, enforced.

**Betting round, minimal but real.** Showdown is refused until every
un-folded player's stake matches (and is above zero) — so a raise
forces calls or folds, which is the whole game. Folding down to one
player settles immediately.

**The evaluator.** A `score` helper turns five cards into a comparable
list: count copies of each rank, read the *shape* of the counts
(`[4,1]` = quads, `[3,2]` = full house, `[2,2,1]` = two pair...), then
tie-break by rank, grouped-first — `sorted(vs, key=lambda v: (n[v], v),
reverse=True)`, "most copies first, then highest rank", which is exactly
how a player reads their own hand. Comparing two scores is just Python
list comparison — `max()` finds the winner, equality splits the pot.
Straights and flushes are left as an exercise (see Going further); the
shape trick carries every pair-based hand.

## Build it

The table, with the pot on public display:

```text
@create the poker table
drop the poker table
@desc the poker table = Green felt, chip rails, a shaded lamp. [[result = 'The pot holds ' + str(V('pot', 0)) + ' credits.']]
@set the poker table/hands = {}
@attr the poker table/hands = secret
```

Seating (lobby only, no double-sitting):

```text
@set the poker table/cmd_sit = $sit: p = V('players', []); n = V('names', {}); ok = V('phase', 'lobby') == 'lobby' and enactor.id not in p; [(set_attr(me, 'players', p + [enactor.id]), n.update({enactor.id: name(enactor)}), set_attr(me, 'names', n), remit(here, name(enactor) + ' takes a seat at the poker table.')) for g in [ok] if g]; pemit(enactor, 'You are in. Someone type: deal cards.' if ok else 'No seat for you -- a hand is in play, or you are already seated.')
```

The deal — build a deck, shuffle it, five cards each, whispered:

```text
@set the poker table/cmd_deal = $deal cards: p = V('players', []); ok = V('phase', 'lobby') == 'lobby' and enactor.id in p and len(p) >= 2; d = [r + s for s in ['s', 'h', 'd', 'c'] for r in ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']]; sh = [d.pop(rand(0, len(d) - 1)) for i in range(len(d))]; [(set_attr(me, 'hands', {pid: sh[i * 5:i * 5 + 5] for i, pid in enumerate(p)}), set_attr(me, 'bets', {pid: 0 for pid in p}), set_attr(me, 'folded', []), set_attr(me, 'phase', 'betting'), remit(here, 'Five cards apiece, face down. Betting is open: pay the table to bet, fold to quit, showdown when stakes match.'), [pemit(get('#' + pid), 'Your hand: ' + ' '.join(sh[i * 5:i * 5 + 5])) for i, pid in enumerate(p)]) for g in [ok] if g]; pemit(enactor, 'Take a seat first, find an opponent, or finish the current hand.') if not ok else None
```

The till — bets in, strangers refunded:

```text
@set the poker table/on_payment = paid = adata('amount', 0) if target == me else 0; b = V('bets', {}); live = paid > 0 and V('phase', 'lobby') == 'betting' and enactor.id in b and enactor.id not in V('folded', []); [(b.update({enactor.id: b[enactor.id] + paid}), set_attr(me, 'bets', b), set_attr(me, 'pot', V('pot', 0) + paid), remit(here, name(enactor) + ' pushes ' + str(paid) + ' into the pot -- staked ' + str(b[enactor.id]) + ' this hand.')) for g in [live] if g]; (transfer_credits(me, enactor, paid), pemit(enactor, 'The table returns your credits: no hand in play for you.')) if not live and paid > 0 else None
```

Two things in that first clause are load-bearing.

`adata('amount', 0)` replaces the **till idiom** from
[item 1](001_slot_machine.md), which this hook used to carry: open with
`paid = credits(me) - V('ledger', 0)`, close with `set_attr(me,
'ledger', credits(me))`, and infer each payment from the change in your
own balance, because the hook could not see the amount. A till only
stays accurate if *every* path that moves the table's money remembers to
re-sync it — one forgotten re-sync in `settle` and the next player's bet
reads as a refund.

`if target == me` is what makes it safe. `ON_PAYMENT` is a *witnessed*
event: it fires on every object in the room, so paying the bartender
next to the table fires the table's hook too. `enactor` is who paid;
`target` is who was **paid**. Without that test, `adata('amount')` hands
this table the bartender's money — and a seated player buying a drink
would find their tab quietly staked. (The till idiom was immune by
accident: a neighbour's payment moved none of the table's credits, so
the delta was 0.) [Item 108](108_casino_floor.md) has the full note; the
rule is that every payment hook opens with the guard.

Folding — and the last player standing takes it without showing:

```text
@set the poker table/cmd_fold = $fold: f = V('folded', []); p = V('players', []); ok = V('phase') == 'betting' and enactor.id in p and enactor.id not in f; f2 = f + [enactor.id]; live = [pid for pid in p if pid not in f2]; [(set_attr(me, 'folded', f2), remit(here, name(enactor) + ' folds.')) for g in [ok] if g]; eval_attr(me, 'settle', ' '.join(live)) if ok and len(live) == 1 else None
```

The evaluator and its narrator:

```text
@set the poker table/score = cs = arg0.split(); vs = sorted([member(c[:-1], '2 3 4 5 6 7 8 9 10 J Q K A') for c in cs], reverse=True); n = {v: vs.count(v) for v in vs}; shape = sorted(n.values(), reverse=True); cat = 7 if shape[0] == 4 else (6 if shape == [3, 2] else (3 if shape[0] == 3 else (2 if shape[:2] == [2, 2] else (1 if shape[0] == 2 else 0)))); result = [cat] + sorted(vs, key=lambda v: (n[v], v), reverse=True)
@set the poker table/catname = result = switch(int(arg0), 7, 'four of a kind', 6, 'a full house', 3, 'three of a kind', 2, 'two pair', 1, 'a pair', 'high card')
```

Showdown — guard, reveal every live hand, crown the best score:

```text
@set the poker table/cmd_showdown = $showdown: p = V('players', []); f = V('folded', []); b = V('bets', {}); live = [pid for pid in p if pid not in f]; h = V('hands', {}); n = V('names', {}); ok = V('phase') == 'betting' and enactor.id in live and len(set(b[pid] for pid in live)) == 1 and b[live[0]] > 0; sc = {pid: eval_attr(me, 'score', ' '.join(h[pid])) for pid in live} if ok else {}; best = max(sc.values()) if ok else None; w = [pid for pid in live if sc[pid] == best] if ok else []; [remit(here, n.get(pid, '?') + ' shows ' + ' '.join(h[pid]) + ' -- ' + eval_attr(me, 'catname', str(sc[pid][0])) + '.') for g in [ok] if g for pid in live]; eval_attr(me, 'settle', ' '.join(w)) if ok else pemit(enactor, 'Not yet -- betting still open (all live stakes must match and be above zero).')
```

Settlement — split the pot among the winner ids it's handed, then reset
the machine. An odd chip that won't split stays on the felt for the next
pot:

```text
@set the poker table/settle = w = arg0.split(); pot = V('pot', 0); share = pot // len(w); n = V('names', {}); [transfer_credits(me, get('#' + pid), share) for pid in w]; remit(here, 'The pot -- ' + str(pot) + ' credits -- goes to ' + ', '.join(n.get(pid, '?') for pid in w) + '.'); set_attr(me, 'pot', pot - share * len(w)); set_attr(me, 'phase', 'lobby'); set_attr(me, 'players', []); set_attr(me, 'hands', {}); result = 1
```

## Try it

Three players, each with pocket money (`@eval adjust_credits(me, 100)`):

```text
sit                           (all three)
deal cards                    -> five cards whispered to each
pay 10 to the poker table     -> "Kess pushes 10 into the pot -- staked 10 this hand."
pay 10 to the poker table     (second player)
pay 10 to the poker table     (third player)
fold                          (third player thinks better of it)
showdown                      -> both live hands hit the felt, best shape wins 30
```

A raise: pay again before showdown — now the others must match your
total or fold; `showdown` refuses while stakes differ. Hole cards are
engine-private: `@eval result = get_attr(get('the poker table'),
'hands')` reads `None` for anyone but the table's owner.

## Going further

- **Ante up:** have `$deal cards` refuse until every seated player's
  `bets` entry is at least the `ante` attribute — paid before the deal.
- **Straights and flushes:** extend `score` — `flush = len(set(c[-1]
  for c in cs)) == 1`, `run = vs == list(range(vs[0], vs[0] - 5, -1))`
  — and slot categories 4, 5, 8 into the `cat` ladder.
- **Draw poker:** between deal and showdown, a `$draw <cards>` verb
  that mucks named cards and deals replacements — the deck remainder is
  still sitting in the dealt order.
- **A dealer NPC:** move `$deal cards` onto a croupier with a
  `script_ticker` that opens a fresh hand whenever the lobby has two
  seated players — the [casino floor](108_casino_floor.md) seats one.

**~~Engine gaps~~ — FIXED 2026-07-17.** This tutorial was written around a
sandbox sharp edge that no longer exists. Scripts used to run under
`exec(code, globals, locals)` with *separate* dicts, which meant
generator expressions and `lambda`s resolved free names against
`globals` and raised `NameError` on any script-local: `set(b[pid] for
pid in live)` failed where `set([b[pid] for pid in live])` worked, and
`sorted(vs, key=lambda v: (n[v], v))` failed where
`sorted([[n[v], v] for v in vs])` worked. Scripts now share **one**
namespace, so genexprs and lambdas read script locals like any other
Python; the build above uses the direct forms, and the tie-break in
`score` is the one that reads most differently for it. The
`[...]`-wrapped versions are still correct if you meet them in older
builds — they were never wrong, only forced.

Two shapes above are *not* scoping workarounds and are staying:
`[(...) for g in [ok] if g]` is how a one-line script runs a block only
when a guard holds (there is no `if` statement in an attribute), and
`max(d, key=d.get)` is simply good style.
