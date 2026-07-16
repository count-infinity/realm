# 004. ATM / bank terminal

> Checklist item 4 — [now] — *shared state on one bank object, eval_attr, attrs vs object identity*

**What you'll build:** A banking network: one admin-owned **BankNet
Core** holds every account and the cash reserve; steel kiosks scattered
across the map are dumb frontends — `deposit`, `withdraw`, and `atm`
work identically at every terminal, and `@clone` opens a new branch in
one command.

**Concepts:** state on a single master object vs. object identity
(accounts are *attributes of the core*, not properties of a kiosk),
`eval_attr()` calling shared routines across the map, owner authority
(an admin's machine may debit a consenting player), `transfer_credits`
between wallet and vault, terminals as clonable furniture.

This is the little sibling of the [bank accounts](087_bank_accounts.md)
tutorial — 087 builds the full bank (audit logs, wires, interest on a
ticker) as *one* counter object; this build shows how to split the same
state into a master plus any number of frontends. Read 087 for the
deposit/withdraw mechanics in depth; read this for the network shape.

## How it works

**Accounts are attributes, not objects.** Your balance is
`acct_<your-id>` on the core — a number on one object, exactly like
087. What this tutorial adds is the *split*: no player ever stands in
front of the core. They stand at a terminal, and the terminal reaches
the core by name with `get('BankNet Core')` — object identity matters
only for finding the state, never for holding it.

**`eval_attr` borrows code, not identity.** Each operation lives once,
as a function attribute on the core (`net_deposit`, `net_withdraw`,
`net_balance`); a terminal command is one line:
`eval_attr(get('BankNet Core'), 'net_deposit', trim(arg0))`. The
routine runs *as the calling terminal* (the executor doesn't change —
that's the authority rule for softcode subroutines), which is why each
routine begins by resolving `bank = get('BankNet Core')` instead of
trusting `me`. Fix a bug in one routine and every kiosk on the map is
fixed.

**Why the owner must be an admin.** Scripts move money only from
objects they control. A terminal owned by an admin acts with the
admin's authority (Penn-style delegation), so
`transfer_credits(enactor, bank, amt)` may debit the typing player —
the same owner-authority lesson as 087's counter. The consent is the
typed command: nobody's wallet moves until they ask a terminal to move
it. Build this as a mortal builder and deposits simply fail.

**Where the cash sits.** Deposits land on the *core* — its credit
balance is the network's vault reserve, and withdrawals pay out of it.
The kiosks never hold a credit: rob a terminal, get scrap metal.

## Build it

The core. Drop it in a back office, a vault, anywhere — terminals find
it by name, not location (build as an **admin**; see above):

```text
@create BankNet Core
drop BankNet Core
```

The three shared routines. Each resolves the core by name, validates,
moves real credits wallet-to-vault (or back), updates the ledger
attribute, and answers the customer — `arg0` arrives from the calling
terminal, and `isdigit` keeps `deposit lots` from crashing anything:

```text
@set BankNet Core/net_balance = bank = get('BankNet Core'); pemit(enactor, 'BANKNET -- account balance: ' + str(get_attr(bank, 'acct_' + enactor.id, 0)) + ' credits.'); result = 1
@set BankNet Core/net_deposit = bank = get('BankNet Core'); amt = int(arg0) if arg0.isdigit() else 0; ok = amt > 0 and transfer_credits(enactor, bank, amt); k = 'acct_' + enactor.id; bal = get_attr(bank, k, 0) + amt; set_attr(bank, k, bal) if ok else None; pemit(enactor, 'Deposit accepted. Balance: ' + str(bal) + ' credits.' if ok else 'The terminal buzzes: your wallet cannot cover that.'); result = 1
@set BankNet Core/net_withdraw = bank = get('BankNet Core'); amt = int(arg0) if arg0.isdigit() else 0; k = 'acct_' + enactor.id; bal = get_attr(bank, k, 0); ok = 0 < amt <= bal and transfer_credits(bank, enactor, amt); set_attr(bank, k, bal - amt) if ok else None; pemit(enactor, 'Notes whir out of the slot. Balance: ' + str(bal - amt) + ' credits.' if ok else 'The terminal buzzes: insufficient funds on account.'); result = 1
```

The terminal — a dumb frontend: a screen that reads *your* account off
the core per viewer, and three one-line commands that delegate.
(`$atm`, not `$balance` — `balance` is an alias of the `credits`
builtin, and builtins dispatch first.)

```text
@create atm terminal
drop atm terminal
@desc atm terminal = A steel kiosk with a scratched screen and a cash slot polished by thumbs. [[result = 'The screen glows: ACCT ' + str(get_attr(get('BankNet Core'), 'acct_' + viewer.id, 0)) + ' CR.']]
@set atm terminal/cmd_atm = $atm: eval_attr(get('BankNet Core'), 'net_balance')
@set atm terminal/cmd_deposit = $deposit *: eval_attr(get('BankNet Core'), 'net_deposit', trim(arg0))
@set atm terminal/cmd_withdraw = $withdraw *: eval_attr(get('BankNet Core'), 'net_withdraw', trim(arg0))
```

A second branch is a walk and a clone — the copy carries every
attribute, so it works the moment it lands:

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

Same account, either kiosk — the state never left the core. Overdrafts
(`withdraw 500`), overdeposits, and word salad (`deposit lots`) all
buzz with a specific refusal and move nothing. `@examine BankNet Core`
as the admin shows the vault: 35 credits of reserve and one
`acct_<id>` per customer.

## Going further

- **Audit trails:** add 087's `log_row` routine to the core and call it
  from `net_deposit`/`net_withdraw` — the statement command then works
  at every kiosk for free.
- **Wires between players:** port 087's `xfer` as a `net_xfer` routine;
  ledger-to-ledger transfers need no cash movement at all.
- **Out-of-order terminals:** give kiosks an `offline` attribute the
  three commands check first — network maintenance becomes `@set`.
- **Withdrawal fees:** debit `amt + 1` from the ledger and keep the
  fee in the vault — a credit sink, which player economies need more
  than faucets.
