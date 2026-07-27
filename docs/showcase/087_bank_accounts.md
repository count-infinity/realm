# 087. Bank accounts

> Checklist item 87 ([now]): *ledger attrs, transfer_credits, on_tick interest, audit logs*

**What you'll build:** A station bank, all held as attributes on one
admin-owned master object: deposits, withdrawals, player-to-player wires
that reach across the map, interest on a heartbeat, and a capped
per-account audit trail.

**Concepts:** ledger state as attributes (`acct_<id>`); owner authority
(an admin's master may move players' money); `transfer_credits` between
wallet and vault; `script_ticker`/`on_tick` interest with an explicit
minting faucet; audit-log attributes with a cap; `eval_attr` for shared
routines.

## How it works

The bank is one object, First Orbital Bank, dropped in a room, and every
account it holds is a plain attribute on that object. A player types
`deposit`, `withdraw`, `xfer`, or `bank` at it, and a heartbeat pays
interest. This section covers where the money lives, why two kinds of
money never get confused, how interest can create money without breaking
the books, and why the balance command is not called `balance`.

### Accounts are attributes

The bank's whole state is attributes on the one object:

- `acct_<player-id>`, the account balance (an integer of ledger money),
- `log_<player-id>`, the newest ten audit rows for that account,
- `members`, every id that ever held an account, which the interest tick
  iterates. Softcode cannot list an object's attributes by prefix, so the
  roster of holders is kept explicitly rather than read back off the
  `acct_<id>` keys.
- `rate`, interest percent per tick.

### Two kinds of money

Two kinds of money meet here and are never confused. Wallet credits are
the engine's canonical balance, the number the `credits` builtin reports;
ledger numbers are the bank's promises, the `acct_<id>` attributes.
`deposit` converts one into the other with
[`transfer_credits(enactor, me, amt)`](../reference/softcode.md#fn-transfer_credits),
so the credits physically sit on the bank object as its vault reserve, and
`withdraw` converts back. An internal `xfer` between accounts touches only
ledger attributes, so no credits move, which is why the recipient can be
on the far side of the station, or offline. The vault therefore always
covers the ledger. The little sibling of this build, the
[ATM terminal](004_atm_terminal.md), splits this same reserve across many
kiosks.

### The interest faucet

The exception to "the vault covers the ledger" is interest, which creates
money. The tick makes that faucet explicit: for each member it mints
reserve with
[`adjust_credits(me, gain)`](../reference/softcode.md#fn-adjust_credits)
and credits the ledger, so the invariant survives. Delete the
`adjust_credits` call and you have built a bank that can promise more than
it holds, a fine drama hook but a poor default. The reserve backing is the
same idea as the [currency mint](086_currency.md), where every coin in
circulation is backed one-for-one.

### The capped audit log

Every mutation appends a row to the account's log through one shared
`log_row` function attribute, called with
[`eval_attr`](../reference/softcode.md#fn-eval_attr) so the formatting
lives in exactly one place. The slice keeps only the newest ten rows,
because an unbounded list on a hot attribute is the classic MUD database
leak.

### Why the command is `bank`, not `balance`

Builtins dispatch before `$`-triggers, and `balance` is already an alias
of the `credits` builtin, so a `$balance` trigger would be shadowed every
time. `bank` is unclaimed. The four commands here are `$`-triggers, which
fire only for the player who typed them, so they need no `target is me`
guard. The only scheduled code, `on_tick`, runs on the bank itself on a
cadence and walks its own roster, so it needs no guard either.

## Build it

The scripts here are `'''` multi-line blocks (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)).

Create the master as an admin, because owner authority is what lets its
scripts debit a depositor's wallet, then set the interest rate:

```text
@create First Orbital Bank
drop First Orbital Bank
@set First Orbital Bank/rate = 5
```

The shared audit-row routine is called as a subroutine by every command.
Its args arrive as `arg0..arg3` (the account id, the verb, the amount, and
the resulting balance); it reads the current rows with
[`V`](../reference/softcode.md#fn-v) (which reads an attribute off `me`,
the bank), appends the new one, and writes the capped list back with
[`set_attr`](../reference/softcode.md#fn-set_attr):

```text
@set First Orbital Bank/log_row = '''
k = 'log_' + arg0
row = f'{arg1} {arg2} -> balance {arg3}'
set_attr(me, k, (V(k, []) + [row])[-10:])  # keep only the newest ten rows
result = 1
'''
```

`bank` prints a statement on demand: the balance first, then each audit
row, reaching the player with [`pemit`](../reference/softcode.md#fn-pemit):

```text
@set First Orbital Bank/cmd_bank = '''
$bank:
pemit(enactor, f"Account balance: {V('acct_' + enactor.id, 0)} credits.")
for row in V('log_' + enactor.id, []):
    pemit(enactor, '  ' + row)
'''
```

`deposit <amount>` moves credits from the wallet into the vault, then
bumps the ledger with [`incr`](../reference/softcode.md#fn-incr) (which
adds to an attribute on `me` and returns the new value), records the
holder in `members`, and logs the row. All of that sits inside the `if`,
so a refused transfer leaves every one of the ledger writes unrun:

```text
@set First Orbital Bank/cmd_deposit = '''
$deposit *:
amt = int(arg0)
bal = V('acct_' + enactor.id, 0) + amt
if amt > 0 and transfer_credits(enactor, me, amt):  # false, and nothing moves, if the wallet is short
    incr('acct_' + enactor.id, amt)
    set_attr(me, 'members', sorted(set(V('members', []) + [enactor.id])))  # remember this holder for the interest tick
    eval_attr(me, 'log_row', enactor.id, 'deposit', amt, bal)
    pemit(enactor, f'Deposited {amt} credits. Balance: {bal}.')
else:
    pemit(enactor, 'Your wallet cannot cover that.')
'''
```

`withdraw <amount>` is the mirror image, gated on the ledger balance
rather than the wallet, and it pays out of the vault with a matching
[`decr`](../reference/softcode.md#fn-decr):

```text
@set First Orbital Bank/cmd_withdraw = '''
$withdraw *:
amt = int(arg0)
bal = V('acct_' + enactor.id, 0)
if 0 < amt <= bal and transfer_credits(me, enactor, amt):  # gated on the ledger balance, not the wallet
    decr('acct_' + enactor.id, amt)
    eval_attr(me, 'log_row', enactor.id, 'withdraw', amt, bal - amt)
    pemit(enactor, f'Withdrew {amt} credits. Balance: {bal - amt}.')
else:
    pemit(enactor, 'Insufficient funds on account.')
'''
```

`xfer <amount> to <player>` moves ledger to ledger, so no credits move and
the recipient can be anywhere. [`get(arg1)`](../reference/softcode.md#fn-get)
resolves the recipient globally by name,
[`has_tag`](../reference/softcode.md#fn-has_tag) confirms it is a player,
both sides get an audit row via [`name`](../reference/softcode.md#fn-name),
and the recipient gets a `pemit` wherever they stand:

```text
@set First Orbital Bank/cmd_xfer = '''
$xfer * to *:
amt = int(arg0)
who = get(arg1)
bal = V('acct_' + enactor.id, 0)
if who is not None and has_tag(who, 'player') and 0 < amt <= bal:  # 'is not None' is an identity check, not '=='
    decr('acct_' + enactor.id, amt)
    incr('acct_' + who.id, amt)
    set_attr(me, 'members', sorted(set(V('members', []) + [who.id])))
    eval_attr(me, 'log_row', enactor.id, 'transfer to ' + name(who), amt, bal - amt)
    eval_attr(me, 'log_row', who.id, 'transfer from ' + name(enactor), amt, V('acct_' + who.id, 0))
    pemit(who, f'{name(enactor)} wires you {amt} credits at First Orbital Bank.')
    pemit(enactor, f'Wired {amt} credits.')
else:
    pemit(enactor, 'No such account holder, or insufficient funds.')
'''
```

Interest runs on a heartbeat. Attach the `script_ticker` behavior, then
write `on_tick` as a loop over the roster: for each member, compute the
gain once, and when it is positive, mint the reserve, raise the ledger,
and log the row:

```text
@behavior First Orbital Bank = script_ticker, interval:150
@set First Orbital Bank/on_tick = '''
for pid in V('members', []):
    bal = V('acct_' + pid, 0)
    gain = bal * V('rate', 0) // 100
    if gain > 0:
        adjust_credits(me, gain)  # mint reserve to back the interest, so the vault still covers the ledger
        incr('acct_' + pid, gain)
        eval_attr(me, 'log_row', pid, 'interest', gain, bal + gain)
'''
```

## Try it

```text
@eval adjust_credits(me, 400)
deposit 300                 -> Deposited 300 credits. Balance: 300.
bank                        -> the balance plus your first audit row
withdraw 50                 -> Withdrew 50 credits. Balance: 250.
xfer 100 to Bob             -> Wired 100 credits.  (Bob can be anywhere)
@tr First Orbital Bank/on_tick
bank                        -> "interest 7 -> balance 157" in the trail
```

`@tr First Orbital Bank/on_tick` fires the interest attribute's body
directly, with the bank as executor, which is how you exercise a ticker
without waiting 150 seconds for the heartbeat. Bob, wherever he stands,
sees "Vala wires you 100 credits at First Orbital Bank," and his next
`bank` at the terminal shows both the balance and the `transfer from Vala`
row.

## Going further

- **Withdrawal fees.** Pay out `amt`, debit the ledger `amt + amt // 100`,
  a 1% credit sink, which player economies need more than faucets.
- **Loans.** Let `withdraw` take the ledger to `-limit`, and make the
  interest tick *charge* negative balances (skip the minting on the way
  down, since burning is `adjust_credits(me, -cost)` on the borrower's
  row).
- **Statements as items.**
  [`create_obj('a bank statement')`](../reference/softcode.md#fn-create_obj)
  holding a copy of the log rows in its description, carryable and
  droppable evidence.
- **Branch terminals.** More `@create`d terminals whose commands
  `eval_attr` against the *one* bank master, so accounts become
  station-wide while state stays in one place. That split is exactly the
  [ATM terminal](004_atm_terminal.md) build.
