# 013. Fortune teller booth

> Checklist item 13 ([now]): *composing ON_PAYMENT + spawned collectible items*

**What you'll build:** Zoltar, a coin-operated cabinet automaton. Feed it
credits and it shudders to life, grinds its gears, and drops a **printed
fortune card** into the tray: a real, keepable item with a random prophecy
and lucky numbers baked on. Underpay and your coins clatter straight back.

**Concepts:** composition. Almost every part of this gadget is an idiom
from an earlier tutorial wired into a new machine:
[`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks) reading its own
[`adata('amount')`](../reference/softcode.md#event-data-namespace) payload
and branching between refund and service, as the
[slot machine](001_slot_machine.md) does; goods minted on demand with
[`create_obj`](../reference/softcode.md#fn-create_obj), as the
[vending machine](002_vending_machine.md) does; a `desc_extras` face on the
spawned keepsake, as the [camera](008_camera.md) prints; a
[`rand`](../reference/softcode.md#fn-rand) pick against a data table, as
the [magic 8-ball](005_magic_8ball.md) rolls; and a live `[[...]]` counter
on the cabinet. The one new verb is
[`move_to`](../reference/softcode.md#fn-move_to), which hands the finished
card to the customer, and that near-total reuse is the lesson.

Build the [slot machine](001_slot_machine.md) first for the money
plumbing; the [camera](008_camera.md) shows the printed-keepsake trick
this build reuses.

## How it works

One object carries the whole booth: a price and a prophecy table stored as
plain data, plus a single `ON_PAYMENT` hook that takes the coins, vends
the card, and keeps score. This section explains how the money arrives,
how the branch decides, why the fortune is a real object, and how that
object reaches the customer's hands.

**Money in, the only way there is.** A script runs with its object's
authority, so Zoltar can spend its own balance but cannot lift coins from
a customer's pocket; the fee has to arrive through the built-in `pay`,
which is consent. A payment runs as a before/apply/after trio
([action phases](../design/action-phases.md)): wards may veto it first,
then the credits move, and only then does the cabinet's
[`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks) fire. The hook
therefore always runs with the coins already in the cabinet, and
[`adata('amount')`](../reference/softcode.md#event-data-namespace) names
how many arrived, exactly as the [slot machine](001_slot_machine.md) reads
its wager. Because the hook fires on every object in the room, it opens
with `if target is me:`
([guard on `target`](../reference/softcode.md#guard-on-target));
unguarded, a payment to the machine next door would have Zoltar lecturing
that customer about its prices.

**One branch, two fates.** With enough coin the machine keeps the fee and
returns the change with
[`transfer_credits(me, enactor, paid - cost)`](../reference/softcode.md#fn-transfer_credits),
which works because Zoltar is spending its own money; then it counts the
fortune, plays the theatrics, and prints the card. Short coin: the coins
have already landed, so the machine sends every one of them straight back
with the price quoted. Every failure path tells the customer the exact
number that would fix it, which is vending machine manners. The same
condition also refuses to vend from an empty `fortunes` table, refunding
rather than minting a blank card.

**The card is a collectible, not a message.** A
[`pemit`](../reference/softcode.md#fn-pemit) prophecy scrolls away,
whereas a card persists, trades, and litters the fairground charmingly.
[`create_obj`](../reference/softcode.md#fn-create_obj) mints it, and
`desc_extras` rows give it a readable face, the `@detail` convention the
[camera](008_camera.md) uses for its prints: each `['', text]` row is a
detail line every viewer sees on `look`. (`create_obj` can also write a
plain one-block description, but the rows keep each line of the card its
own entry, the same composed face the camera builds.) The face holds the
prophecy, picked from the table with
[`rand`](../reference/softcode.md#fn-rand), plus two lucky numbers. Tagged
`no_group`, every card stays its own line in a room listing instead of
collapsing into "2 fortune cards", and collectors care about that.

**How the card reaches the customer's hands.** `create_obj` mints into the
machine's own room by default, but it refuses `location=enactor` for a
paying stranger: placing a newborn object inside another player is a
mutation of someone the machine does not control, so the call would come
back `None` and no card would exist. The build therefore lets the card be
born in the tray (the machine's room) and hands it over with
[`move_to(card, enactor)`](../reference/softcode.md#fn-move_to), the
engine's one relocation verb, whose delivery honors the customer's own
wards and locks like any other movement. The fiction and the mechanics
agree: the card drops into the tray, and you lift it out.

**The cabinet keeps score.**
[`incr('told')`](../reference/softcode.md#fn-incr) bumps a counter per
fortune, and the description renders it live through a `[[...]]` block,
the same living-description trick as the
[slot machine](001_slot_machine.md)'s hopper readout. The take needs no
counter at all, because the fees simply sit on the cabinet as its credit
balance; `@examine Zoltar` shows `credits` and `told` side by side in
plain attributes.

## Build it

The payment hook below is a `'''` multi-line block: end the `@set` line
with `'''`, type the body as ordinary indented Python, and close with a
line of just `'''` (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)).

**The cabinet.** Create it, place it, and give it a living face: the
`[[...]]` block runs per look, so the brass counter always shows the
current [`V('told', 0)`](../reference/softcode.md#fn-v):

```text
@create Zoltar
drop Zoltar
@desc Zoltar = A glass cabinet housing a turbaned automaton, its waxen hand hovering over a deck of cards. [[result = f"The brass counter reads {V('told', 0)} fortunes told."]]
```

**The price and the prophecies.** Both are data, so retheming a booth
never touches its script, and `@set` parses JSON, which stores the table
as a real list:

```text
@set Zoltar/cost = 5
@set Zoltar/fortunes = ["You will take a journey your boots already suspect.", "Beware a door that is polite to you.", "Money finds you when you stop watching for it.", "An old debt returns wearing a new face."]
```

**The whole machine, one hook.** Guard, read the payment, then the
two-fate branch: with enough coin it refunds any overpay, counts the
fortune, plays the theatrics, mints the card, hands it over, and writes
its face; otherwise it returns everything with the price quoted:

```text
@set Zoltar/on_payment = '''
if target is me:  # ON_PAYMENT fires on EVERY object in the room, so guard it
    cost = V('cost', 5)
    paid = adata('amount')
    deck = V('fortunes', [])
    if paid >= cost and deck:
        transfer_credits(me, enactor, paid - cost)  # the fee stays; any overpay goes back
        incr('told')
        remit(here, "Zoltar's eyes flare. Gears grind behind the glass, and a stiff card drops into the brass tray.")
        card = create_obj('a printed fortune card', tags=['thing', 'no_group'])
        move_to(card, enactor)  # minting straight into a stranger's inventory is refused; hand it over instead
        pick = deck[rand(0, len(deck) - 1)]
        rows = [['', 'ZOLTAR SPEAKS:'], ['', f'"{pick}"'], ['', f'Lucky numbers: {rand(1, 99)} and {rand(1, 99)}.']]
        set_attr(card, 'desc_extras', rows)
        pemit(enactor, 'You lift the fortune card from the tray.')
    else:
        transfer_credits(me, enactor, paid)  # the coins already landed, so send every one back
        pemit(enactor, f'A fortune costs {cost} credits. The coins clatter back.')
'''
```

[`remit`](../reference/softcode.md#fn-remit) plays the theatrics to the
whole room while [`pemit`](../reference/softcode.md#fn-pemit) hands the
lift line to the customer alone, and
[`set_attr`](../reference/softcode.md#fn-set_attr) writes the face onto
the card, which still works after the handover because a machine controls
what it mints.

## Try it

With 20 credits in pocket (`@eval adjust_credits(me, 20)`):

```text
> pay 3 to Zoltar
A fortune costs 5 credits. The coins clatter back.
You pay Zoltar 3 credits.

> pay 5 to Zoltar
Zoltar's eyes flare. Gears grind behind the glass, and a stiff card drops into the brass tray.
You lift the fortune card from the tray.
You pay Zoltar 5 credits.

> look fortune card
a printed fortune card
ZOLTAR SPEAKS:
"Money finds you when you stop watching for it."
Lucky numbers: 41 and 87.

> pay 9 to Zoltar
Zoltar's eyes flare. Gears grind behind the glass, and a stiff card drops into the brass tray.
You lift the fortune card from the tray.
You pay Zoltar 9 credits.

> look Zoltar
Zoltar
A glass cabinet housing a turbaned automaton, its waxen hand hovering over a deck of cards. The brass counter reads 2 fortunes told.
```

The prophecy and both lucky numbers follow the roll, so those two lines
vary; everything else is fixed. Note the order on the underpay: "You pay
Zoltar 3 credits." still prints, because the payment itself succeeded and
the hook only ran after it; the refund is the machine's own transfer
straight back, and `credits` confirms you ended where you began. The
9-credit visit returns 4 as exact change (your balance runs 20, then 15,
then 10), each card is an independent object with its own prophecy, and
bystanders see "Bilda pays Zoltar." plus the gear-grinding line. The take
is the cabinet's own balance: `@examine Zoltar` shows the fee income in
`credits`, 5 a fortune, change already returned.

## Going further

- **Rarity tiers:** band a `rand(1, 100)` the way the
  [slot machine](001_slot_machine.md) weights its reels, so 1% of cards
  come gold-inked ([`ansi('yh', ...)`](../reference/softcode.md#fn-ansi)
  in the rows) and are worth something to a collector NPC running the
  `shopkeeper` behavior from [the shopkeeper](063_shopkeeper.md).
- **Personalized dooms:** the hook already knows
  [`name(enactor)`](../reference/softcode.md#fn-name), so a table of
  templates filled in with
  [`replace(text, '<mark>', name(enactor))`](../reference/softcode.md#fn-replace)
  makes every card feel aimed.
- **Prophecies that check out:** stamp
  [`now()`](../reference/softcode.md#fn-now) or the payer's id onto the
  card, the [camera](008_camera.md)'s `taken_at` trick, and later gadgets
  can verify a card came from this Zoltar.
- **A grudging machine:** track `told_<player-id>` per customer, the
  [slot machine](001_slot_machine.md)'s per-player stake idiom, and after
  the third fortune have Zoltar refuse: "The spirits tire of your
  questions."
