# 090. Pawn shop

> Checklist item 90 ([now]): *db.value valuation, expire() buyback windows*

**What you'll build:** Honest Yaro's pawn counter. It advances credits against
anything you carry at a percentage of the item's `value`, holds the item for a
buyback window, charges a small vig on redemption, and when the window closes a
persistent timer forfeits the pledge onto a sale rack that anyone can buy from.

**Concepts:** valuation from a `value` attribute with an explicit fallback;
escrow with [`move_to`](../reference/softcode.md#fn-move_to); pledge rows keyed
by item id (`pledge_<id>`); an expiring companion tag
([`expire`](../reference/softcode.md#fn-expire) plus `ON_EXPIRE`) because the
timer must not destroy the pawned item; deadlines enforced twice, by arithmetic
and by the timer; the vig as a credit sink.

## How it works

The counter is one dropped object holding a float of credits and a row per
active pledge. Pawning appraises an item, pays out a loan, escrows the item,
and starts a countdown. Redeeming inside the window returns the item for the
loan plus a vig. When the countdown elapses the pledge forfeits to a sale rack.
This section explains how the counter prices goods, how it records a pledge,
why the forfeit timer lives on a separate token, and how the rack sells
forfeits without colliding with the pawn command.

### How the counter values what you carry

The loan quotes [`get_attr`](../reference/softcode.md#fn-get_attr)`(item,
'value', 0)`, and anything unvalued falls back to the counter's flat `fallback`
of 5 credits, because a pawn shop that refused unappraised goods would refuse
most of a MUD. The advance is `value` times `rate` percent. Redemption costs
the loan plus a vig of `max(1, loan // 10)`, roughly a tenth of the loan and
never less than one credit, so every round trip burns a few player credits into
the shop. That makes the counter a credit sink, which economies need more than
faucets (the [bank](087_bank_accounts.md) turns the same idea into a withdrawal
fee).

### How a pledge is recorded, and why the deadline is a number and a timer

Pawning escrows the item into the counter's own inventory with
[`move_to`](../reference/softcode.md#fn-move_to), the same owner-authority move
the native [shopkeeper](063_shopkeeper.md) uses to hand goods across, and writes
a row `pledge_<item-id>` holding the owner, the loan, and the due time.
Redemption checks `now() <= due` by arithmetic, so a pledge whose window has
passed is refused even if nothing has cleaned it up yet. But forfeiture should
also happen on its own: the rack should fill when the window closes, without
waiting for the debtor to return and be turned away. That second, active
deadline is an [`expire`](../reference/softcode.md#fn-expire) timer.

### Why the timer rides a companion tag

`expire(obj, seconds)` fires the object's `ON_EXPIRE` and then destroys the
object, unless the handler pushes its own `expires_at` out. Destroying the
pawned item at its deadline would be a strange pawn shop, so the timer cannot
ride the item. Instead the counter mints a small pawn tag per pledge, a
shop-owned token carrying the item's id, and the tag is what expires. Its
`ON_EXPIRE` deletes the pledge row, tags the item `forfeit` where it already
sits in the counter, announces the move to the room, and then the tag dies on
schedule with its work done.

The handler text is written once on the counter as `tag_expire`, and pawning
copies it onto each fresh tag with
[`set_attr`](../reference/softcode.md#fn-set_attr)`(t, 'on_expire',
V('tag_expire'))`, which keeps you from quoting code inside code. Inside the
handler `me` is the tag, sitting in the counter's inventory, not the counter
itself, so it reads the item id with the longhand `get_attr(me, 'item')` and
emits with [`remit`](../reference/softcode.md#fn-remit)`(loc(shop), ...)` to
reach the room rather than the inside of the counter.

### How the tag forfeits only its own pledge

`ON_EXPIRE` reaches every object in the counter, not only the tag whose timer
fired, so with two pledges open the expiry of one tag would otherwise run the
other tag's handler and forfeit an item still inside its window. The handler
opens with a [`target is me`](../reference/softcode.md#guard-on-target) guard,
an identity check written with `is`, so that only the tag that actually expired
acts on its pledge.

### How the rack sells forfeits without colliding with pawn

Forfeited goods are ordinary escrowed items wearing a `forfeit` tag. `rack`
lists them at full `value` and `rack buy <item>` sells them, so the counter
sells anything back, including what its debtors abandoned. The buy verb is
`rack buy`, not `pawn buy`: `$`-commands are matched in attribute order and the
first match wins, so a `$pawn *` defined earlier would swallow `pawn buy watch`
before a `$pawn buy *` was ever tried. Giving the rack its own verb keeps the
two families from shadowing each other. Because `$rack` carries no wildcard it
matches only the bare word, so `rack buy watch` falls through to `$rack buy *`.

## Build it

The counter, its terms, and a float so it can advance loans:

```text
@dig Yaros Den
@teleport Yaros Den
@create the Pawn Counter
drop the Pawn Counter
@set the Pawn Counter/rate = 60
@set the Pawn Counter/window = 300
@set the Pawn Counter/fallback = 5
@eval adjust_credits(get('the Pawn Counter'), 1000)
```

The forfeit handler, written once on the counter as the code each tag will run
when its window closes. It guards on `target is me`, reads the item id from the
tag, and if the pledge row is still open it deletes the row, tags the item
`forfeit`, and announces the move to the room:

```text
@set the Pawn Counter/tag_expire = '''
if target is me:  # ON_EXPIRE reaches every object in the counter; act only for the expiring tag
    shop = get('the Pawn Counter')
    iid = get_attr(me, 'item')          # me is the tag, so the item id lives on it
    row = get_attr(shop, 'pledge_' + iid)
    if row:
        del_attr(shop, 'pledge_' + iid)
        add_tag(get('#' + iid), 'forfeit')
        remit(loc(shop), f"Yaro shrugs and moves {name(get('#' + iid))} to the sale rack.")
'''
```

`pawn <item>` appraises the named item, escrows it, advances the loan, opens
the pledge row, and mints the expiring tag with the handler copied onto it:

```text
@set the Pawn Counter/cmd_pawn = '''
$pawn *:
itm = [o for o in contents(enactor) if name(o).lower() == arg0.strip().lower()]
if not itm:
    pemit(enactor, 'You are not carrying that, or the counter cannot cover the loan.')
else:
    o = itm[0]
    val = get_attr(o, 'value', 0) or V('fallback', 5)   # unvalued goods pawn at the fallback
    loan = max(1, val * V('rate', 60) // 100)
    if transfer_credits(me, enactor, loan):
        move_to(o, me)
        set_attr(me, 'pledge_' + o.id, {'owner': enactor.id, 'owner_name': name(enactor), 'loan': loan, 'due': now() + V('window', 300)})
        t = create_obj(f'a pawn tag ({name(o)})', tags=['thing', 'pawn_tag'], location=me)
        set_attr(t, 'item', o.id)
        set_attr(t, 'on_expire', V('tag_expire'))   # copy the counter's handler onto this tag
        expire(t, V('window', 300))
        pemit(enactor, f"Yaro counts out {loan} credits against your {name(o)}. Redeem it for {loan + max(1, loan // 10)} within {V('window', 300)} seconds.")
    else:
        pemit(enactor, 'You are not carrying that, or the counter cannot cover the loan.')
'''
```

`redeem <item>` returns your pledge inside the window for the loan plus the
vig. The window is checked by arithmetic even if the tag has not been reaped
yet, and a successful redemption also destroys the tag so a live timer cannot
later forfeit a row that is already settled:

```text
@set the Pawn Counter/cmd_redeem = '''
$redeem *:
itm = [o for o in contents(me) if name(o).lower() == arg0.strip().lower() and has_attr(me, 'pledge_' + o.id)]
row = V('pledge_' + itm[0].id) if itm else None
cost = row['loan'] + max(1, row['loan'] // 10) if row else 0
ok = bool(row) and row['owner'] == enactor.id and now() <= row['due'] and transfer_credits(enactor, me, cost)
if ok:
    o = itm[0]
    teleport_obj(o, enactor)
    del_attr(me, 'pledge_' + o.id)
    for t in list(contents(me)):
        if has_tag(t, 'pawn_tag') and get_attr(t, 'item') == o.id:
            destroy_obj(t)
    pemit(enactor, f'You redeem your {name(o)} for {cost} credits.')
else:
    pemit(enactor, 'No such pledge of yours, the window has closed, or you cannot cover it.')
'''
```

The sale rack lists forfeits at full value:

```text
@set the Pawn Counter/cmd_rack = '''
$rack:
pemit(enactor, 'On the sale rack:')
for o in contents(me):
    if has_tag(o, 'forfeit'):
        pemit(enactor, f"  {name(o)} - {max(1, get_attr(o, 'value', 0) or V('fallback', 5))} credits")
'''
```

`rack buy <item>` sells one at full value, then peels off the `forfeit` tag and
hands it over:

```text
@set the Pawn Counter/cmd_buyrack = '''
$rack buy *:
itm = [o for o in contents(me) if has_tag(o, 'forfeit') and name(o).lower() == arg0.strip().lower()]
price = max(1, get_attr(itm[0], 'value', 0) or V('fallback', 5)) if itm else 0
if itm and transfer_credits(enactor, me, price):
    o = itm[0]
    remove_tag(o, 'forfeit')
    teleport_obj(o, enactor)
    pemit(enactor, f'Yours for {price} credits. No refunds.')
else:
    pemit(enactor, 'Not on the rack, or you cannot cover it.')
'''
```

## Try it

With a `value = 40` chrono watch in your pack:

```text
> pawn a chrono watch
Yaro counts out 24 credits against your a chrono watch. Redeem it for 26 within 300 seconds.

> redeem a chrono watch
You redeem your a chrono watch for 26 credits.
```

The watch is back and Yaro kept the 2 credit vig (24 loaned, 26 returned). Pawn
it again and let the window lapse: the tag's timer fires on the next world
tick, the room hears "Yaro shrugs and moves a chrono watch to the sale rack,"
and `redeem` now answers "the window has closed." A bare `rack` lists the watch
at 40, and anyone can `rack buy a chrono watch`, including you, at the full
price.

An unvalued item such as a mystery box pawns against the fallback: 3 credits
advanced, which is 60 percent of 5.

## Going further

- **Interest by the day.** Store a `pawned_at` stamp in the row and scale the
  redemption `cost` by `(now() - pawned_at) // 86400`, so the longer a pledge
  sits the worse the vig.
- **A grace knock.** Have the tag's `on_expire` renew itself once with
  `expire(me, 60)` and a `warned` flag, and `pemit` the owner a last chance
  before the second expiry forfeits.
- **Fence risks.** Tag stolen goods `hot` at theft time and give the counter a
  chance to refuse them loudly, since pawn shops are where loot goes and where
  guards look.
- **Haggling the appraisal.** Gate a better `rate` behind a `contest(enactor,
  'merchant', me, 'merchant')` quick contest, so social skill touches the
  payout.
