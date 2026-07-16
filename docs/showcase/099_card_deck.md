# 099. Card Deck

> Checklist item 99 — [now] — *list attrs, rand shuffles, pemit-private state*

**What you'll build:** A 52-card deck you can shuffle, deal from, and
play cards out of — where every hand is visible only to its owner,
enforced by the engine, not by politeness.

**Concepts:** building a deck with a comprehension, an unbiased
`rand()` shuffle, hands as one `secret`-flagged dict attribute,
`pemit()` private views vs `remit()` public plays, and case-insensitive
card matching.

## How it works

**The deck is a list attribute.** A `fresh` helper builds all 52 cards
as `rank + suit` strings (`'As'`, `'10h'`, `'Qd'`) with one nested
comprehension. `$shuffle` draws them into a new order by popping a
random index until the pile is empty — a selection shuffle, unbiased,
and four lines shorter than Fisher–Yates.

**Hands are one secret dict.** All hands live in a single `hands`
attribute on the deck, keyed by player id. REALM attributes are
readable by default (deliberately — traps read hp, shops read prices),
so a bare dict would let any stranger's gadget read your aces. The
`@attr` command's `secret` flag closes exactly that hole: flagged
attributes read as `None` for everyone but the deck's controllers —
while the deck's own `$`-commands, which run *as the deck*, keep full
access ([item 16](016_combination_safe.md) proved this pattern on the
safe's combination).

**Private vs public channels.** Your cards arrive by `pemit()` — a
whisper only you receive. Plays land by `remit()` — the whole table
sees `Kess plays Qh onto the table.` The information asymmetry of every
card game is just choosing the right emit per line.

## Build it

The deck and its card factory:

```text
@create a deck of cards
drop a deck of cards
@desc a deck of cards = Well-worn cards in a battered tin. [[result = str(len(get_attr(me, 'deck', []))) + ' cards remain in the tin.']]
@set a deck of cards/fresh = result = [r + s for s in ['s', 'h', 'd', 'c'] for r in ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']]
```

The hands ledger, sealed before the first card moves:

```text
@set a deck of cards/hands = {}
@attr a deck of cards/hands = secret
```

The shuffle — note the comprehension: `range(len(d))` is sized once
(52), while `d.pop(rand(0, len(d) - 1))` pulls from the shrinking pile:

```text
@set a deck of cards/cmd_shuffle = $shuffle: d = eval_attr(me, 'fresh'); p = [d.pop(rand(0, len(d) - 1)) for i in range(len(d))]; set_attr(me, 'deck', p); set_attr(me, 'hands', {}); set_attr(me, 'table', []); remit(here, name(enactor) + ' shuffles the deck with a riffle and a bridge.')
```

The deal. Cards come off the top (`d[:n]`), the recipient must be in
the room, and the tuple's left-to-right evaluation means `h` is already
updated when the `pemit` reads it:

```text
@set a deck of cards/cmd_deal = $deal * to *: n = int(trim(arg0)); who = get(trim(arg1)); d = get_attr(me, 'deck', []); h = get_attr(me, 'hands', {}); ok = who is not None and loc(who) is here and 0 < n <= len(d); (h.update({who.id: h.get(who.id, []) + d[:n]}), set_attr(me, 'hands', h), set_attr(me, 'deck', d[n:]), remit(here, name(who) + ' is dealt ' + str(n) + ' cards, face down.'), pemit(who, 'Your cards: ' + ' '.join(h[who.id]))) if ok else pemit(enactor, 'The deck cannot do that -- shuffle first, name a player here, and mind the count.')
```

Peeking and playing:

```text
@set a deck of cards/cmd_hand = $hand: h = get_attr(me, 'hands', {}).get(enactor.id, []); pemit(enactor, 'Your hand: ' + ' '.join(h) if h else 'You hold no cards.'); oemit(enactor, name(enactor) + ' fans a hand of cards close to the chest.') if h else None
@set a deck of cards/cmd_play = $play *: c = trim(arg0); h = get_attr(me, 'hands', {}); mine = h.get(enactor.id, []); pick = [x for x in mine if x.lower() == c.lower()]; (mine.remove(pick[0]), h.update({enactor.id: mine}), set_attr(me, 'hands', h), set_attr(me, 'table', get_attr(me, 'table', []) + [pick[0]]), remit(here, name(enactor) + ' plays ' + pick[0] + ' onto the table.')) if pick else pemit(enactor, 'That card is not in your hand.')
@set a deck of cards/cmd_table = $table: t = get_attr(me, 'table', []); pemit(enactor, 'On the table: ' + (' '.join(t) if t else 'nothing yet.'))
```

## Try it

```text
shuffle                  -> "Bilda shuffles the deck with a riffle and a bridge."
deal 5 to Kess           -> room: "Kess is dealt 5 cards, face down."
                            Kess alone: "Your cards: 7h Kd 2s As 9c"
deal 5 to Bilda
hand                     -> your five, whispered; the room sees only the fan
play As                  -> "Kess plays As onto the table."
table                    -> "On the table: As"
look a deck of cards     -> "42 cards remain in the tin."
```

And the lock on the hole cards — as anyone who isn't the deck's owner:

```text
@eval result = get_attr(get('a deck of cards'), 'hands')     -> => None
```

The owner reads the full dict; strangers read nothing. Hands are
engine-private, not honor-system private.

## Going further

- **Discard and redeal:** a `$muck` verb that moves your hand onto a
  `discards` list; `$shuffle` folds `discards` back in.
- **A cut for the superstitious:** `$cut` — `d = d[n:] + d[:n]` at a
  `rand()` index.
- **Build the game on top:** the [poker table](100_poker_table.md)
  reuses this exact deck-and-secret-hands core and adds betting rounds.
- **Physical cards:** deal `create_obj()` card objects into a player's
  inventory instead — they become droppable, tradeable props, at the
  cost of the single-attribute audit trail (`@examine` the deck shows
  every hand at once, for the table's owner only).
