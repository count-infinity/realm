# 088. Player-run shop stalls

> Checklist item 88 — [now] — *delegated vendor attrs, on_tick rent, escrow*

**What you'll build:** a rentable market stall: any player can rent it,
stock it from their own pack, chalk their own prices, and collect the
takings — while the market collects rent on a heartbeat and repossesses
the pitch when the takings can't cover it.

**Concepts:** the **delegated-authority boundary** — `$`-verbs on an
admin-owned stall run with the *stall owner's* authority no matter who
types them, so the script itself is the security policy; escrow via
`move_to` into the stall's inventory; an `earnings` ledger attribute
riding on the stall's real credit balance; `script_ticker`/`on_tick`
rent; eviction via `teleport_obj` to an absent player.

## How it works

The interesting question in a player-run shop is not the selling — it's
**who is allowed to do what to an object they don't own**. The stall is
built by an admin, so every `$`-verb on it executes *as the stall, with
the admin's authority* — that's what lets `stall stock` take an item out
of a mortal's pack, `stall buy` debit a stranger's wallet, and the rent
tick reach into anything at all. The renter never gains authority over
the stall; they gain *permissions the script chooses to grant them*.
Every mutating verb therefore opens with the same gate:
`enactor.id == get_attr(me, 'renter')`. The enactor is untrusted input;
the executor's owner is the power; the script is the policy. (The `use`
lock could bar players from the stall's verbs wholesale, but it is
per-object, not per-verb — renter-only *versus* public verbs on one
object must be decided inside the scripts.)

The money model keeps one honest invariant. Buyers'
`transfer_credits(enactor, me, price)` lands on the stall's real balance,
and an `earnings` attribute records how much of that balance is *the
renter's claim*. Rent never moves credits at all: the tick just reduces
`earnings` by the rent and leaves the credits sitting on the stall — so
at any moment `credits(stall) == earnings + accumulated rents`, and the
market's income is whatever the renter can no longer claim.

Goods are **escrowed**: `stall stock` uses `move_to(item, me)` to pull
the item into the stall's inventory (the auction kiosk's pattern — you
can't sell the knife you're still holding), and `stall buy` hands it out
with `teleport_obj`, which the stall may do to its own contents. Pricing
is an attribute stamped *on the escrowed item* (`stall_price`), set by an
admin-authority script at the renter's request — the renter could never
`@set` it themselves.

Rent is due by arithmetic (`now() >= paid_until`), swept by
`script_ticker` + `on_tick`. A tick that finds the takings short doesn't
extend credit: goods and leftover earnings go back to the renter by
`teleport_obj` — which reaches them *wherever they are*, because
eviction shouldn't wait for the evicted.

## Build it

The pitch and the stall, as an admin (the delegation boundary depends on
the stall being admin-owned):

```text
@dig Stall Row
@teleport Stall Row
@create stall three
drop stall three
@set stall three/rent = 20
@set stall three/period = 300
```

`rent stall` — anyone, if it's free. The first period is paid up front
into the stall (the market's opening take); `transfer_credits` doubles as
the affordability check:

```text
@set stall three/cmd_rent = $rent stall:ok = not get_attr(me, 'renter') and transfer_credits(enactor, me, get_attr(me, 'rent', 20)); [(set_attr(me, 'renter', enactor.id), set_attr(me, 'renter_name', name(enactor)), set_attr(me, 'paid_until', now() + get_attr(me, 'period', 300)), set_attr(me, 'earnings', 0), remit(here, name(enactor) + ' rents stall three and shakes out the awning.')) for g in [ok] if g]; pemit(enactor, 'Stall three is yours. Stock it, price it, collect your takings.' if ok else 'The stall is already let, or you cannot cover the rent.')
```

`stall stock <item>` — renter only. The stall (admin authority) takes the
item from the enactor's pack into escrow and stamps a starting price from
its `value`:

```text
@set stall three/cmd_stock = $stall stock *:itm = [o for o in contents(enactor) if name(o).lower() == arg0.strip().lower()]; ok = enactor.id == get_attr(me, 'renter') and bool(itm); [(move_to(o, me), set_attr(o, 'stall_price', max(1, get_attr(o, 'value', 1))), pemit(enactor, name(o) + ' goes on the shelf at ' + str(get_attr(o, 'stall_price', 1)) + ' credits.')) for g in [ok] if g for o in [itm[0]]]; pemit(enactor, 'Only the renter stocks this stall, and only from their own pack.') if not ok else None
```

`stall price <item> = <credits>` — the item that makes the shop
*player-run*: a mortal repricing goods on an object they don't own,
because the admin-authority script agrees to do it for them:

```text
@set stall three/cmd_price = $stall price * = *:itm = [o for o in contents(me) if name(o).lower() == arg0.strip().lower()]; ok = enactor.id == get_attr(me, 'renter') and bool(itm) and int(arg1) > 0; [(set_attr(o, 'stall_price', int(arg1)), remit(here, get_attr(me, 'renter_name', 'The stallholder') + ' chalks a new price: ' + name(o) + ' at ' + str(int(arg1)) + ' credits.')) for g in [ok] if g for o in [itm[0]]]; pemit(enactor, 'Only the renter sets prices here.' if enactor.id != get_attr(me, 'renter') else 'No such item on the shelf, or a bad price.') if not ok else None
```

`stall` — the public shelf:

```text
@set stall three/cmd_shelf = $stall:pemit(enactor, 'stall three, run by ' + get_attr(me, 'renter_name', 'nobody (rent stall to claim it)') + ':'); [pemit(enactor, '  ' + name(o) + ' - ' + str(get_attr(o, 'stall_price', 0)) + ' credits') for o in contents(me) if has_attr(o, 'stall_price')]
```

`stall buy <item>` — any player but the renter. Payment first (the
transfer is the wallet check), then delivery out of escrow, then the
earnings ledger and a receipt to the renter wherever they are:

```text
@set stall three/cmd_buy = $stall buy *:itm = [o for o in contents(me) if has_attr(o, 'stall_price') and name(o).lower() == arg0.strip().lower()]; price = get_attr(itm[0], 'stall_price', 0) if itm else 0; ok = bool(itm) and enactor.id != get_attr(me, 'renter') and transfer_credits(enactor, me, price); [(del_attr(o, 'stall_price'), teleport_obj(o, enactor), set_attr(me, 'earnings', get_attr(me, 'earnings', 0) + p), remit(here, name(enactor) + ' buys ' + name(o) + ' for ' + str(p) + ' credits.'), pemit(get('#' + get_attr(me, 'renter')), 'Your stall sells ' + name(o) + ' for ' + str(p) + ' credits.')) for g, p in [[ok, price]] if g for o in [itm[0]]]; pemit(enactor, 'Not on the shelf, or you cannot cover it.') if not ok else None
```

`stall collect` — the renter draws down their claim:

```text
@set stall three/cmd_collect = $stall collect:e = get_attr(me, 'earnings', 0); ok = enactor.id == get_attr(me, 'renter') and e > 0 and transfer_credits(me, enactor, e); [(set_attr(me, 'earnings', 0), pemit(enactor, 'You pocket ' + str(k) + ' credits in takings.')) for g, k in [[ok, e]] if g]; pemit(enactor, 'No takings to collect, or this is not your stall.') if not ok else None
```

And the rent heartbeat. When rent falls due, it's docked from the
earnings ledger (the credits never move — they *become* the market's);
if the takings can't cover it, the pitch is repossessed and everything —
goods and leftover claim — chases the renter home:

```text
@behavior stall three = script_ticker, interval:60
@set stall three/on_tick = r = get_attr(me, 'renter'); e = get_attr(me, 'earnings', 0); rent = get_attr(me, 'rent', 20); due = bool(r) and now() >= get_attr(me, 'paid_until', 0); (set_attr(me, 'earnings', e - rent), set_attr(me, 'paid_until', get_attr(me, 'paid_until', 0) + get_attr(me, 'period', 300)), pemit(get('#' + r), 'The market takes ' + str(rent) + ' credits rent from your stall takings.')) if due and e >= rent else None; ([teleport_obj(o, get('#' + r)) for o in contents(me) if has_attr(o, 'stall_price')], [del_attr(o, 'stall_price') for o in contents(get('#' + r)) if has_attr(o, 'stall_price')], transfer_credits(me, get('#' + r), e) if e > 0 else None, pemit(get('#' + r), 'Stall three is repossessed for unpaid rent; your goods and takings are returned.'), del_attr(me, 'renter'), del_attr(me, 'renter_name'), set_attr(me, 'earnings', 0), remit(here, 'The market warden strips stall three: TO LET.')) if due and e < rent else None
```

## Try it

As Bob, with 100 credits:

```text
rent stall              -> "Bob rents stall three and shakes out the awning."
stall stock a stimpack  -> a stimpack goes on the shelf at 20 credits.
stall price a stimpack = 35
stall                   -> stall three, run by Bob: a stimpack - 35 credits
```

As Cass: `stall buy a stimpack` — 35 credits leave her wallet, the
stimpack lands in her pack, and Bob (in another room, even) hears "Your
stall sells a stimpack for 35 credits." Bob's `stall collect` pockets 35.
Cass typing `stall price ...` or `stall stock ...` gets "Only the renter
..." — same object, same verbs, different enactor, different answer.

Rent day: `@eval set_attr(get('stall three'), 'paid_until', now() - 1)`
then `@tr stall three/on_tick`. With takings on the ledger the rent is
docked silently; run it again with an empty ledger and the awning comes
down — goods and any leftover claim teleport back to Bob, and the room
hears the warden strip the pitch.

## Going further

- **A row of stalls.** `$`-command search takes the first match in the
  room, so give each pitch its own verb family (`stall2 buy *`, ...) or
  its own alcove room — one stall per room is the classic market street.
- **Market cut on sales.** Dock `earnings` by 5% of each sale instead of
  (or on top of) flat rent — the tax arithmetic lives in one script line.
- **Vacation mode.** A `stall close` verb that hides the shelf
  (`add_tag(me, 'shuttered')`, `$stall buy` refusing) while rent still
  ticks — absence should cost, not crash.
- **The shopkeeper hybrid.** Park an `npc`-tagged assistant behind the
  counter with the engine's native `shopkeeper` behavior (tutorial 063)
  and let the stall's tick re-stock it from the renter's escrow — the
  native `list`/`buy` UI over player-owned goods.
