# 004. ATM / bank terminal

> Checklist item 4 ([now]): *shared state on one bank object, eval_attr, referencing objects by stable id*

**What you'll build:** A banking network. One admin-owned **BankNet
Core** holds every account and the cash reserve; steel kiosks scattered
across the map are dumb frontends, so `deposit`, `withdraw`, and `atm`
work identically at every terminal, and `@clone` opens a new branch in
one command.

**Concepts:** state on a single master object vs. object identity
(accounts are *attributes of the core*, not properties of a kiosk),
[`eval_attr()`](../reference/softcode.md#fn-eval_attr) calling shared
routines across the map, referencing that master by a **stable id**
instead of by name, owner authority (an admin's machine may debit a
consenting player),
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
of the core. They stand at a terminal, and the terminal reaches the
core to read and move the state. Object identity matters only for
*finding* the state, never for holding it.

**Find the core by id, not by name.** A terminal has to name the object
it delegates to, and the tempting way is
[`get('BankNet Core')`](../reference/softcode.md#fn-get). Don't:
[`get`](../reference/softcode.md#fn-get) resolves a *name* to the first
match and never complains about ambiguity, so the day someone builds a
second "BankNet Core" anywhere in the world, half your kiosks may
silently wire themselves to the impostor. Instead, capture the core's
**id** once, at build time, into a `bank_core_id` attribute: the core
writes its own `#id` there, every terminal copies that handle, and from
then on each lookup is
[`get(V('bank_core_id'))`](../reference/softcode.md#fn-v), an exact,
collision-proof reference that survives renames and duplicate names
alike. (Ids are the stable handle; names are for humans. See the
backlog's *friendlier object ids* note for where legibility is headed.)

**`eval_attr` borrows code, not identity.** Each operation lives once,
as a function attribute on the core (`net_deposit`, `net_withdraw`,
`net_balance`); a terminal command is one line:
[`eval_attr(get(V('bank_core_id')), 'net_deposit', trim(arg0))`](../reference/softcode.md#fn-eval_attr).
The routine runs *as the calling terminal* (the executor doesn't
change, that's the authority rule for softcode subroutines), which is
why each routine re-resolves `bank = get(V('bank_core_id'))` from the
terminal's own handle instead of trusting `me`. Fix a bug in one
routine and every kiosk on the map is fixed.

**Why the owner must be an admin.** Scripts move money only from
objects they control. A terminal owned by an admin acts with the
admin's authority (Penn-style delegation), so
[`transfer_credits(enactor, bank, amt)`](../reference/softcode.md#fn-transfer_credits)
may debit the typing player, the same owner-authority lesson as 087's
counter. The consent is the typed command: nobody's wallet moves until
they ask a terminal to move it. Build this as a mortal builder and
deposits simply fail.

**Where the cash sits.** Deposits land on the *core*: its credit
balance is the network's vault reserve, and withdrawals pay out of it.
The kiosks never hold a credit, so rob a terminal and get scrap metal.

## Build it

The core. Drop it in a back office, a vault, anywhere. Terminals find
it by id, not location (build as an **admin**; see above):

```text
@create BankNet Core
drop BankNet Core
```

Stamp the core with its own stable handle. This is the one time we
resolve it by name: right after creating it, before any duplicate could
exist, we read its `#id` and store it in `bank_core_id`. Every node in
the network shares this exact handle from here on:

```text
@eval c = get('BankNet Core'); set_attr(c, 'bank_core_id', '#' + c.id)
```

The three shared routines. Each resolves the core through its stored id,
validates, moves real credits wallet-to-vault (or back), updates the
ledger attribute, and answers the customer. `arg0` arrives from the
calling terminal, and `isdigit` keeps `deposit lots` from crashing
anything:

```text
@set BankNet Core/net_balance = bank = get(V('bank_core_id')); pemit(enactor, f"BANKNET -- account balance: {get_attr(bank, 'acct_' + enactor.id, 0)} credits."); result = 1
@set BankNet Core/net_deposit = bank = get(V('bank_core_id')); amt = int(arg0) if arg0.isdigit() else 0; ok = amt > 0 and transfer_credits(enactor, bank, amt); k = f'acct_{enactor.id}'; bal = get_attr(bank, k, 0) + amt; set_attr(bank, k, bal) if ok else None; pemit(enactor, f'Deposit accepted. Balance: {bal} credits.' if ok else 'The terminal buzzes: your wallet cannot cover that.'); result = 1
@set BankNet Core/net_withdraw = bank = get(V('bank_core_id')); amt = int(arg0) if arg0.isdigit() else 0; k = f'acct_{enactor.id}'; bal = get_attr(bank, k, 0); ok = 0 < amt <= bal and transfer_credits(bank, enactor, amt); set_attr(bank, k, bal - amt) if ok else None; pemit(enactor, f'Notes whir out of the slot. Balance: {bal - amt} credits.' if ok else 'The terminal buzzes: insufficient funds on account.'); result = 1
```

The terminal, a dumb frontend: a screen that reads *your* account off
the core per viewer, and three one-line commands that delegate. The
first thing it does is copy the core's handle onto itself, so every
lookup below is by id. (`$atm`, not `$balance`, because `balance` is an
alias of the `credits` builtin and builtins dispatch first.)

```text
@create atm terminal
drop atm terminal
@eval set_attr(get('atm terminal'), 'bank_core_id', get_attr(get('BankNet Core'), 'bank_core_id'))
@desc atm terminal = A steel kiosk with a scratched screen and a cash slot polished by thumbs. [[result = f"The screen glows: ACCT {get_attr(get(V('bank_core_id')), 'acct_' + viewer.id, 0)} CR."]]
@set atm terminal/cmd_atm = $atm: eval_attr(get(V('bank_core_id')), 'net_balance')
@set atm terminal/cmd_deposit = $deposit *: eval_attr(get(V('bank_core_id')), 'net_deposit', trim(arg0))
@set atm terminal/cmd_withdraw = $withdraw *: eval_attr(get(V('bank_core_id')), 'net_withdraw', trim(arg0))
```

A second branch is a walk and a clone. The copy carries every
attribute, `bank_core_id` included, so it points at the same vault the
moment it lands:

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
terminals hold the same `bank_core_id`, so both resolve to the same
vault no matter what else shares its name. Overdrafts (`withdraw 500`),
overdeposits, and word salad (`deposit lots`) all buzz with a specific
refusal and move nothing. `@examine BankNet Core` as the admin shows
the vault: 35 credits of reserve and one `acct_<id>` per customer.

## Going further

- **Audit trails:** add 087's `log_row` routine to the core and call it
  from `net_deposit`/`net_withdraw`, and the statement command then
  works at every kiosk for free.
- **Wires between players:** port 087's `xfer` as a `net_xfer` routine;
  ledger-to-ledger transfers need no cash movement at all.
- **Out-of-order terminals:** give kiosks an `offline` attribute the
  three commands check first, and network maintenance becomes `@set`.
- **Withdrawal fees:** debit `amt + 1` from the ledger and keep the fee
  in the vault, a credit sink, which player economies need more than
  faucets.
