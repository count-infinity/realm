# 086. Multi-denomination currency

> Checklist item 86 — [now] — *credits() as canonical value, coin items, $exchange math*

**What you'll build:** physical cash — bars, chits and chips — layered over
the engine's wallet integer, with automatic change-making whenever money
changes shape, and total value conserved to the credit.

**Concepts:** `credits()` as the canonical store of value; coin objects as
*representations* (two attributes, name derived); `$`-command triggers on an
admin-owned master; `eval_attr` function attributes; `create_obj`/
`destroy_obj`; greedy change-making with `divmod`.

## How it works

REALM already has money: every object carries a `credits` balance that the
`credits`/`pay`/`buy`/`sell` builtins and the softcode money functions all
share. That integer stays **canonical** — this tutorial never replaces it,
because two parallel currencies is how economy bugs are born.

What we add is a *physical representation*. A coin stack is an ordinary
object tagged `cash` holding exactly two numbers, `denom` and `count`; its
name ("a stack of 3 ten-credit chits") is *derived from* the numbers, never
parsed back out of the string. Worth = `denom * count`, always.

The machinery lives on **the Mint**, a master object you create as a
wizard. Its scripts therefore run with *your* authority — which is what
lets `cashout` pull credits out of the enactor's wallet and park them on
the Mint as a **reserve**. Every coin in circulation is backed one-for-one
by reserve credits, so `pocket` (melt coins back into the wallet) can
always pay out, and at any moment `credits(mint) == face value of all
coins`. Conservation is a checkable invariant, not a hope.

Change-making is a function attribute, `change`: a greedy walk down the
100/10/1 ladder via `divmod`. Greedy is optimal because each denomination
divides the one above it. `$cashout`, and the `$exchange` re-mint, both
call it with `eval_attr(me, 'change', amount)` — Penn's `u()`, one
arithmetic routine shared by every command that needs coins counted out.

## Build it

The room and the master (as an admin — the Mint inherits your authority):

```text
@dig Market Square
@teleport Market Square
@create the Mint
drop the Mint
```

The change-maker, as a function attribute. `divmod(a, b)` returns
quotient and remainder, so two calls walk the whole ladder; the result is
a list of `[count, denomination, name]` rows:

```text
@set the Mint/change = b, r = divmod(int(arg0), 100); c, u = divmod(r, 10); result = [[b, 100, 'hundred-credit bar'], [c, 10, 'ten-credit chit'], [u, 1, 'one-credit chip']]
```

`cashout <amount>` — wallet to coins. `transfer_credits(enactor, me, amt)`
moves the credits into the reserve (it returns False, changing nothing, if
the wallet is short); then one comprehension mints a stack per non-zero
rung. Note the `for g, a in [[ok, amt]] if g` opener — a comprehension
can't see names assigned earlier in the script, so we bind `ok` and `amt`
in through the first clause; and note `for c in [create_obj(...)]`, which
binds the new stack so we can set both attributes on it:

```text
@set the Mint/cmd_cashout = $cashout *:amt = int(arg0); ok = amt > 0 and transfer_credits(enactor, me, amt); pemit(enactor, 'The Mint counts out ' + str(amt) + ' credits in coin.' if ok else 'Your wallet cannot cover that.'); [(set_attr(c, 'denom', d), set_attr(c, 'count', n)) for g, a in [[ok, amt]] if g for n, d, nm in eval_attr(me, 'change', a) if n for c in [create_obj('a stack of ' + str(n) + ' ' + nm + ('s' if n > 1 else ''), tags=['thing', 'cash'], location=enactor)]]
```

`pocket` — coins to wallet. Sum the face value of every `cash` object the
enactor carries, pay it out of the reserve, and only then destroy the
stacks (gated on the transfer succeeding, so a failed payout can never
vaporize coins):

```text
@set the Mint/cmd_pocket = $pocket:total = sum(get_attr(o, 'denom', 0) * get_attr(o, 'count', 0) for o in contents(enactor) if has_tag(o, 'cash')); ok = transfer_credits(me, enactor, total); [destroy_obj(o) for g in [ok] if g for o in contents(enactor) if has_tag(o, 'cash')]; pemit(enactor, 'You pocket ' + str(total) + ' credits.' if ok else 'You are not carrying any coin.')
```

`exchange` — melt and re-mint. Because value is just an integer, "make
change" needs no special cases: total the coins, destroy them, mint the
same total optimally. The wallet is never touched, so the reserve
invariant holds throughout:

```text
@set the Mint/cmd_exchange = $exchange:total = sum(get_attr(o, 'denom', 0) * get_attr(o, 'count', 0) for o in contents(enactor) if has_tag(o, 'cash')); [destroy_obj(o) for t in [total] if t for o in contents(enactor) if has_tag(o, 'cash')]; [(set_attr(c, 'denom', d), set_attr(c, 'count', n)) for t in [total] if t for n, d, nm in eval_attr(me, 'change', t) if n for c in [create_obj('a stack of ' + str(n) + ' ' + nm + ('s' if n > 1 else ''), tags=['thing', 'cash'], location=enactor)]]; pemit(enactor, 'The Mint remints your coin: same value, fewest pieces.' if total else 'You have no coin to exchange.')
```

## Try it

```text
@eval adjust_credits(me, 137)
credits                     -> You are carrying 137 credits.
cashout 137                 -> The Mint counts out 137 credits in coin.
inventory                   -> 1 bar, 3 chits, 7 chips — greedy change
pocket                      -> You pocket 137 credits.
```

Coins are real objects — droppable, givable, stealable (which wallet
credits never are):

```text
cashout 25
give a stack of 2 ten-credit chits to Bob
```

Bob types `pocket` at the Mint and his wallet grows by 20. And the
re-mint: `cashout 5` three times leaves you three chip stacks; `exchange`
collapses them to one chit and five chips — same 15 credits, fewest
pieces.

## Going further

- **Weight.** `set_attr(c, 'weight', n * d // 100)` at mint time — now
  hauling ten thousand credits in chips is a real decision.
- **A second ladder.** Corp scrip with its own `change2` attribute and an
  exchange-rate spread: `$convert *` pays out 9 credits per 10 scrip.
- **Coin-operated machinery.** A vending machine whose `$insert *` only
  accepts `cash` objects — melt them with the same sum-and-destroy dance,
  no wallet involved.
- **A public reserve window.** `$audit:pemit(enactor, ...)` printing
  `credits(me)` next to the face value of coins in the room — let players
  verify the bank of issue themselves.
