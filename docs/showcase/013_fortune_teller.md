# 013. Fortune teller booth

> Checklist item 13 — [now] — *composing ON_PAYMENT + spawned collectible items*

**What you'll build:** Zoltar — a coin-operated cabinet automaton.
Feed it credits and it shudders to life, grinds its gears, and drops a
**printed fortune card** into the tray: a real, keepable item with a
random prophecy and lucky numbers baked on. Underpay and your coins
clatter straight back.

**Concepts:** composition — this gadget is nothing but idioms from
earlier tutorials wired together: `ON_PAYMENT` + the **ledger idiom**
(001), refund-or-vend branching (001/002), `create_obj()` collectibles
with `desc_extras` faces (008), `rand()` against a data table (005),
a `[[...]]` counter on the cabinet. New softcode: none. That's the
lesson.

Close the loop: [slot machine](001_slot_machine.md) for the money
plumbing, [camera](008_camera.md) for the printed-keepsake trick.

## How it works

**Money in, the only way there is.** Zoltar can't pick pockets —
players `pay 5 to Zoltar` (consent), the credits land, and the
cabinet's `ON_PAYMENT` fires. The script recovers *how much* with the
ledger idiom — `paid = credits(me) - ledger`, re-syncing `ledger` at
the end — because payment events don't carry amounts; the
[slot machine](001_slot_machine.md) explains why.

**One branch, two fates.** Enough coin: keep the fee, return the
change (`transfer_credits(me, enactor, paid - cost)` — Zoltar spends
its own money, which it may), do the theatrics, print the card. Short
coin: return *everything* with the price quoted. Every failure path
tells the customer the exact number that would fix it — vending
machine manners.

**The card is a collectible, not a message.** A `pemit` prophecy
scrolls away; a *card* persists, trades, and litters the fairground
charmingly. `create_obj` mints it into the customer's hands, and the
`desc_extras` rows (the [camera](008_camera.md)'s workaround for the
spawned-things-have-no-desc gap) give it a readable face: the
prophecy — picked by `rand()` from a data list — plus two lucky
numbers. `chr(34)` wraps the prophecy in literal quote marks (a
one-liner inside `@set` can't nest a third quoting level; `chr()` is
the clean escape). Tagged `no_group`, every card stays its own line in
a room listing — collectors care.

**The cabinet keeps score.** A `told` counter increments per fortune
and renders in the description through `[[...]]` — the same living-
description trick as the slot machine's hopper, and the number a
carnival owner actually wants to see.

## Build it

The automaton, its price, and its prophecy table — all data:

```text
@create Zoltar
drop Zoltar
@desc Zoltar = A glass cabinet housing a turbaned automaton, its waxen hand hovering over a deck of cards. [[result = f"The brass counter reads {V('told', 0)} fortunes told."]]
@set Zoltar/cost = 5
@set Zoltar/fortunes = ["You will take a journey your boots already suspect.", "Beware a door that is polite to you.", "Money finds you when you stop watching for it.", "An old debt returns wearing a new face."]
```

The whole machine is one `ON_PAYMENT`: ledger math, the two-fate
branch (the `for c in [create_obj(...)]` comprehension binds the fresh
card so two `set_attr`s can reach it — the arc's standard binding
trick), and the ledger re-sync last:

```text
@set Zoltar/on_payment = cost = V('cost', 5); paid = credits(me) - V('ledger', 0); f = V('fortunes', []); ok = paid >= cost and bool(f); (transfer_credits(me, enactor, paid - cost), incr('told'), remit(here, "Zoltar's eyes flare. Gears grind behind the glass, and a stiff card drops into the brass tray."), [(set_attr(c, 'desc_extras', [['', 'ZOLTAR SPEAKS:'], ['', chr(34) + f[rand(0, len(f) - 1)] + chr(34)], ['', f'Lucky numbers: {rand(1, 99)} and {rand(1, 99)}.']]), pemit(enactor, 'You lift the fortune card from the tray.')) for c in [create_obj('a printed fortune card', tags=['thing', 'no_group'], location=enactor)]]) if ok else (transfer_credits(me, enactor, paid), pemit(enactor, f'A fortune costs {cost} credits. The coins clatter back.')); set_attr(me, 'ledger', credits(me))
```

## Try it

With 20 credits in pocket:

```text
pay 3 to Zoltar      -> A fortune costs 5 credits. The coins clatter back.
pay 5 to Zoltar      -> (the room) Zoltar's eyes flare. Gears grind...
look fortune card
pay 9 to Zoltar      -> a second card -- and 4 credits in change
look Zoltar          -> The brass counter reads 2 fortunes told.
```

The card reads back its rows:

```text
a printed fortune card
ZOLTAR SPEAKS:
"Money finds you when you stop watching for it."
Lucky numbers: 41 and 87.
```

The underpayment moved nothing (check `credits`); the overpayment
came back as exact change; and each card is an independent object with
its own prophecy — trade them, hoard them, drop them dramatically.
Zoltar's own balance is the take: `@examine Zoltar` shows the fee
income sitting on the cabinet, ledger in agreement.

## Going further

- **Rarity tiers:** band a `rand(1, 100)` like the slot machine —
  1% of cards are gold-inked (`ansi('yh', ...)` in the rows) and worth
  something to a collector NPC (`shopkeeper` behavior buys them back).
- **Personalized dooms:** the prophecy already knows `name(enactor)`;
  a table of templates with `replace(text, '<mark>', name(enactor))`
  makes every card feel aimed.
- **Prophecies that check out:** stamp `expires_at`-style dates or the
  payer's id on the card (008's timestamp trick) — later gadgets can
  *verify* a card came from this Zoltar.
- **A grudging machine:** track `told_<player-id>` and after the third
  fortune, have Zoltar refuse: "The spirits tire of your questions." —
  per-player state keys, the slot machine's stake idiom.
