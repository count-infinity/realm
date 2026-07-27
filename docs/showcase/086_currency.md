# 086. Multi-denomination currency

> Checklist item 86 ([now]): *credits() as canonical value, coin items, $exchange math*

**What you'll build:** physical cash (bars, chits, and chips) layered over
the engine's wallet integer, with automatic change-making whenever money
changes shape and total value conserved to the credit.

**Concepts:** [`credits()`](../reference/softcode.md#fn-credits) as the canonical
store of value; coin objects as *representations* (two attributes, name derived);
`$`-command triggers on an admin-owned master;
[`eval_attr`](../reference/softcode.md#fn-eval_attr) function attributes;
[`create_obj`](../reference/softcode.md#fn-create_obj) /
[`destroy_obj`](../reference/softcode.md#fn-destroy_obj); greedy change-making
with `divmod`.

## How it works

The finished machine is one master object, the Mint, that turns credits into
coins and back. Coins are ordinary items you can drop, give, and steal, yet the
wallet integer stays the single source of truth, and every coin in circulation
is backed one-for-one by credits the Mint holds in reserve. This section
answers four questions: why the wallet stays canonical, what a coin actually
is, how the reserve keeps value conserved, and how one arithmetic routine is
shared by every command.

### Why the wallet stays the source of truth

REALM already has money: every object carries a `credits` balance that the
`credits`/`pay`/`buy`/`sell` builtins and the softcode money functions all
share. That integer stays **canonical**, and this tutorial never replaces it,
because two parallel currencies is how economy bugs are born. The same integer
vault backs the [ATM terminal](004_atm_terminal.md) and the
[bank accounts](087_bank_accounts.md); here we give it a physical face.

### What a coin actually is

A coin stack is an ordinary object tagged `cash` holding exactly two numbers,
`denom` and `count`. Its name ("a stack of 3 ten-credit chits") is *derived
from* those numbers and never parsed back out of the string, so its worth is
always `denom * count`. Storing value as two integers rather than a parsed name
means a stack can never disagree with itself.

### How value stays conserved

The machinery lives on **the Mint**, a master object you create as a wizard, so
its scripts run with *your* authority. That authority is what lets `cashout`
pull credits out of the enactor's wallet with
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits) and park them
on the Mint as a **reserve**. Every coin in circulation is backed one-for-one by
reserve credits, so `pocket` (melt coins back into the wallet) can always pay
out, and at any moment `credits(mint)` equals the face value of all coins.
Conservation is a checkable invariant, not a hope.

Because the Mint is admin-owned, [`create_obj`](../reference/softcode.md#fn-create_obj)
with `location=enactor` mints coins straight into the customer's inventory even
when the customer is a stranger: authority walks the owner chain to the admin,
who controls every player. A mint built by a mortal would instead have to create
the stack in the room and move it, since a script cannot seed objects into a
player it does not control.

### One arithmetic routine, shared

Change-making is a function attribute, `change`: a greedy walk down the
100/10/1 ladder via `divmod`. Greedy is optimal here because each denomination
divides the one above it. Both `$cashout` and the `$exchange` re-mint call it
with [`eval_attr(me, 'change', amount)`](../reference/softcode.md#fn-eval_attr),
a subroutine call, so one arithmetic routine is shared by every command that
counts out coins. `eval_attr` runs with the *caller's* authority and `me` stays
the caller, which is what makes it a subroutine rather than a method that runs
as the attribute's object.

## Build it

The room and the master, built **as an admin** so the Mint inherits your
authority (that is what lets it mint into any player's inventory and debit a
consenting wallet):

```text
@dig Market Square
@teleport Market Square
@create the Mint
drop the Mint
```

The change-maker is a function attribute. `divmod(a, b)` returns the quotient
and remainder together, so two calls walk the whole ladder, and the result is a
list of `[count, denomination, name]` rows:

```text
@set the Mint/change = '''
b, r = divmod(int(arg0), 100)
c, u = divmod(r, 10)
result = [[b, 100, 'hundred-credit bar'], [c, 10, 'ten-credit chit'], [u, 1, 'one-credit chip']]
'''
```

`cashout <amount>` turns wallet credits into coins. First
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits) moves the
credits into the reserve; then, for each non-zero rung the change-maker returns,
one stack is minted and stamped with its two numbers:

```text
@set the Mint/cmd_cashout = '''
$cashout *:
amt = int(arg0)
ok = amt > 0 and transfer_credits(enactor, me, amt)  # False and no coins if the wallet is short
if ok:
    pemit(enactor, f'The Mint counts out {amt} credits in coin.')
    for n, d, nm in eval_attr(me, 'change', amt):
        if n:  # skip empty rungs
            c = create_obj(f"a stack of {n} {nm}{'s' if n > 1 else ''}", tags=['thing', 'cash'], location=enactor)
            set_attr(c, 'denom', d)
            set_attr(c, 'count', n)
else:
    pemit(enactor, 'Your wallet cannot cover that.')
'''
```

`pocket` turns coins back into wallet credits. It sums the face value of every
`cash` object the enactor carries, pays that out of the reserve, and destroys
the stacks only if the payout succeeded, so a failed transfer can never
vaporize coins:

```text
@set the Mint/cmd_pocket = '''
$pocket:
total = sum(get_attr(o, 'denom', 0) * get_attr(o, 'count', 0) for o in contents(enactor) if has_tag(o, 'cash'))
ok = transfer_credits(me, enactor, total)  # total 0 (no coins) makes this False
if ok:
    for o in contents(enactor):
        if has_tag(o, 'cash'):
            destroy_obj(o)
    pemit(enactor, f'You pocket {total} credits.')
else:
    pemit(enactor, 'You are not carrying any coin.')
'''
```

`exchange` melts every coin and re-mints the same total optimally. Because value
is just an integer, making change needs no special cases: total the coins,
destroy them, mint the total back with the fewest pieces. The wallet is never
touched, so the reserve invariant holds throughout:

```text
@set the Mint/cmd_exchange = '''
$exchange:
total = sum(get_attr(o, 'denom', 0) * get_attr(o, 'count', 0) for o in contents(enactor) if has_tag(o, 'cash'))
if total:
    for o in contents(enactor):
        if has_tag(o, 'cash'):
            destroy_obj(o)
    for n, d, nm in eval_attr(me, 'change', total):
        if n:
            c = create_obj(f"a stack of {n} {nm}{'s' if n > 1 else ''}", tags=['thing', 'cash'], location=enactor)
            set_attr(c, 'denom', d)
            set_attr(c, 'count', n)
    pemit(enactor, 'The Mint remints your coin: same value, fewest pieces.')
else:
    pemit(enactor, 'You have no coin to exchange.')
'''
```

## Try it

Fund your wallet with [`adjust_credits`](../reference/softcode.md#fn-adjust_credits),
then cash it all out and pocket it back:

```text
@eval adjust_credits(me, 137)
credits                     -> You are carrying 137 credits.
cashout 137                 -> The Mint counts out 137 credits in coin.
inventory                   -> 1 bar, 3 chits, 7 chips (greedy change)
pocket                      -> You pocket 137 credits.
```

Coins are real objects, so they are droppable, givable, and stealable, which
wallet credits never are:

```text
cashout 25
give a stack of 2 ten-credit chits to Bob
```

Bob types `pocket` at the Mint and his wallet grows by 20, because the reserve
backs the coins wherever they travel. For the re-mint, `cashout 5` three times
leaves you three chip stacks, and `exchange` collapses them to one chit and five
chips: the same 15 credits in the fewest pieces.

## Going further

- **Weight.** Add `set_attr(c, 'weight', n * d // 100)` at mint time, so hauling
  ten thousand credits in chips becomes a real decision.
- **A second ladder.** Corp scrip with its own `change2` attribute and an
  exchange-rate spread: `$convert *` pays out 9 credits per 10 scrip.
- **Coin-operated machinery.** A [vending machine](002_vending_machine.md) whose
  `$insert *` accepts only `cash` objects, melting them with the same
  sum-and-destroy step and no wallet involved.
- **A public reserve window.** `$audit` that prints `credits(me)` next to the
  face value of coins in the room, so players can verify the bank of issue
  themselves.
