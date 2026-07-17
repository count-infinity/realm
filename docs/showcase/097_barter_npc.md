# 097. Barter NPC

> Checklist item 97 — [now] — *want-list attrs, ON_RECEIVE matching*

**What you'll build:** Rook the Tinker, who has no use for your money:
hand him anything off his want-list and he presses a counter-gift into
your hands on the spot. Item for item, wallets untouched.

**Concepts:** a want-list as a data attribute (`[[want-tag,
counter-gift], ...]`); `give` + `ON_RECEIVE` as the entire trade
interface; **tag matching** so whole categories barter (any
`scrap_metal`-tagged thing, not one blessed item name); counter-gift
delivery via the create-at-self + `teleport_obj` idiom; the push-back
pattern for refusals.

## How it works

A barter NPC is a shopkeeper with the money deleted — which makes it
*simpler*, not harder. There are no prices, no wallet checks, no till:
the whole trade is one `give` and one reaction.

**The want-list is data, matched by tag.** `wants` holds rows of
`[want-tag, counter-gift-name]`. Matching by **tag** rather than name is
the load-bearing choice: tag your world's junk `scrap_metal` and every
bent plate, snapped strut and shredded hull panel is currency here,
without Rook's script ever learning their names. (The shopkeeper's
`value` attr prices *everything*; a barter tag *classifies* everything —
same trick, different axis.)

**`ON_RECEIVE` is the deal.** `give <thing> to Rook the Tinker` works
because Rook is `npc`-tagged, and his recipient-side hook fires after
the item lands. This build finds the new arrival as whatever he holds
that isn't stamped `kept` (the coat-check idiom); `adata('item')` now
names it directly. The
script walks the want-list for the first row whose tag the item
carries:

- **Match:** stamp the item `kept` (Rook hoards his takings — the stamp
  is also what keeps it out of the *next* trade's "new arrival" scan),
  then conjure the counter-gift. `create_obj` refuses to create
  directly into another player's pockets — the documented engine
  behavior — so Rook crafts it *in his own hands* and `teleport_obj`s
  it over: handing over what you hold is always yours to do.
- **No match:** the item goes straight back (`teleport_obj` again) with
  a spoken refusal. A barter counter that silently keeps non-matching
  goods is a theft bug, the same rule every escrow build in this arc
  follows.

**Wallets are never touched.** No `transfer_credits`, no
`adjust_credits`, no `pay` anywhere in the build — the trade is real
goods for real goods, which also means it works for characters with
zero credits, which is exactly who barter economies are for.

## Build it

The yard, the tinker, and his list — two rows: scrap buys a cloak,
power cells buy a lantern:

```text
@dig The Tinker Yard
@teleport The Tinker Yard
@create Rook the Tinker
@tag Rook the Tinker = npc
drop Rook the Tinker
@set Rook the Tinker/wants = [["scrap_metal", "a patched thermal cloak"], ["power_cell", "a tinkered lantern"]]
```

The menu, for the asking:

```text
@set Rook the Tinker/cmd_wants = $wants:pemit(enactor, 'Rook trades goods for goods. No coin.'); [pemit(enactor, f'  anything {w} -> {g}') for w, g in V('wants', [])]
```

And the deal itself — his receive hook:

```text
@set Rook the Tinker/on_receive = stuff = [o for o in contents(me) if not has_attr(o, 'kept')]; it = stuff[0] if stuff else None; deal = [[w, g] for itx in [it] for w, g in V('wants', []) if itx is not None and has_tag(itx, w)]; [(set_attr(x, 'kept', 1), teleport_obj(c, enactor), say(f'A fair swap: {name(c)} for your {name(x)}.')) for ok, x, d in [[bool(deal), it, deal]] if ok for w, g in [d[0]] for c in [create_obj(g, tags=['thing'], location=me)]]; (teleport_obj(it, enactor), say('No use to me. Ask me what I want.')) if it is not None and not deal else None
```

Something to trade with (any object carrying the tag qualifies — that's
the point):

```text
@create a bent hull plate
@tag a bent hull plate = scrap_metal
```

## Try it

```text
wants
    Rook trades goods for goods. No coin.
      anything scrap_metal -> a patched thermal cloak
      anything power_cell -> a tinkered lantern

give a bent hull plate to Rook the Tinker
    Rook the Tinker says, "A fair swap: a patched thermal cloak for
    your a bent hull plate."
```

The cloak is in your pack, the plate is in Rook's hoard, and — check
`credits` before and after — not one credit moved on either side. Hand
him something off-list (a ration bar, your boots) and it comes straight
back: "No use to me. Ask me what I want." Any *other*
`scrap_metal`-tagged thing in the world trades just the same, without
touching his script.

## Going further

- **Exchange rates.** Rows of `[want-tag, count, gift]` and a `pile_<tag>`
  counter on Rook: stamp arrivals, count them, and only gift when the
  pile hits `count` — "three scrap for one cloak" in one extra attr.
- **Finite stock.** Give the gift rows a `stock` count that decrements
  to refusal ("Come back next week.") and let a `script_ticker`
  replenish it — the shopkeeper restock heartbeat (063) without money.
- **Want what he lacks.** Have `on_receive` re-derive the want-list from
  what he's short of (`len([o for o in contents(me) if has_tag(o, w)])`)
  — a tinker who stops wanting scrap once he's drowning in it is a tiny
  economy simulation.
- **Chained crafting.** Make the counter-gift itself tagged for the
  *next* NPC's want-list — a barter chain across the zone is a quest
  line with no quest system, the trade-up folktale as world design.
