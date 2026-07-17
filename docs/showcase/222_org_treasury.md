# 222. Org treasury & storage

> Checklist item 222 — [now] — *shared bank on the org master, rank-gated withdrawals, rank-sealed lockers via on_check wards*

**What you'll build:** money and storage for the Void Runners crew from
[221](221_organizations.md). Any member pays into a shared treasury; only
officers draw from it. Two footlockers stand in the clubhouse, each sealed
to a rank — a Recruit can open the common locker, but the officers' safe
stays shut for anyone below Officer.

**Concepts:** a **shared vault** as credits on the org master
(the [bank](087_bank_accounts.md) reserve idea, one account for the whole
crew); **rank-gated** deposit/withdraw verbs reading the ladder from 221;
a capped audit log; and **rank-sealed containers** — the
[locked chest](015_locked_chest.md)'s `on_check` gate, but keyed to org
rank instead of a physical key.

## How it works

**The treasury is the crew's wallet.** Instead of per-player accounts
like the [bank](087_bank_accounts.md), the whole crew shares one balance:
the credits sitting on the master object itself. `treasury deposit`
transfers wallet credits onto the master; `treasury withdraw` transfers
them back. Because the money physically lives on the master, the vault
never promises more than it holds — no minting faucet here, just crew
funds moving in and out.

**Rank gates the money, exactly as it gated the roster.** Deposit asks
only that you're a member (rank ≥ 1) — anyone can chip in. Withdraw
demands Officer (rank ≥ 2), read from the same `rank_<id>` ladder built in
221. This is the [organization](221_organizations.md) authority boundary
carried into the economy: the master's admin ownership lets it *hold and
move* the credits, but *who may move them* is pure rank, checked in the
verb.

**Lockers are rank-sealed containers.** Each footlocker is an ordinary
closed [container](014_basic_container.md) with an `on_check` ward on the
`item:on_open` event — the same gate the [gift box](012_gift_box.md) and
[airlock](032_airlock.md) use. Instead of checking a key or a recipient
id, the ward reads the opener's org rank off the Void Runners master and
`block`s the open if it's below the locker's `min_rank`. Set `min_rank` to
1 for a common locker, 2 for the officers' safe — one attribute is the
whole access tier.

## Build it

*(Continues from [221](221_organizations.md) — the Void Runners master and
clubhouse already exist.)* First the treasury: a capped log routine, the
statement verb, and the two gated money verbs:

```text
@teleport The Void Runners Clubhouse
@set the Void Runners/log_row = set_attr(me, 'tlog', (V('tlog', []) + [arg0])[-10:]); result = 1
@set the Void Runners/cmd_treasury = $treasury:pemit(enactor, 'Void Runners treasury: ' + str(credits(me)) + ' credits.'); [pemit(enactor, '  ' + r) for r in V('tlog', [])]
@set the Void Runners/cmd_deposit = $treasury deposit *:amt = int(arg0) if trim(arg0).isdigit() else 0; ok = V('rank_' + enactor.id, 0) >= 1 and amt > 0 and transfer_credits(enactor, me, amt); [(eval_attr(me, 'log_row', name(enactor) + ' deposited ' + str(a)), pemit(enactor, 'Deposited ' + str(a) + ' credits.'), remit(here, name(enactor) + ' pays ' + str(a) + ' credits into the crew treasury.')) for g, a in [[ok, amt]] if g]; pemit(enactor, 'Members only, and your wallet must cover it.') if not ok else None
@set the Void Runners/cmd_withdraw = $treasury withdraw *:amt = int(arg0) if trim(arg0).isdigit() else 0; ok = V('rank_' + enactor.id, 0) >= 2 and amt > 0 and amt <= credits(me) and transfer_credits(me, enactor, amt); [(eval_attr(me, 'log_row', name(enactor) + ' withdrew ' + str(a)), pemit(enactor, 'Withdrew ' + str(a) + ' credits.'), remit(here, name(enactor) + ' draws ' + str(a) + ' credits from the crew treasury.')) for g, a in [[ok, amt]] if g]; pemit(enactor, 'Officers only, and the treasury must cover it.') if not ok else None
```

Now the two lockers — closed containers, each with a rank ward on
`item:on_open`. The common footlocker admits any member; the officers'
safe demands rank 2:

```text
@create the crew footlocker
@set the crew footlocker/container = true
drop the crew footlocker
@set the crew footlocker/min_rank = 1
close the crew footlocker
@set the crew footlocker/on_check = org = get('the Void Runners'); block('The footlocker is sealed to Void Runners members.') if atype == 'item:on_open' and target == me and get_attr(org, 'rank_' + actor.id, 0) < V('min_rank', 1) else None
@create the officers safe
@set the officers safe/container = true
drop the officers safe
@set the officers safe/min_rank = 2
close the officers safe
@set the officers safe/on_check = org = get('the Void Runners'); block('The officers safe reads your crew rank and stays shut. Officers only.') if atype == 'item:on_open' and target == me and get_attr(org, 'rank_' + actor.id, 0) < V('min_rank', 2) else None
```

## Try it

With Vala (Commander) and Bob (Recruit) from 221, fund the crew and prove
the gates. Bob can pay in but not draw out:

```text
(Bob)  treasury deposit 40   -> Deposited 40 credits.
(Bob)  treasury withdraw 10  -> Officers only, and the treasury must cover it.
(Vala) treasury withdraw 10  -> Withdrew 10 credits.
treasury
   Void Runners treasury: 30 credits.
     Bob deposited 40
     Vala withdrew 10
```

The lockers read rank the same way. Bob opens the common footlocker but
bounces off the safe:

```text
(Bob)  open the crew footlocker  -> You open the crew footlocker.
(Bob)  open the officers safe    -> The officers safe reads your crew rank and stays shut. Officers only.
(Vala) open the officers safe    -> You open the officers safe.
```

Promote Bob to Officer (`org promote Bob` from 221) and the safe opens for
him too — no locker edit, just his rung changing on the ladder.

## Going further

- **Per-rank allowances** — cap a withdraw at `V('rank_' + enactor.id, 0)
  * 100` credits per day (stamp `drew_<id>` with `now()`),
  so higher rank means a bigger draw, not just permission.
- **Locker teleport storage** — on a successful open, the safe could
  `teleport_obj` its contents from a hidden back room, so shared crew gear
  lives off the map until an officer calls for it (the
  [coat check](022_coat_check.md) storage-teleport variant).
- **Dues** — a `script_ticker` on the master that debits each member's
  wallet a small dues amount into the treasury each period, evicting
  (kicking, per 221) anyone who can't pay twice running.
- **Treasury-funded perks** — wire the [titles Herald](220_titles_badges.md)
  or the [event board](227_event_calendar.md) to draw prize money from the
  crew vault, so the crew's own funds pay for its ceremonies.
```
