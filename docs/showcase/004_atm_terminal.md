# 004. ATM / bank terminal

> Checklist item 4 ([now]): *shared state on one bank object, call() as a method on the core, referencing objects by stable id*

**What you'll build:** A banking network. One admin-owned **BankNet
Core** holds every account and the cash reserve; steel kiosks scattered
across the map are dumb frontends, so `deposit`, `withdraw`, and `atm`
work identically at every terminal, and `@clone` opens a new branch in
one command.

**Concepts:** state on a single master object vs. object identity
(accounts are *attributes of the core*, not properties of a kiosk),
[`call()`](../reference/softcode.md#fn-call) invoking a routine as a
**method on the core** (so it runs *as* the core), referencing that
master by a **stable id**, owner authority (the core debits a consenting
player),
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits)
between wallet and vault, terminals as clonable furniture.

This is the little sibling of the [bank accounts](087_bank_accounts.md)
tutorial. 087 builds the full bank (audit logs, wires, interest on a
ticker) as *one* counter object; this build shows how to split the same
state into a master plus any number of frontends. Read 087 for the
deposit/withdraw mechanics in depth; read this for the network shape.

## How it works

**Accounts are attributes, not objects.** Your balance is
`acct_<your-id>` on the core, a number on one object, exactly like 087.
What this tutorial adds is the *split*: no player ever stands in front
of the core. They stand at a terminal, and the terminal asks the core to
read and move the state. Object identity matters only for *finding* the
core, never for holding the accounts.

**Find the core by id, not by name.** A terminal has to name the object
it delegates to, and the tempting way is
[`get('BankNet Core')`](../reference/softcode.md#fn-get). Don't:
[`get`](../reference/softcode.md#fn-get) resolves a *name* to the first
match and never complains about ambiguity, so the day someone builds a
second "BankNet Core" anywhere in the world, half your kiosks may
silently wire themselves to the impostor. Instead, capture the core's
**id** once, at build time, into each terminal's `bank_core_id`, and look
it up with `get('#' + V('bank_core_id'))`: an exact, collision-proof
reference that survives renames and duplicate names alike. Store the
*bare* id, not a `#`-prefixed string, because that is what a fresh-id
import remaps: worldio rewrites a bare exported id to each copy's own
core, so importing the branch as a fresh copy yields an independent bank
rather than a second face on the same vault. (Ids are the stable handle;
names are for humans. A well-known object can also carry a
friendly [`$keyid`](../design/object-identity.md) handle set with
`@keyid`; this build stores the id to show the underlying
reference-by-identity pattern.)

**`call` runs the routine *as the core*.** Each operation lives once, as
a function attribute on the core (`net_deposit`, `net_withdraw`,
`net_balance`), and a terminal command is one line:
[`call(get('#' + V('bank_core_id')), 'net_deposit', trim(arg0))`](../reference/softcode.md#fn-call).
The point is *whose* the routine runs as.
[`call`](../reference/softcode.md#fn-call) is a **method invocation on
the core**: inside the routine `me` *is* the core, so
[`V()`](../reference/softcode.md#fn-v) and `get_attr(me, ...)` read the
core's own accounts directly, with nothing to re-resolve. (Its sibling
[`eval_attr`](../reference/softcode.md#fn-eval_attr) would instead run the
code *as the calling terminal*, which is right for splitting up one
object's own logic but wrong here, because the accounts live on the core,
not the kiosk.) Fix a bug in one routine and every kiosk on the map is
fixed.

**Why the core must be admin-owned.** A routine can move money only from
objects its runner controls, and `call` runs `net_deposit` *as the core*,
so it is the **core's** authority that debits the customer:
[`transfer_credits(enactor, me, amt)`](../reference/softcode.md#fn-transfer_credits)
works because the admin-owned core controls the typing player (Penn-style
delegation), the same owner-authority lesson as [087](087_bank_accounts.md)'s counter. The
consent is the typed command: nobody's wallet moves until they ask a
terminal to move it. The **terminals** need no special ownership; built
by the same admin, they co-own the core, and `call` is allowed between
objects that control each other. (A player-built kiosk calling someone
else's core would instead need that routine flagged
[`public`](../reference/softcode.md#fn-call), the deliberate cross-owner
opt-in.) Build the core as a mortal and deposits simply fail.

**Where the cash sits.** Deposits land on the *core*: its credit balance
is the network's vault reserve, and withdrawals pay out of it. The kiosks
never hold a credit, so rob a terminal and get scrap metal.

## Build it

The scripts here are `'''` multi-line blocks (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)).

The core. Drop it in a back office, a vault, anywhere. Terminals find it
by id, not location (build the core as an **admin**; see above):

```text
@create BankNet Core
drop BankNet Core
```

The three shared routines, each running *as the core*, so `me` is the
vault. Each validates, moves real credits wallet-to-vault (or back),
bumps the ledger on `me` with [`incr`](../reference/softcode.md#fn-incr) / [`decr`](../reference/softcode.md#fn-decr), and answers the customer. `arg0`
arrives from the calling terminal, and `isdigit` keeps `deposit lots`
from crashing anything:

```text
@set BankNet Core/net_balance = '''
pemit(enactor, f"BANKNET -- account balance: {get_attr(me, 'acct_' + enactor.id, 0)} credits.")
result = 1
'''
@set BankNet Core/net_deposit = '''
amt = int(arg0) if arg0.isdigit() else 0
k = 'acct_' + enactor.id
if amt > 0 and transfer_credits(enactor, me, amt):  # me = the core, so it debits the consenting player
    pemit(enactor, f'Deposit accepted. Balance: {incr(k, amt)} credits.')
else:
    pemit(enactor, 'The terminal buzzes: your wallet cannot cover that.')
result = 1
'''
@set BankNet Core/net_withdraw = '''
amt = int(arg0) if arg0.isdigit() else 0
k = 'acct_' + enactor.id
bal = get_attr(me, k, 0)
if 0 < amt <= bal and transfer_credits(me, enactor, amt):
    pemit(enactor, f'Notes whir out of the slot. Balance: {decr(k, amt)} credits.')
else:
    pemit(enactor, 'The terminal buzzes: insufficient funds on account.')
result = 1
'''
```

The terminal, a dumb frontend: a screen that reads *your* account off the
core per viewer, and three one-line commands that `call` the core. It
first captures the core's id into its own `bank_core_id` (the one time we
resolve the core by name, before any duplicate could exist), so every
lookup below is by id. (`$atm`, not `$balance`, because `balance` is an
alias of the `credits` builtin and builtins dispatch first.)

```text
@create atm terminal
drop atm terminal
@eval set_attr(get('atm terminal'), 'bank_core_id', get('BankNet Core').id)
@desc atm terminal = A steel kiosk with a scratched screen and a cash slot polished by thumbs. [[result = f"The screen glows: ACCT {get_attr(get('#' + V('bank_core_id')), 'acct_' + viewer.id, 0)} CR."]]
@set atm terminal/cmd_atm = $atm: call(get('#' + V('bank_core_id')), 'net_balance')
@set atm terminal/cmd_deposit = $deposit *: call(get('#' + V('bank_core_id')), 'net_deposit', trim(arg0))
@set atm terminal/cmd_withdraw = $withdraw *: call(get('#' + V('bank_core_id')), 'net_withdraw', trim(arg0))
```

A second branch is a walk and a clone. The copy carries every attribute,
`bank_core_id` included, so it points at the same vault the moment it
lands:

```text
@dig The Docks Concourse = gangway, plaza
gangway
@clone atm terminal
plaza
```

## Try it

As a customer with 100 credits in pocket, at the plaza terminal:

```text
atm                  -> BANKNET -- account balance: 0 credits.
deposit 60           -> Deposit accepted. Balance: 60 credits.
look atm terminal    -> The screen glows: ACCT 60 CR.
gangway
atm                  -> BANKNET -- account balance: 60 credits.
withdraw 25          -> Notes whir out of the slot. Balance: 35 credits.
plaza
atm                  -> BANKNET -- account balance: 35 credits.
```

Same account, either kiosk: the state never left the core, and both
terminals hold the same `bank_core_id`, so both resolve to the same vault
no matter what else shares its name. Overdrafts (`withdraw 500`),
overdeposits, and word salad (`deposit lots`) all buzz with a specific
refusal and move nothing. `@examine BankNet Core` as the admin shows the
vault: 35 credits of reserve and one `acct_<id>` per customer.

## Going further

- **Audit trails:** add 087's `log_row` routine to the core and call it
  from `net_deposit`/`net_withdraw`, and the statement command then works
  at every kiosk for free.
- **Wires between players:** port 087's `xfer` as a `net_xfer` routine;
  ledger-to-ledger transfers need no cash movement at all.
- **Kiosks anyone can own:** flag the `net_*` routines
  [`public`](../reference/softcode.md#fn-call) (`@attr BankNet Core/net_deposit = public`)
  and a player can build their own branded terminal that `call`s your
  core without owning it. The `public` flag is the deliberate cross-owner
  opt-in; co-owned kiosks like the ones above never need it.
- **A second, independent branch:** import the bank as a fresh copy
  (fresh ids); because `bank_core_id` holds a bare id, each copy's
  terminals re-wire to *its* core, so it is a separate bank, not a second
  face on the same vault.
- **Withdrawal fees:** debit `amt + 1` from the ledger and keep the fee
  in the vault, a credit sink, which player economies need more than
  faucets.
