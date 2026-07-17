# 108. Casino Floor

> Checklist item 108 — [now] — *composing prior builds into a venue*

**What you'll build:** A casino as one venue: a cashier cage that
exchanges credits for physical chips (and back), a croupier who runs a
double-or-nothing wheel *in chips*, and a house bank whose reserve
provably backs every chip on the floor — the conservation discipline of
[item 86](086_currency.md)'s Mint, composed with the games this
chapter already built.

**Concepts:** scoped currency (chips as tagged token objects only the
cage honors), `ON_PAYMENT` minting against a reserve, `ON_RECEIVE` as a
betting channel (`give` chips to the croupier), the merge/split float
that conserves face value, and composition — this tutorial is mostly
other tutorials, arranged.

## How it works

**Chips are the Mint pattern, scoped to the house.** A chip stack is
an object named `casino chips`, tagged `chip`, with a `chips` face
value. Only the cage mints them (on payment, backed 1:1 by the credits
that just landed in its reserve) and only the cage melts them (cash-in,
paid from that same reserve). The invariant to audit: **the cage's
credit balance equals the face value of every chip in the world,
including the croupier's rack.** Games that follow the rule below keep
it true forever.

**The rule: games merge and split, never mint.** Croupier Hazel keeps
a *house float* — one chip stack flagged `house`. A bet is `give
casino chips to Croupier Hazel`; her `ON_RECEIVE` merges your stack
into the float (face value moves, total unchanged), spins, and on a
win splits `2×` your stake back out of the float into a fresh stack in
your hands — again, total unchanged. Chips are created and destroyed
only in equal-and-opposite pairs. On a loss the merged stake simply
stays in the float: that's the house edge accumulating as float, and
`cashin`-able profit for the owner.

**Why chips at all?** The cage is the venue's seam. Credit games like
the [slot machine](001_slot_machine.md) can sit on the same floor and
play in credits directly; chip games mark you as *inside the house
economy* — chips are worthless at the [shopkeeper](063_shopkeeper.md),
so winnings walk back past the cage (a natural exit tax point), and
the pit boss can audit the whole floor with one sum.

**The wheel's arithmetic:** even money at 45% — expected return 90
credits per 100 staked, a 10% edge. Recompute whenever you touch the
odds; a casino that pays over evens is a charity
([item 1](001_slot_machine.md) has the worked example).

## Build it

As an **admin** (the cage mints chip stacks straight into patrons'
hands, which takes owner authority). The floor and the cage:

```text
@dig The Casino Floor
@teleport The Casino Floor
@create the cashier cage
drop the cashier cage
@desc the cashier cage = Brass bars over a marble sill. [[result = f'The reserve holds {credits(me)} credits.']]
@set the cashier cage/on_payment = paid = credits(me) - V('ledger', 0); c = create_obj('casino chips', tags=['thing', 'chip'], location=enactor) if paid > 0 else None; (set_attr(c, 'chips', paid), pemit(enactor, 'The teller slides ' + str(paid) + ' in chips under the bars.')) if c is not None else None; set_attr(me, 'ledger', credits(me))
@set the cashier cage/cmd_cashin = $cashin: stacks = [o for o in contents(enactor) if has_tag(o, 'chip')]; total = sum(get_attr(o, 'chips', 0) for o in stacks); ok = total > 0 and transfer_credits(me, enactor, total); [destroy_obj(o) for g in [ok] if g for o in stacks]; pemit(enactor, 'The teller counts ' + str(total) + ' in chips back into credits.' if ok else 'You have no chips, or the cage cannot cover them.'); set_attr(me, 'ledger', credits(me))
```

The croupier and her wheel — merge, spin, split:

```text
@create Croupier Hazel
@tag Croupier Hazel = npc
drop Croupier Hazel
@desc Croupier Hazel = Green visor, quick hands, a wheel of numbered brass. Hand her chips to play double-or-nothing.
@set Croupier Hazel/on_receive = stakes = [o for o in contents(me) if has_tag(o, 'chip') and not get_attr(o, 'house', 0)]; w = sum(get_attr(o, 'chips', 0) for o in stakes); rack = [o for o in contents(me) if has_tag(o, 'chip') and get_attr(o, 'house', 0)]; f = rack[0] if rack else None; ok = w > 0 and f is not None; short = ok and get_attr(f, 'chips', 0) < w; [(move_to(o, enactor), pemit(enactor, 'Hazel pushes your chips back: the rack cannot cover that.')) for g in [short] if g for o in stakes]; play = ok and not short; [(set_attr(f, 'chips', get_attr(f, 'chips', 0) + w), [destroy_obj(o) for o in stakes], set_attr(me, 'spin', rand(1, 100))) for g in [play] if g]; win = play and V('spin', 100) <= 45; [(set_attr(f, 'chips', get_attr(f, 'chips', 0) - 2 * w), set_attr(create_obj('casino chips', tags=['thing', 'chip'], location=enactor), 'chips', 2 * w), remit(here, 'Hazel spins the wheel... ' + name(enactor) + ' doubles up! ' + str(2 * w) + ' in chips slide back.')) for g in [win] if g]; remit(here, 'Hazel spins the wheel... the house rakes ' + str(w) + ' in chips.') if play and not win else None
```

Seed the house float — the owner buys chips like anyone else, flags
the stack as the rack, and hands it over. (Flag *before* giving: `@set`
finds carried objects, not the insides of the croupier.)

```text
@eval adjust_credits(me, 500); result = credits(me)
pay 500 to the cashier cage
@set casino chips/house = 1
give casino chips to Croupier Hazel
```

Furnish the floor from this chapter: the
[slot machine](001_slot_machine.md) by the door (credits — it sits
outside the chip economy on purpose), the
[card deck](099_card_deck.md) and [poker table](100_poker_table.md) on
the felt, the [dueling stone](103_rock_paper_scissors.md) in the
corner. Same room, zero interference: each machine owns its verbs and
its state.

## Try it

A patron with 200 credits:

```text
pay 100 to the cashier cage         -> "The teller slides 100 in chips under the bars."
inventory                           -> casino chips
give casino chips to Croupier Hazel -> "Hazel spins the wheel... Kess doubles up!
                                        200 in chips slide back."   (or the rake)
cashin                              -> "The teller counts 200 in chips back into credits."
look the cashier cage               -> the reserve, live
```

The audit, any time, as the pit boss:

```text
@eval cage = get('the cashier cage'); floor = sum(get_attr(o, 'chips', 0) for o in search_world(tag='chip')); result = [credits(cage), floor]
```

The two numbers match after every buy-in, every spin, every cash-out.
If they ever diverge, some game on your floor is minting — find it.

## Going further

- **An exit tax:** `cashin` pays `total * 95 // 100` — the classic
  house rake, visible in the invariant as reserve outgrowing chips.
- **Chip-side wagers everywhere:** re-key the
  [dueling stone](103_rock_paper_scissors.md) or
  [wrestling table](106_arm_wrestling.md) escrows to `ON_RECEIVE` +
  chip stacks instead of `ON_PAYMENT` + credits — the merge/split rule
  keeps the audit green.
- **Comp drinks:** Hazel tracks `rake_<id>` per patron and a
  `script_ticker` has her comp big losers via the
  [bartender](064_bartender.md) — retention, casino style.
- **Zone announcements:** tag the floor rooms into `zone:casino` and
  `act(here, ..., targeting='zone')` on big wins — the
  [slot machine](001_slot_machine.md)'s advertising trick, venue-wide.
