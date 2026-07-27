# 097. Barter NPC

> Checklist item 97 ([now]): *want-list attrs, ON_RECEIVE matching*

**What you'll build:** Rook the Tinker, who has no use for your money. Hand
him anything off his want-list and he presses a counter-gift into your hands on
the spot, item for item, with both wallets untouched.

**Concepts:** a want-list as a data attribute (rows of `[want-tag,
counter-gift]`); `give` plus [`ON_RECEIVE`](../reference/softcode.md#lifecycle-hooks)
as the whole trade interface; tag matching, so a whole category barters rather
than one blessed item name; counter-gift delivery by the create-at-self plus
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj) idiom; the push-back
pattern for refusals.

## How it works

A barter NPC is a [shopkeeper](063_shopkeeper.md) with the money deleted, which
makes it simpler rather than harder. There are no prices, no wallet checks, and
no till: the whole trade is one `give` and one reaction. This section walks the
two moving parts, the want-list Rook reads and the receive hook that acts on it,
and says why each takes the shape it does.

### How Rook decides what to take

`wants` holds rows of `[want-tag, counter-gift-name]`, and Rook matches an
offered item by its **tag**, never by its value or its name. That is the
load-bearing choice. Tag your world's junk `scrap_metal` and every bent plate,
snapped strut, and shredded hull panel is currency here, without Rook's script
ever learning their names. The [shopkeeper](063_shopkeeper.md)'s `value`
attribute prices everything on a single numeric axis; a barter tag classifies
everything into buckets instead, and Rook reads no `value` at all.

### How the deal happens

`give <thing> to Rook the Tinker` works because Rook is `npc`-tagged, so `give`
finds him as a recipient. The item lands in his hands, and then his
[`ON_RECEIVE`](../reference/softcode.md#lifecycle-hooks) hook fires as the
after-the-fact reaction (see [action phases](../design/action-phases.md): the
effect ran first, and the hook observes the result). The payload names exactly
what arrived: [`adata('item')`](../reference/softcode.md#event-data-namespace)
is the object Rook was just handed. The hook walks the want-list for the first
row whose tag the item carries with
[`has_tag`](../reference/softcode.md#fn-has_tag), and the two outcomes are the
two branches at the end:

- **A match.** Rook stamps the item `kept` with
  [`set_attr`](../reference/softcode.md#fn-set_attr), so his own takings are
  marked as his, then conjures the counter-gift.
  [`create_obj`](../reference/softcode.md#fn-create_obj) refuses to create
  directly into another player's pockets, because creation is confined to the
  executor's own location or somewhere it controls. So Rook mints the gift in
  his own hands and [`teleport_obj`](../reference/softcode.md#fn-teleport_obj)s
  it across, since handing over what you already hold is always yours to do.
- **No match.** The item goes straight back, again with `teleport_obj`, and
  Rook speaks a refusal. A counter that silently keeps non-matching goods would
  be a theft bug, the same rule every escrow build in this arc follows, such as
  the [job board](094_job_board.md) that bounces the wrong delivery.

### How Rook knows the item was handed to him

`event:on_receive` is heard by every object in the room, not only the recipient
(see [Guard on `target`](../reference/softcode.md#guard-on-target)), so the hook
gates on [`target is me`](../reference/softcode.md#guard-on-target) before it
reacts. Skip that guard and a second trader in the same yard would pay out a
cloak for scrap that was handed to someone else. Write `is`, not `==`: it is an
identity check.

Wallets are never touched anywhere in the build. There is no
`transfer_credits`, no `adjust_credits`, and no `pay`. The trade is real goods
for real goods, which also means it works for a character with zero credits,
who is exactly who a barter economy is for.

## Build it

The yard and the tinker come first. Rook is a plain `npc`-tagged object dropped
into the room, so `give` can find him:

```text
@dig The Tinker Yard
@teleport The Tinker Yard
@create Rook the Tinker
@tag Rook the Tinker = npc
drop Rook the Tinker
```

Give him his want-list as data. `@set` parses JSON, so this saves as a real
list of rows, each `[want-tag, counter-gift]`: scrap buys a cloak, power cells
buy a lantern.

```text
@set Rook the Tinker/wants = [["scrap_metal", "a patched thermal cloak"], ["power_cell", "a tinkered lantern"]]
```

The menu, for the asking. `$wants` is a plain command anyone can type, so it
needs no target guard; it prints the header and then one line per want-row read
off Rook with [`V`](../reference/softcode.md#fn-v), each sent privately with
[`pemit`](../reference/softcode.md#fn-pemit):

```text
@set Rook the Tinker/cmd_wants = '''
$wants:
pemit(enactor, 'Rook trades goods for goods. No coin.')
[pemit(enactor, f'  anything {w} -> {g}') for w, g in V('wants', [])]
'''
```

Now the deal itself, his receive hook. The whole body sits under the
`target is me` guard. Inside it, `it` is the item that arrived, `deal` collects
the counter-gifts of every want-row whose tag `it` carries (the first one
wins), and the `if`/`else` at the end is the two outcomes: swap or hand back.

```text
@set Rook the Tinker/on_receive = '''
if target is me:  # event:on_receive is heard by the whole room, so gate on the target
    it = adata('item')
    deal = [g for w, g in V('wants', []) if has_tag(it, w)]
    if deal:
        set_attr(it, 'kept', 1)  # mark the takings as Rook's own
        gift = create_obj(deal[0], location=me)  # in his own hands; create_obj refuses a stranger's pockets
        teleport_obj(gift, enactor)
        say(f'A fair swap: {name(gift)} for your {name(it)}.')
    else:
        teleport_obj(it, enactor)  # no match: hand it straight back, never keep it
        say('No use to me. Ask me what I want.')
'''
```

Finally, something to trade with. Any object carrying the tag qualifies, which
is the whole point, so the plate needs no special name:

```text
@create a bent hull plate
@tag a bent hull plate = scrap_metal
```

## Try it

```text
> wants
    Rook trades goods for goods. No coin.
      anything scrap_metal -> a patched thermal cloak
      anything power_cell -> a tinkered lantern

> give a bent hull plate to Rook the Tinker
    Rook the Tinker says, "A fair swap: a patched thermal cloak for your a bent hull plate."
```

The cloak is now in your pack and the plate sits in Rook's hands stamped
`kept`. Check `credits` before and after and not one credit moved on either
side. Hand him something off-list, a ration bar or your boots, and it comes
straight back with "No use to me. Ask me what I want." Any other
`scrap_metal`-tagged thing in the world trades just the same, without touching
his script.

## Going further

- **Exchange rates.** Rows of `[want-tag, count, gift]` and a `pile_<tag>`
  counter on Rook: stamp arrivals, count them, and only gift when the pile hits
  `count`, so "three scrap for one cloak" is one extra attribute.
- **Finite stock.** Give the gift rows a `stock` count that decrements to a
  refusal ("Come back next week.") and let a `script_ticker` replenish it, the
  [shopkeeper](063_shopkeeper.md) restock heartbeat without any money.
- **Want what he lacks.** Have `on_receive` re-derive the want-list from what
  he is short of (`len([o for o in contents(me) if has_tag(o, w)])`), so a
  tinker who stops wanting scrap once he is drowning in it becomes a tiny
  economy simulation.
- **Chained crafting.** Make the counter-gift itself tagged for the next NPC's
  want-list, so a barter chain across the zone is a quest line with no quest
  system, the trade-up folktale as world design.
