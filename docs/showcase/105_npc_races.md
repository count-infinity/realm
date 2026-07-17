# 105. NPC Races & Betting

> Checklist item 105 — [now] — *on_tick simulation, odds attrs, betting-book objects*

**What you'll build:** Bookie Barnum, who chalks odds on a three-runner
field, takes stakes through his palm (`pay`), pencils bets into a book,
counts down to post time, calls the race tick by tick, and pays winners
at their odds.

**Concepts:** a ticker-driven simulation (`script_ticker` + `on_tick`
as the race clock), odds as data an economy designer can retune, the
two-step betting book (`ON_PAYMENT` arms a stake, `$back` assigns it),
a seeded float so the book can always pay, and `eval_attr()` helpers
splitting one NPC's brain into readable pieces.

## How it works

**The race is the ticker.** Barnum's `on_tick` does one of three
things: nothing (no bets), count down to post (bets are in), or run one
stride of the race. Each stride advances every runner by
`rand(1, 9 - odds)` — the odds attribute *is* the speed model, so a
2-to-1 favorite strides up to 7 while the 5-to-1 nag manages 4, and the
payout price and the win probability come from the same number. First
past `distance` wins on the spot.

**Betting is two steps, both consensual.** `pay 10 to Bookie Barnum`
fires `ON_PAYMENT`; the ledger idiom ([item 1](001_slot_machine.md))
banks it as your *armed stake* — money in Barnum's pocket, not yet on a
runner. `back Comet` moves the stake into the `book` keyed by your id.
Payments while the field is running bounce straight back: no
past-posting. The book, the field, the positions — all attributes;
`@examine Bookie Barnum` is the stewards' inquiry.

**Winners are paid stake × (odds + 1)** — stake back plus odds — from
Barnum's float. Losing stakes stay in his pocket; the float and the
odds spread are the house's margin, and like every machine in the
economy chapter, a bookmaker that can't cover the payout fails
silently — seed the float first.

## Build it

The bookmaker, his float (note the ledger init — the float must not
read as a giant first bet), and the card:

```text
@create Bookie Barnum
@tag Bookie Barnum = npc
drop Bookie Barnum
@desc Bookie Barnum = Loud coat, louder voice, a chalkboard of odds and a pocket that eats credits.
@eval m = get('Bookie Barnum'); adjust_credits(m, 1000); set_attr(m, 'ledger', credits(m)); result = credits(m)
@set Bookie Barnum/field = {"Comet": 2, "Old Thunder": 3, "Rustbucket": 5}
@set Bookie Barnum/distance = 30
@set Bookie Barnum/cmd_odds = $odds: f = V('field', {}); pemit(enactor, 'The chalkboard:'); [pemit(enactor, f'  {nm} -- {od}-to-1') for nm, od in sorted(f.items())]; pemit(enactor, 'Pay me your stake, then: back <runner>.')
```

The palm — stakes armed while the track is quiet, bounced while it
runs:

```text
@set Bookie Barnum/on_payment = paid = credits(me) - V('ledger', 0); ok = not V('running', 0) and paid > 0; k = 'stake_' + enactor.id; (set_attr(me, k, V(k, 0) + paid), pemit(enactor, 'Barnum palms your ' + str(paid) + ' credits: now back a runner.')) if ok else (transfer_credits(me, enactor, paid), pemit(enactor, 'No bets while they run. Your credits, returned.')) if paid > 0 else None; set_attr(me, 'ledger', credits(me))
```

The book — assigning your armed stake starts the post-time countdown:

```text
@set Bookie Barnum/cmd_back = $back *: f = V('field', {}); pickl = [nm for nm in f if nm.lower() == trim(arg0).lower()]; k = 'stake_' + enactor.id; st = V(k, 0); ok = bool(pickl) and st > 0 and not V('running', 0); bk = V('book', {}); [(bk.update({enactor.id: {'runner': pickl[0], 'stake': st, 'name': name(enactor)}}), set_attr(me, 'book', bk), del_attr(me, k), set_attr(me, 'post', V('post', 3)), remit(here, f'{name(enactor)} backs {pickl[0]} for {st} at {f[pickl[0]]}-to-1.')) for g in [ok] if g]; pemit(enactor, 'Pay your stake first, name a runner on the card, and bet before the off.') if not ok else None
```

The clock, split into helpers. The dispatcher:

```text
@behavior Bookie Barnum = script_ticker, interval:6
@set Bookie Barnum/on_tick = eval_attr(me, 'stride') if V('running', 0) else (eval_attr(me, 'countdown') if V('book', {}) else None)
```

Post time:

```text
@set Bookie Barnum/countdown = c = decr('post'); (set_attr(me, 'running', 1), set_attr(me, 'positions', {nm: 0 for nm in V('field', {})}), remit(here, 'A bell! They are off!')) if c <= 0 else remit(here, f'Barnum bawls: post time in {c}!'); result = 1
```

The race call — every runner strides, the leader gets the line, the
wire ends it:

```text
@set Bookie Barnum/stride = f = V('field', {}); pos = V('positions', {}); upd = {nm: pos[nm] + rand(1, 9 - min(f[nm], 7)) for nm in pos}; set_attr(me, 'positions', upd); lead = max(upd, key=upd.get); dist = V('distance', 30); (remit(here, f'{lead} takes the wire! {lead} wins!'), eval_attr(me, 'payout', lead)) if upd[lead] >= dist else remit(here, f'{lead} leads at the {upd[lead]} mark.'); result = 1
```

Settlement — winners at odds+1, the book wiped, the ledger re-synced:

```text
@set Bookie Barnum/payout = f = V('field', {}); bk = V('book', {}); [(transfer_credits(me, get('#' + pid), b['stake'] * (f[arg0] + 1)), pemit(get('#' + pid), f'Barnum counts out {b["stake"] * (f[arg0] + 1)} credits. Pleasure doing business.')) for pid, b in bk.items() if b['runner'] == arg0]; set_attr(me, 'running', 0); set_attr(me, 'book', {}); del_attr(me, 'positions'); del_attr(me, 'post'); set_attr(me, 'ledger', credits(me)); result = 1
```

## Try it

```text
odds                        -> the chalkboard: Comet 2-to-1, Old Thunder 3-to-1, Rustbucket 5-to-1
pay 10 to Bookie Barnum     -> "Barnum palms your 10 credits: now back a runner."
back comet                  -> "Kess backs Comet for 10 at 2-to-1."
                            ... "post time in 2!" ... "post time in 1!" ... "A bell! They are off!"
                            ... "Comet leads at the 7 mark." ... stride by stride ...
                            -> "Comet takes the wire! Comet wins!"
                            -> "Barnum counts out 30 credits. Pleasure doing business."
pay 10 to Bookie Barnum     (mid-race) -> "No bets while they run. Your credits, returned."
```

Back a loser and the stake simply stays in Barnum's pocket — that, and
the gap between true odds and chalked odds, is how he affords the coat.

## Going further

- **A fair-odds audit:** with speeds `rand(1, 9 - odds)`, the favorite
  wins more often than 2-to-1 pays — Barnum keeps an overround, like
  every real book. Retune `field` and rerun a few hundred races
  (`@tr Bookie Barnum/on_tick` in a loop) to measure it.
- **Race cards:** rotate `field` from a `cards` list each time `payout`
  clears the book — nightly programs, data only.
- **The photo finish:** two runners past `distance` on the same tick —
  currently the sort winner takes it; split payouts across
  `[nm for nm in upd if upd[nm] >= dist]` for dead heats.
- **Announce zone-wide:** swap the `remit` calls for `act(here, ...,
  targeting='zone')` so the whole fairground hears the call — the
  [slot machine](001_slot_machine.md)'s jackpot trick.

**~~Engine gaps~~ — FIXED 2026-07-17.** The leader is found with
`max(upd, key=upd.get)` — a bound method — rather than the more direct
`sorted(upd, key=lambda nm: -upd[nm])`, because a `lambda` closing over the
script-local `upd` used to `NameError`: scripts exec'd with split
`globals`/`locals`, so lambdas and generator expressions couldn't see script
locals. Scripts now share one namespace and the `lambda` form works. The
bound-method version below is left as written and remains perfectly good
style (full note on item 100).
