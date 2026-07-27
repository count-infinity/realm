# 222. Org treasury & storage

> Checklist item 222 ([now]): *org credits, rank-gated $-commands, locked containers*

**What you'll build:** money and storage for the Void Runners crew from
[221](221_organizations.md). Any member pays into a shared treasury, only
officers draw from it, and two footlockers in the clubhouse each stay shut
until the opener's crew rank is high enough, so a Recruit opens the common
locker while the officers' safe reads that same rank and turns him away.

**Concepts:** a **shared vault** held as credits on the org master, one
account for the whole crew where the [bank](087_bank_accounts.md) keeps one
per player; **rank-gated** `$`-commands reading the ladder built in 221; a
capped audit log written through a shared
[`eval_attr`](../reference/softcode.md#fn-eval_attr) routine; and
**rank-sealed containers**, where an `on_check` ward keyed to org rank does
the job a physical key does in the [locked chest](015_locked_chest.md).

## How it works

The finished build is one object plus two boxes. The Void Runners master
from [221](221_organizations.md) gains three verbs (`treasury`,
`treasury deposit <n>`, and `treasury withdraw <n>`) and carries the crew's
money as its own credit balance, while the two footlockers are ordinary
closed containers that consult that master for the opener's rank before
they agree to open. This section answers where the money sits, what
authority lets the master reach into a player's wallet, what keeps a
Recruit from draining the vault, and how a locker enforces a rank it never
stores.

### Where does the crew's money sit?

On the master, as the master's own balance. Every object in REALM carries
one credit balance, so the crew's vault is the same integer a player's
wallet is, and [`credits(me)`](../reference/softcode.md#fn-credits) reads
it. The [bank](087_bank_accounts.md) keeps a per-player `acct_<id>` ledger
attribute because it holds many accounts; the crew needs no ledger at all,
since there is exactly one account and the engine already stores it.

Money moves only through
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits), which
debits the source and credits the destination in one step and refuses
outright when the source is short. A deposit is
`transfer_credits(enactor, me, amt)` and a withdrawal is
`transfer_credits(me, enactor, amt)`, which means the vault pays out only
money it genuinely holds and no bookkeeping is needed to keep it honest.
Nothing here calls
[`adjust_credits`](../reference/softcode.md#fn-adjust_credits), the
mint-and-burn primitive that creates or destroys money out of nothing; the
bank uses that deliberately to pay interest, whereas a crew treasury only
ever moves funds that already exist.

### What lets the master reach into a player's wallet?

`transfer_credits` moves money only **out of something the executing object
controls**, and a script runs as the object it is stored on. So the deposit
verb is the master debiting a player, which succeeds because the master is
admin-owned and an object acts with its owner's authority. Build the
charter as an ordinary player instead and that call returns False for
everyone except that one owner, so their crewmates' deposits fall into the
refusal branch.

Withdrawals need none of that reach. A withdrawal takes money out of the
master itself, and every object controls itself, so `treasury withdraw`
works on a charter owned by anybody. That asymmetry is the general rule for
softcode handling other people's property: the direction of the transfer
decides which authority is required.

### What stops a Recruit from draining the vault?

The verb checks rank, and nothing else does. Deposit asks for rank 1 or
better, so any member may chip in, while withdraw asks for rank 2, which is
Officer and up. Both read the `rank_<id>` attributes that
[221](221_organizations.md) writes onto this same master, so the ladder has
one home and the treasury simply reads it.

Ownership and rank stay strictly separate here, exactly as they do in 221.
Owner authority is what lets the object move money at all, while *who* may
move it is a number on the ladder, checked in the verb. An admin who never
joined the crew has rank 0 and collects the same refusal as any outsider.

### How does a footlocker enforce a rank it never stores?

It asks the master at the moment of the open. Each locker is a closed
[container](014_basic_container.md) carrying a `min_rank` attribute and an
`on_check` ward on the `item:on_open`
[action](../reference/softcode.md#event-data-namespace), the same gate the
[gift box](012_gift_box.md) and the [airlock](032_airlock.md) hang on that
event. The ward resolves the charter by name with
[`get`](../reference/softcode.md#fn-get), reads `rank_<opener id>` off it
with [`get_attr`](../reference/softcode.md#fn-get_attr), and calls
[`block`](../reference/softcode.md#event-data-namespace) when that rank
falls under `min_rank`. A locker's whole access tier is
therefore one integer: 1 for the common footlocker, 2 for the officers'
safe. Promote someone in 221 and the set of boxes they can open changes
with no edit to either box.

The lockers are `closed` but never `locked`, and the difference matters.
The `locked` tag makes `open` refuse before any action is fired, so a ward
would never see the attempt; leaving the box merely closed sends a real
`item:on_open` action through the room, and the ward is what refuses it.
That is how the refusal ends up depending on live crew rank rather than on
who is holding a key.

Because the check pass runs *before* the effect, a ward is read-only by
construction: its namespace has the reads, the dice, and the decision verbs
(`block`, `mod`, `set_adata`), and no mutators at all. Anything the locker
should *do* on a successful open belongs in an `ON_OPEN`
[hook](../reference/softcode.md#lifecycle-hooks) instead, which runs after
the box is open.

### How the ward knows the open is its own

Every ward here opens with the same line,
[`if atype == 'item:on_open' and target is me:`](../reference/softcode.md#guard-on-target),
and both halves of it earn their place, though for different reasons.

The `atype` test is what keeps the two lockers apart from the rest of a
box's life. A ward runs on the participants in an action, which means the
actor, the room it happens in, and the target, so *every* action aimed at
this box runs this script: closing it, picking it up, putting something
inside it, locking it. Without the `atype` test the safe would refuse all
of those to a Recruit as well, and the box would become unusable rather
than merely shut.

The `target is me` test is the identity check that says "this happened to
me" rather than "this happened near me". Wards are the narrower case, since
a bystander standing in the room does not run its ward at all, but the
matching reaction hooks are not narrow: an
[`ON_<EVENT>`](../reference/softcode.md#lifecycle-hooks) hook fires on the
room, on every object in it, and on the target, so an unguarded `ON_OPEN`
on the safe announces itself when the footlocker is opened. Writing the
guard on both, always, is how the two stay consistent, and `is` is the
identity test to use rather than `==`.

One more property makes the ward trustworthy: a ward that calls `block`
fails **closed**. If the script raises, the engine refuses the action and
messages the object's owner, so a broken ward never reads to the world as
an open one.

## Build it

This continues from [221](221_organizations.md), so the Void Runners master
and the clubhouse already exist. Stand in the clubhouse, since the lockers
are dropped there:

```text
@teleport The Void Runners Clubhouse
```

The audit trail is one attribute, `tlog`, holding the ten newest rows. A
single statement appends and trims it, so `log_row` stays a one-liner. It
is called through `eval_attr`, which runs a routine with the *caller's*
identity rather than swapping to the attribute's object, and since the
caller here is the master, `me` inside the routine is still the master:

```text
@set the Void Runners/log_row = set_attr(me, 'tlog', (V('tlog', []) + [arg0])[-10:])
```

`treasury` on its own reports the balance and replays the log, so it needs
no rank at all:

```text
@set the Void Runners/cmd_treasury = '''
$treasury:
pemit(enactor, f'Void Runners treasury: {credits(me)} credits.')
for row in V('tlog', []):
    pemit(enactor, '  ' + row)
'''
```

`treasury deposit <n>` reads the amount, reads the payer's rung, and then
tries the transfer. Because the transfer is the last test in the condition,
it is attempted only after the rank and the amount pass, and a short wallet
lands in the same else branch as a stranger:

```text
@set the Void Runners/cmd_deposit = '''
$treasury deposit *:
amt = int(trim(arg0)) if trim(arg0).isdigit() else 0
mine = V('rank_' + enactor.id, 0)
if mine >= 1 and amt > 0 and transfer_credits(enactor, me, amt):
    eval_attr(me, 'log_row', f'{name(enactor)} deposited {amt}')
    pemit(enactor, f'Deposited {amt} credits.')
    remit(here, f'{name(enactor)} pays {amt} credits into the crew treasury.')
else:
    pemit(enactor, 'Members only, and your wallet must cover it.')
'''
```

`treasury withdraw <n>` is the mirror image with the rung raised to Officer
and the transfer running the other way. No balance check is written out,
because `transfer_credits` already refuses to overdraw the master:

```text
@set the Void Runners/cmd_withdraw = '''
$treasury withdraw *:
amt = int(trim(arg0)) if trim(arg0).isdigit() else 0
mine = V('rank_' + enactor.id, 0)
if mine >= 2 and amt > 0 and transfer_credits(me, enactor, amt):
    eval_attr(me, 'log_row', f'{name(enactor)} withdrew {amt}')
    pemit(enactor, f'Withdrew {amt} credits.')
    remit(here, f'{name(enactor)} draws {amt} credits from the crew treasury.')
else:
    pemit(enactor, 'Officers only, and the treasury must cover it.')
'''
```

Now the storage. Both lockers are plain containers, dropped and closed, and
each carries the one integer that is its access tier:

```text
@create crew footlocker
@tag crew footlocker = container
drop crew footlocker
@set crew footlocker/min_rank = 1
close crew footlocker
@create officers safe
@tag officers safe = container
drop officers safe
@set officers safe/min_rank = 2
close officers safe
```

(Name them without a leading "the": the engine supplies the article when it
prints `You open the crew footlocker`, and a player typing
`open the crew footlocker` is matched either way.)

The common footlocker's ward names its own business first, then asks the
charter for the opener's rung:

```text
@set crew footlocker/on_check = '''
if atype == 'item:on_open' and target is me:  # every action aimed at this box runs this script
    org = get('the Void Runners')
    if get_attr(org, 'rank_' + actor.id, 0) < V('min_rank', 1):
        block('The footlocker is sealed to Void Runners members.')
'''
```

The officers' safe's ward is the same script with a different refusal line,
since the rung it demands comes from its own `min_rank` rather than from
the code:

```text
@set officers safe/on_check = '''
if atype == 'item:on_open' and target is me:
    org = get('the Void Runners')
    if get_attr(org, 'rank_' + actor.id, 0) < V('min_rank', 2):
        block('The officers safe reads your crew rank and stays shut. Officers only.')
'''
```

## Try it

Vala is the Commander and Bob a Recruit, both from [221](221_organizations.md).
Give Bob some money to spend, then watch his rung decide which way that
money is allowed to flow:

```text
(Vala)
> @eval adjust_credits(get('Bob'), 100)

(Bob)
> treasury deposit 40
Deposited 40 credits.
Bob pays 40 credits into the crew treasury.

> treasury withdraw 10
Officers only, and the treasury must cover it.

(Vala)
> treasury withdraw 10
Withdrew 10 credits.
Vala draws 10 credits from the crew treasury.

> treasury
Void Runners treasury: 30 credits.
  Bob deposited 40
  Vala withdrew 10
```

The two lines worth confirming deliberately are the recruit's refusal, which
proves the gate is rank and not ownership, and the closing balance of 30,
which proves the money really moved twice rather than being reported from a
tally attribute.

The lockers read the same ladder. Cass, who never joined, is turned away by
the common footlocker; Bob opens it and bounces off the safe:

```text
(Cass)
> open the crew footlocker
The footlocker is sealed to Void Runners members.

(Bob)
> open the crew footlocker
You open the crew footlocker.

> open the officers safe
The officers safe reads your crew rank and stays shut. Officers only.
```

Bob's successful open is the one to watch, because the safe is standing in
the same room and demands a rung he lacks. It stays quiet, which is the
ward scope in action: the safe is a bystander to that open, not a
participant, so its ward never runs. Promote him and the safe changes its
mind with no edit to any box:

```text
(Vala)
> org promote Bob
Vala promotes Bob to Officer.

(Bob)
> open the officers safe
You open the officers safe.
```

## Going further

- **Per-rank allowances.** Cap a draw at
  [`V('rank_' + enactor.id, 0)`](../reference/softcode.md#fn-v)` * 100`
  credits per period, stamping `drew_<id>` with
  [`now()`](../reference/softcode.md#fn-now) on each withdrawal, so a higher
  rung means a bigger draw and not merely permission.
- **Pay straight into the vault.** The built-in
  `pay 40 to the Void Runners` moves the money itself and then fires
  `event:payment` at the master, so an `ON_PAYMENT` hook reads
  [`adata('amount')`](../reference/softcode.md#event-data-namespace) and
  writes the audit row. That route needs no rank check and no owner
  authority, since the payer's own command did the moving. Open the hook
  with `if target is me:`, because a reaction hook hears every payment in
  the room and would otherwise bank the credits a member handed to the
  vending machine next to it.
- **Locker teleport storage.** On a successful open, an `ON_OPEN` hook on
  the safe (guarded with `if target is me:`, and a hook rather than the ward
  because the check pass may not mutate) calls
  [`teleport_obj`](../reference/softcode.md#fn-teleport_obj) to bring the
  crew's shared gear in from a back room, which is the
  [coat check](022_coat_check.md)'s storage-teleport idea applied to a crew.
- **Dues.** Give the master a `script_ticker` and an `on_tick` that debits
  each member's wallet a small amount into the treasury every period,
  expelling (the `org kick` path from 221) anyone who misses two periods
  running.
- **Treasury-funded perks.** Wire the
  [titles Herald](220_titles_badges.md) or the
  [event board](227_event_calendar.md) to draw prize money from the crew
  vault, so the crew's own funds pay for its ceremonies.
