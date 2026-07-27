# 099. Card Deck

> Checklist item 99 ([now]): *list attrs, rand shuffles, pemit-private state*

**What you'll build:** A 52-card deck you can shuffle, deal from, and
play cards out of, where every hand is visible only to its owner because
the engine enforces it, not because the other players are polite.

**Concepts:** building a deck with a comprehension, an unbiased
[`rand`](../reference/softcode.md#fn-rand) selection shuffle, hands held
in one `secret`-flagged dict attribute, [`pemit`](../reference/softcode.md#fn-pemit)
private views against [`remit`](../reference/softcode.md#fn-remit) public
plays, and case-insensitive card matching.

## How it works

The finished deck is one object carrying three lists: the `deck` of
undealt cards, a `hands` dictionary keyed by player, and the `table` of
cards played so far. Every verb (`shuffle`, `deal`, `hand`, `play`,
`table`) is a `$`-command on that object, so it runs with the deck's own
authority. That single fact answers the two questions a card game poses:
how the cards move, and how a hand stays private.

### Where do the cards live?

The deck is a plain list attribute. A `fresh` helper builds all 52 cards
as `rank + suit` strings (`'As'`, `'10h'`, `'Qd'`) with one nested
comprehension, and `$shuffle` draws them into a new order: it pops a card
at a random index from the pile and repeats until the pile is empty. That
is a selection shuffle, and because every remaining card is equally
likely to be the next one popped, the result is an unbiased permutation.
[`rand`](../reference/softcode.md#fn-rand) picks each index, and
[`set_attr`](../reference/softcode.md#fn-set_attr) writes the new order
back onto the deck.

### How can a hand stay secret?

All hands live in a single `hands` attribute on the deck, a dictionary
keyed by player id. REALM attributes are readable by default, and
deliberately so, because traps read hp and shops read prices, which means
a bare dict would let any stranger's gadget read your aces. The `@attr`
command's `secret` flag closes exactly that hole: a flagged attribute
reads as `None` for everyone except the deck's controllers, judged by
[`get_attr`](../reference/softcode.md#fn-get_attr) against the reader.
The deck's own verbs are unaffected, because a `$`-command runs as the
deck, and an object always controls itself. The [combination
safe](016_combination_safe.md) proves this same flag on a lock's
combination.

Because these are `$`-commands rather than reactive `ON_<EVENT>` hooks,
none of them needs a `target` guard: a `$`-command fires only on the
object that owns it, so `me` is always the deck. (A hook that reacted to
a room-wide event would need the [guard on
`target`](../reference/softcode.md#guard-on-target), since events are
heard by every object in the room.)

### Who sees each line?

Your cards arrive by [`pemit`](../reference/softcode.md#fn-pemit), a
whisper only you receive, while plays land by
[`remit`](../reference/softcode.md#fn-remit), which the whole table sees
as `Kess plays Qh onto the table.` The information asymmetry that every
card game depends on is just a matter of choosing the right emit for each
line, and [`oemit`](../reference/softcode.md#fn-oemit) covers the third
case: telling the room what a player did without repeating it to the
player.

## Build it

Create the deck, drop it in the room, and give it a description that
counts the cards still in the tin at look time. [`V`](../reference/softcode.md#fn-v)
reads the `deck` list off the deck itself:

```text
@create a deck of cards
drop a deck of cards
@desc a deck of cards = Well-worn cards in a battered tin. [[result = str(len(V('deck', []))) + ' cards remain in the tin.']]
```

The card factory is a single comprehension, so it stays a one-line
attribute. The outer loop walks the four suits and the inner loop the
thirteen ranks, joining each pair into a `rank + suit` string:

```text
@set a deck of cards/fresh = result = [r + s for s in ['s', 'h', 'd', 'c'] for r in ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']]
```

Start the hands ledger as an empty dict, then seal it with `@attr` before
the first card ever moves, so strangers can never read it:

```text
@set a deck of cards/hands = {}
@attr a deck of cards/hands = secret
```

The shuffle rebuilds a fresh 52 from `fresh`, then pops a card at a random
index until the pile is empty. [`eval_attr`](../reference/softcode.md#fn-eval_attr)
runs the `fresh` script and hands back its `result`, and the loop leaves
`shuffled` holding an unbiased permutation:

```text
@set a deck of cards/cmd_shuffle = '''
$shuffle:
deck = eval_attr(me, 'fresh')
shuffled = []
for i in range(len(deck)):
    # pop from the shrinking pile, so every card is equally likely next
    shuffled.append(deck.pop(rand(0, len(deck) - 1)))
set_attr(me, 'deck', shuffled)
set_attr(me, 'hands', {})
set_attr(me, 'table', [])
remit(here, name(enactor) + ' shuffles the deck with a riffle and a bridge.')
'''
```

The deal takes cards off the top (`deck[:n]`) once three conditions hold:
the recipient exists, stands in the room, and the count fits what is
left. [`get`](../reference/softcode.md#fn-get) resolves the name and
[`loc`](../reference/softcode.md#fn-loc) checks the room with an identity
test, `is`, not `==`:

```text
@set a deck of cards/cmd_deal = '''
$deal * to *:
n = int(trim(arg0))
who = get(trim(arg1))
deck = V('deck', [])
hands = V('hands', {})
if who is not None and loc(who) is here and 0 < n <= len(deck):
    hands[who.id] = hands.get(who.id, []) + deck[:n]
    set_attr(me, 'hands', hands)
    set_attr(me, 'deck', deck[n:])
    remit(here, name(who) + ' is dealt ' + str(n) + ' cards, face down.')
    # the whisper reads the hand only after set_attr has stored it
    pemit(who, 'Your cards: ' + ' '.join(hands[who.id]))
else:
    pemit(enactor, 'The deck cannot do that: shuffle first, name a player here, and mind the count.')
'''
```

Peeking is private: your hand is whispered to you, while the room sees
only that you fanned some cards close to the chest.
[`oemit`](../reference/softcode.md#fn-oemit) is the everyone-but-you
channel:

```text
@set a deck of cards/cmd_hand = '''
$hand:
hand = V('hands', {}).get(enactor.id, [])
if hand:
    pemit(enactor, 'Your hand: ' + ' '.join(hand))
    oemit(enactor, name(enactor) + ' fans a hand of cards close to the chest.')
else:
    pemit(enactor, 'You hold no cards.')
'''
```

Playing a card matches the named card against your hand
case-insensitively, moves it from your hand to the table, and announces
the play to the whole room with `remit`:

```text
@set a deck of cards/cmd_play = '''
$play *:
card = trim(arg0)
hands = V('hands', {})
mine = hands.get(enactor.id, [])
# lower() both sides so "as" finds "As"
pick = [x for x in mine if x.lower() == card.lower()]
if pick:
    mine.remove(pick[0])
    hands[enactor.id] = mine
    set_attr(me, 'hands', hands)
    set_attr(me, 'table', V('table', []) + [pick[0]])
    remit(here, name(enactor) + ' plays ' + pick[0] + ' onto the table.')
else:
    pemit(enactor, 'That card is not in your hand.')
'''
```

The table view is a single read and a single line, so it stays one line:

```text
@set a deck of cards/cmd_table = $table: t = V('table', []); pemit(enactor, 'On the table: ' + (' '.join(t) if t else 'nothing yet.'))
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

The dealt cards vary with the shuffle; everything else is fixed. And the
lock on the hole cards, read as anyone who does not control the deck:

```text
@eval result = get_attr(get('a deck of cards'), 'hands')     -> None
```

The owner reads the full dict; a stranger reads nothing. Hands are
engine-private, not honor-system private.

## Going further

- **Discard and redeal:** a `$muck` verb that moves your hand onto a
  `discards` list, and a `$shuffle` that folds `discards` back in.
- **A cut for the superstitious:** `$cut`, which rotates the deck with
  `d = d[n:] + d[:n]` at a `rand()` index.
- **Build the game on top:** the [poker table](100_poker_table.md) reuses
  this exact deck-and-secret-hands core and adds betting rounds.
- **Physical cards:** deal [`create_obj()`](../reference/softcode.md#fn-create_obj) card objects into a player's
  inventory instead, so they become droppable, tradeable props, at the
  cost of the single-attribute audit trail that lets the deck's owner
  `@examine` every hand at once.
</content>
</invoke>
