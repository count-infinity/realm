# Part 11 — Market Day

Saltmarsh sells things. This part builds the town's living heart: a
shop whose prices are *opinions* — and opinions, in REALM, are the
disposition system you met in part 3, finally spending money.

## Up the lane

```text
@dig Market Square = market, quay
market
@tag here = zone:saltmarsh
@desc here = Fish scales silver the cobbles. Stalls lean together like conspirators.
@dig The Anchorage = tavern, market
```

Two locals, for later parts — a porter in the square, a sailor in the
tavern:

```text
@create Old Bramble
@tag Old Bramble = npc
@set Old Bramble/description = A porter shaped by forty years of other people's cargo.
@set Old Bramble/credits = 15
drop Old Bramble
tavern
@create the sailor
@tag the sailor = npc
@set the sailor/description = Half a bottle past caring, but his eyes still count the exits.
drop the sailor
market
```

## The shop

A shopkeeper is one behavior. Her stock is *literally her inventory*;
her prices come from each item's `value`:

```text
@create Mother Salt
@tag Mother Salt = npc
drop Mother Salt
@behavior Mother Salt = shopkeeper, markup:1.3, buyback:0.4
@create an oilskin cloak
@set an oilskin cloak/value = 18
give an oilskin cloak to Mother Salt
@create a smoked herring
@set a smoked herring/value = 2
give a smoked herring to Mother Salt
@create a milk-opal pendant
@set a milk-opal pendant/value = 60
@set a milk-opal pendant/description = Cold to the touch, and the light inside it moves a half-beat late. Came off a wreck, she says.
give a milk-opal pendant to Mother Salt
```

Now `list`. She sells at `value × 1.3`, buys your loot at 40% —
`sell` anything you dragged out of the cellar or the wreck. `credits`
shows your purse; `buy smoked herring` if it can stand the loss.

## Prices have opinions

The markup is only the start: every price is bent **±5% per
disposition point** (capped at ±15%). Watch it move:

```text
consider mother salt
persuade mother salt
list
```

`consider` rolls her memoized first impression (part 3); a won
`persuade` is +1 *forever* — and the whole price list dips 5%. This is
why the social commands aren't flavor: goodwill is a discount,
`fasttalk` is a temporary +2 con that *wears off* mid-shopping trip
(and costs you a permanent -1 when she catches you), and the pendant
at 78 silver is a persuasion problem as much as a savings one.

## The gift

Merchants can be softened the old way, too. `ON_RECEIVE` fires when
someone gives her something — gate it with part 4's caching trick so
generosity only works once:

```text
@set Mother Salt/ON_RECEIVE = k = 'gift_' + enactor.id; (say('For me? Kind soul.'), adjust_disposition(me, enactor, 1), set_attr(me, k, 1)) if not get_attr(me, k) else say('You spoil me. Once was enough.')
```

Buy the herring back and give it to her — +1, once. (Without the
cache, your players will discover the two-credit friendship machine
before breakfast. They always do.)

## Checkpoint

`list` prices shift after `persuade`; a second `persuade` is refused
(one honest pitch per person); the gift line thanks you once and
deflects you forever after.

!!! info "Learn more"
    `buy`/`sell`/`list`/`pay` find whoever in the room carries the
    `shopkeeper` behavior. The currency's *name* comes from the game
    system (`credits` by default — a fantasy ruleset can call them
    florins without touching the economy). Disposition bands and the
    ±15% cap live in `realm/behaviors/shop.py`; the social commands'
    exact contests are in part 3 and `help persuade`.
