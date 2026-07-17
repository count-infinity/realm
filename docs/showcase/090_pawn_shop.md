# 090. Pawn shop

> Checklist item 90 — [now] — *db.value valuation, expire() buyback windows*

**What you'll build:** Honest Yaro's pawn counter: it advances credits
against anything you carry at a percentage of its `value`, holds the item
for a buyback window, charges a vig on redemption — and when the window
closes, a persistent timer forfeits the pledge onto the sale rack, where
anyone can buy it.

**Concepts:** valuation from a `value` attribute with an explicit
fallback; escrow via `move_to`; pledge rows keyed by item id
(`pledge_<id>`); the **expiring companion token** — `expire()` +
`ON_EXPIRE` on a shop-minted tag, because `expires_at` destroys its
carrier and the pawned item must survive its own deadline; deadlines
enforced twice (arithmetic *and* the timer); the vig as a credit sink.

## How it works

**Valuation is an attribute, honestly defaulted.** The loan quotes
`get_attr(item, 'value', 0)`, and anything unvalued falls back to the
counter's flat `fallback` (5 credits) — a pawn shop that refused
unappraised goods would refuse most of a MUD. The advance is
`value * rate%`; redemption costs the loan plus a 10% vig, so every
round trip burns player credits into the shop — a sink, which economies
need more than faucets.

**The pledge is a ledger row; the deadline is a timer *and* a number.**
Pawning escrows the item into the counter's inventory (`move_to`, the
auction pattern — admin authority takes the enactor's item because they
asked) and writes `pledge_<item-id> = {owner, loan, due}`. Redemption
checks `now() <= due` by arithmetic — the toll-gate doctrine: state that
expires by comparison needs no cleanup to be *correct*. But forfeiture
should also *happen* — the rack should fill without waiting for the
debtor to show up and be refused. That's `expire()`.

**Why the timer rides a companion tag, not the item.** `expire(obj, s)`
fires `ON_EXPIRE` and then **destroys the object** — an `ON_EXPIRE`
handler survives only by clearing its own `expires_at`. Destroying the
pledge would be a strange pawn shop. So the counter mints a **pawn tag**
per pledge — a shop-owned token carrying the item's id — and the *tag*
expires: its `ON_EXPIRE` runs with the shop owner's authority, deletes
the ledger row, tags the item `forfeit` onto the sale rack, announces it,
and then dies right on schedule, its work done. One wrinkle: the tag's
handler is set by *script*, and quoting code inside code is misery — so
the handler text lives once on the counter (`tag_expire`) and pawning
*copies* it onto each tag with
`set_attr(t, 'on_expire', V('tag_expire'))`. (Inside that
handler `me` is the **tag**, in the counter's pockets, not the counter —
the longhand `get_attr(me, 'item')` keeps that switch visible where a
bare `V('item')` would hide it — and it emits with
`remit(loc(shop), ...)`, not `here`, which would whisper to the shelf.)

**The rack closes the loop.** Forfeited goods are ordinary escrowed
items with a `forfeit` tag; `rack` lists them at full `value` and
`rack buy` sells them — the shop "sells anything back," including what
its debtors abandoned. (Not `pawn buy`: `$`-patterns are tried in
attribute order, so the earlier `$pawn *` would swallow it — keep a
verb family's prefixes from shadowing each other.)

## Build it

The counter, its terms, and a float (it must be able to advance loans):

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

The forfeit handler, written once as plain text on the counter — the
code each pawn tag will run when its window closes:

```text
@set the Pawn Counter/tag_expire = shop = get('the Pawn Counter'); iid = get_attr(me, 'item'); row = get_attr(shop, 'pledge_' + iid); (del_attr(shop, 'pledge_' + iid), add_tag(get('#' + iid), 'forfeit'), remit(loc(shop), f"Yaro shrugs and moves {name(get('#' + iid))} to the sale rack.")) if row else None
```

`pawn <item>` — appraise, escrow, advance the loan, open the ledger row,
and mint the expiring tag (the `for g, l in [[ok, loan]] if g` opener is
the standard comprehension-binding trick):

```text
@set the Pawn Counter/cmd_pawn = $pawn *:itm = [o for o in contents(enactor) if name(o).lower() == arg0.strip().lower()]; val = (get_attr(itm[0], 'value', 0) or V('fallback', 5)) if itm else 0; loan = max(1, val * V('rate', 60) // 100); ok = bool(itm) and transfer_credits(me, enactor, loan); [(move_to(o, me), set_attr(me, 'pledge_' + o.id, {'owner': enactor.id, 'owner_name': name(enactor), 'loan': l, 'due': now() + V('window', 300)}), set_attr(t, 'item', o.id), set_attr(t, 'on_expire', V('tag_expire')), expire(t, V('window', 300)), pemit(enactor, f"Yaro counts out {l} credits against your {name(o)}. Redeem it for {l + max(1, l // 10)} within {V('window', 300)} seconds.")) for g, l, lst in [[ok, loan, itm]] if g for o in [lst[0]] for t in [create_obj(f'a pawn tag ({name(o)})', tags=['thing', 'pawn_tag'], location=me)]]; pemit(enactor, 'You are not carrying that, or the counter cannot cover the loan.') if not ok else None
```

`redeem <item>` — your pledge, inside the window, loan plus vig. The
deadline is checked by arithmetic even if the tag hasn't been reaped
yet; redemption also retires the tag (a live timer for a closed pledge
would forfeit a redeemed item's ghost row — the double bookkeeping must
die together):

```text
@set the Pawn Counter/cmd_redeem = $redeem *:itm = [o for o in contents(me) if name(o).lower() == arg0.strip().lower() and has_attr(me, 'pledge_' + o.id)]; row = V('pledge_' + itm[0].id) if itm else None; cost = row['loan'] + max(1, row['loan'] // 10) if row else 0; ok = bool(row) and row['owner'] == enactor.id and now() <= row['due'] and transfer_credits(enactor, me, cost); [(teleport_obj(o, enactor), del_attr(me, 'pledge_' + o.id), [destroy_obj(t) for t in contents(me) if has_tag(t, 'pawn_tag') and get_attr(t, 'item') == o.id], pemit(enactor, f'You redeem your {name(o)} for {c} credits.')) for g, o, c in [[ok, itm[0] if itm else None, cost]] if g]; pemit(enactor, 'No such pledge of yours, the window has closed, or you cannot cover it.') if not ok else None
```

The sale rack — browse and buy forfeits at full value:

```text
@set the Pawn Counter/cmd_rack = $rack:pemit(enactor, 'On the sale rack:'); [pemit(enactor, f"  {name(o)} - {max(1, get_attr(o, 'value', 0) or V('fallback', 5))} credits") for o in contents(me) if has_tag(o, 'forfeit')]
@set the Pawn Counter/cmd_buyrack = $rack buy *:itm = [o for o in contents(me) if has_tag(o, 'forfeit') and name(o).lower() == arg0.strip().lower()]; price = max(1, get_attr(itm[0], 'value', 0) or V('fallback', 5)) if itm else 0; ok = bool(itm) and transfer_credits(enactor, me, price); [(remove_tag(o, 'forfeit'), teleport_obj(o, enactor), pemit(enactor, f'Yours for {p} credits. No refunds.')) for g, p, lst in [[ok, price, itm]] if g for o in [lst[0]]]; pemit(enactor, 'Not on the rack, or you cannot cover it.') if not ok else None
```

## Try it

With a `value = 40` chrono watch in your pack:

```text
pawn a chrono watch     -> "Yaro counts out 24 credits against your
                            a chrono watch. Redeem it for 26 within 300 seconds."
redeem a chrono watch   -> "You redeem your a chrono watch for 26 credits."
```

The watch is back; Yaro kept the 2-credit vig. Pawn it again and let the
window lapse: the tag's timer fires, the room hears "Yaro shrugs and
moves a chrono watch to the sale rack," and your `redeem` now gets "the
window has closed." `rack` lists it at 40; anyone can `rack buy a chrono
watch` — including you, at the full sting.

An unvalued item ("a mystery box") pawns against the fallback: 3 credits
advanced (60% of 5).

## Going further

- **Interest by the day.** Store `pawned_at` in the row and scale the
  redemption `cost` by `(now() - pawned_at) // 86400` — the longer it
  sits, the worse the vig.
- **A grace knock.** Have the tag's `on_expire` *renew itself once*
  (`expire(me, 60)` plus a `warned` attr) and `pemit` the owner a last
  chance before the second expiry forfeits — the timer-that-renews
  pattern from the engine's expiry contract.
- **Fence risks.** Tag stolen goods `hot` at theft time and give the
  counter a `1 in rand(1, 4)` chance to refuse them loudly — pawn shops
  are where loot goes, and where guards look.
- **Haggling the appraisal.** Gate a better `rate` behind a
  `contest(enactor, 'merchant', me, 'merchant')` quick contest — social
  skills touching the economy, the disposition-shop trick in miniature.
