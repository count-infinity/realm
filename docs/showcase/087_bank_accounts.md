# 087. Bank accounts

> Checklist item 87 — [now] — *ledger attrs, transfer_credits, on_tick interest, audit logs*

**What you'll build:** a station bank — deposits, withdrawals,
player-to-player wires that reach across the map, interest on a heartbeat,
and a capped per-account audit trail — all attributes on one admin-owned
master object.

**Concepts:** ledger state as attributes (`acct_<id>`); owner authority
(an admin's master may move players' money); `transfer_credits` between
wallet and vault; `script_ticker`/`on_tick` interest with an explicit
minting faucet; audit-log attributes with a cap; `eval_attr` for shared
routines.

## How it works

The bank is one object, **First Orbital Bank**, dropped in a room. Its
state is plain attributes:

- `acct_<player-id>` — the account balance (an integer of ledger money),
- `log_<player-id>` — the newest ten audit rows for that account,
- `members` — every id that ever held an account (the interest tick's
  iteration list — softcode can't enumerate another script's attributes,
  so the roster is kept explicitly),
- `rate` — interest percent per tick.

Two kinds of money meet here and are never confused. **Wallet credits**
are the engine's canonical balance; **ledger numbers** are the bank's
promises. `deposit` converts one to the other with
`transfer_credits(enactor, me, amt)` — the credits physically sit on the
bank object as its *vault reserve* — and `withdraw` converts back. An
internal `xfer` between accounts touches only ledger attributes: no
credits move, which is why the recipient can be on the far side of the
station (or offline). The vault therefore always covers the ledger...

...except for interest, which creates money. The tick makes that faucet
*explicit*: for each member it mints reserve with `adjust_credits(me,
gain)` **and** credits the ledger, so the invariant survives. Delete the
`adjust_credits` call and you have built a bank that can promise more than
it holds — a fine drama hook, a poor default.

Every mutation appends a row to the account's log through one shared
`log_row` function attribute, capped at the newest 10 — unbounded lists on
hot attributes are the classic MUD database leak.

Why is the status command `bank` and not `balance`? Builtins dispatch
before `$`-triggers, and `balance` is already an alias of the `credits`
builtin — it would shadow the trigger every time.

## Build it

The master and its knobs (as an admin — owner authority is what lets it
debit depositors):

```text
@create First Orbital Bank
drop First Orbital Bank
@set First Orbital Bank/rate = 5
```

The shared audit-row routine — args arrive as `arg0..arg3` (who, verb,
amount, resulting balance), and the slice keeps the newest ten:

```text
@set First Orbital Bank/log_row = k = 'log_' + arg0; set_attr(me, k, (get_attr(me, k, []) + [arg1 + ' ' + arg2 + ' -> balance ' + arg3])[-10:]); result = 1
```

`bank` — statement on demand: balance, then the audit rows:

```text
@set First Orbital Bank/cmd_bank = $bank:pemit(enactor, 'Account balance: ' + str(get_attr(me, 'acct_' + enactor.id, 0)) + ' credits.'); [pemit(enactor, '  ' + row) for row in get_attr(me, 'log_' + enactor.id, [])]
```

`deposit <amount>` — wallet to vault, then ledger + roster + audit row.
The `for g, a, b in [[ok, amt, bal]] if g` opener binds the earlier
results into the comprehension (scripts' comprehensions can't see
body-level names — the arc's standard trick):

```text
@set First Orbital Bank/cmd_deposit = $deposit *:amt = int(arg0); ok = amt > 0 and transfer_credits(enactor, me, amt); bal = get_attr(me, 'acct_' + enactor.id, 0) + amt; [(set_attr(me, 'acct_' + enactor.id, b), set_attr(me, 'members', sorted(set(get_attr(me, 'members', []) + [enactor.id]))), eval_attr(me, 'log_row', enactor.id, 'deposit', a, b)) for g, a, b in [[ok, amt, bal]] if g]; pemit(enactor, 'Deposited ' + str(amt) + ' credits. Balance: ' + str(bal) + '.' if ok else 'Your wallet cannot cover that.')
```

`withdraw <amount>` — the mirror image, gated on the ledger balance:

```text
@set First Orbital Bank/cmd_withdraw = $withdraw *:amt = int(arg0); bal = get_attr(me, 'acct_' + enactor.id, 0); ok = 0 < amt <= bal and transfer_credits(me, enactor, amt); [(set_attr(me, 'acct_' + enactor.id, b - a), eval_attr(me, 'log_row', enactor.id, 'withdraw', a, b - a)) for g, a, b in [[ok, amt, bal]] if g]; pemit(enactor, 'Withdrew ' + str(amt) + ' credits. Balance: ' + str(bal - amt) + '.' if ok else 'Insufficient funds on account.')
```

`xfer <amount> to <player>` — ledger to ledger. `get(arg1)` resolves the
recipient *globally* by name; both sides get audit rows and the recipient
a `pemit` wherever they are:

```text
@set First Orbital Bank/cmd_xfer = $xfer * to *:amt = int(arg0); who = get(arg1); bal = get_attr(me, 'acct_' + enactor.id, 0); ok = who is not None and has_tag(who, 'player') and 0 < amt <= bal; [(set_attr(me, 'acct_' + enactor.id, b - a), set_attr(me, 'acct_' + w.id, get_attr(me, 'acct_' + w.id, 0) + a), set_attr(me, 'members', sorted(set(get_attr(me, 'members', []) + [w.id]))), eval_attr(me, 'log_row', enactor.id, 'transfer to ' + name(w), a, b - a), eval_attr(me, 'log_row', w.id, 'transfer from ' + name(enactor), a, get_attr(me, 'acct_' + w.id, 0)), pemit(w, name(enactor) + ' wires you ' + str(a) + ' credits at First Orbital Bank.')) for g, a, b, w in [[ok, amt, bal, who]] if g]; pemit(enactor, 'Wired ' + str(amt) + ' credits.' if ok else 'No such account holder, or insufficient funds.')
```

Interest on a heartbeat — per member: mint the reserve, raise the ledger,
log the row. The nested `for bal in [...] for gain in [...]` clauses are
the binding trick again, computing each account's gain once:

```text
@behavior First Orbital Bank = script_ticker, interval:150
@set First Orbital Bank/on_tick = [(adjust_credits(me, gain), set_attr(me, 'acct_' + pid, bal + gain), eval_attr(me, 'log_row', pid, 'interest', gain, bal + gain)) for pid in get_attr(me, 'members', []) for bal in [get_attr(me, 'acct_' + pid, 0)] for gain in [bal * get_attr(me, 'rate', 0) // 100] if gain > 0]
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

Bob — wherever he stands — sees "Vala wires you 100 credits at First
Orbital Bank," and his next `bank` at the terminal shows both the balance
and the `transfer from Vala` row.

## Going further

- **Withdrawal fees.** Pay out `amt`, debit the ledger `amt + amt // 100`
  — a 1% credit sink, which player economies need more than faucets.
- **Loans.** Let `withdraw` take the ledger to `-limit`, and make the
  interest tick *charge* negative balances (skip the minting on the way
  down — burning is `adjust_credits(me, -cost)` on the borrower's row).
- **Statements as items.** `create_obj('a bank statement')` holding a copy
  of the log rows in its description — carryable, droppable evidence.
- **Branch terminals.** More `@create`d terminals whose commands
  `eval_attr` against the *one* bank master — accounts become
  station-wide while state stays in one place.
