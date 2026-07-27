# 108. Casino Floor

> Checklist item 108 ([now]): *composing prior builds into a venue*

**What you'll build:** a casino as one venue: a cashier cage that
exchanges credits for physical chips (and back), a croupier who runs a
double-or-nothing wheel paid in chips, and a house bank whose reserve
provably backs every chip on the floor. It is the conservation
discipline of the [currency Mint](086_currency.md) composed with the
games this chapter already built.

**Concepts:** scoped currency (chips as tagged token objects only the
cage honors),
[`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks) minting against
a reserve, [`ON_RECEIVE`](../reference/softcode.md#lifecycle-hooks) as a
betting channel (`give` chips to the croupier), a merge-and-split house
bank that conserves face value with
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits) and
[`create_obj`](../reference/softcode.md#fn-create_obj), and composition,
since this tutorial is mostly other tutorials arranged in one room.

## How it works

The finished venue is one room holding three cooperating objects: a
cashier cage that turns credits into physical chips and back, Croupier
Hazel who runs a double-or-nothing wheel paid in chips, and Hazel's own
chip stack that serves as the house bank. One number ties them
together, and it is the invariant the whole tutorial exists to teach:
the cage's credit balance always equals the face value of every chip on
the floor. This section answers what a chip is, who is allowed to make
and destroy one, how the wheel moves value without ever changing that
total, and why the games can share a room without interfering.

### What a chip is, and who honors it

A chip stack is an ordinary object named `casino chips`, tagged `chip`,
carrying one number in a `chips` attribute that is its face value.
Chips are the Mint pattern from the [currency build](086_currency.md)
scoped to a single house: only the cage mints them, on payment, backed
one-for-one by the credits that just landed in its reserve, and only the
cage melts them back on cash-in, paying out of that same reserve.
Because chips are worthless at the [shopkeeper](063_shopkeeper.md), a
winner has to walk back past the cage to leave with real money, which
makes the cage a natural exit-tax point and lets one person audit the
whole floor with a single sum.

### Who is allowed to mint

The cage builds a chip stack straight into a patron's hands with
[`create_obj`](../reference/softcode.md#fn-create_obj)`(...,
location=enactor)`. A script may only seed an object into a location it
controls, so a stranger's inventory is normally off limits. It works
here because you build the cage as an admin: the cage's scripts run with
its owner's authority, and an admin controls every player, so the
control chain reaches from the cage to you to the buyer. A cage built by
an ordinary player could not mint into a stranger, and would instead
have to create the stack in the room and then
[`move_to`](../reference/softcode.md#fn-move_to) it to the buyer. This is
the same admin-owned reasoning that backs the
[currency Mint](086_currency.md).

### The rule that keeps the reserve honest: merge and split, never mint

Croupier Hazel keeps a house bank, one chip stack flagged `house`. A bet
is `give casino chips to Croupier Hazel`, and her
[`ON_RECEIVE`](../reference/softcode.md#lifecycle-hooks) hook merges your
stack into that bank so the face value moves but the total on the floor
does not change. She then spins, and on a win splits twice your stake
back out of the bank into a fresh stack in your hands, again leaving the
total unchanged. Chips are created and destroyed only in equal and
opposite pairs, so the only object that ever makes a chip from nothing
is the cage, matched credit for credit. On a loss the merged stake
simply stays in the bank, which is the house edge accumulating as chips
the owner can cash in later.

### Why the wheel pays even money at 45%

Hazel's wheel is even money that wins only 45% of the time. A win returns
twice the stake, so the expected return is `0.45 * 2 = 0.90`, or 90
credits for every 100 staked, which leaves the house a 10% edge.
Recompute this whenever you retune the odds, because a wheel that pays
over even money is a charity (the [slot machine](001_slot_machine.md) has
the worked example).

### Why the games can share one room

A casino floor is the worst possible room to get event guards wrong,
because the whole point of the venue is that a cage, a
[slot machine](001_slot_machine.md), a
[poker table](100_poker_table.md), and a bookmaker all stand together.
Both an [`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks) and an
[`ON_RECEIVE`](../reference/softcode.md#lifecycle-hooks) fire on *every*
object in the room, not only the one the action was aimed at, so both
the cage's payment hook and Hazel's receive hook open with `if target is
me:`. Without that guard on the cage, dropping 25 credits in the slot
machine next door would have the cage cheerfully mint 25 in chips backed
by nothing, and the reserve-equals-chips invariant would break on the
first pull of the lever. `enactor` tells a hook who acted and `target`
tells it who was acted upon, so `target is me` is the entire difference
between "this happened to me" and "this happened near me". See
[Guard on `target`](../reference/softcode.md#guard-on-target).

## Build it

Build the whole floor **as an admin**, because the cage mints chip
stacks straight into patrons' hands and that takes owner authority over
players (see "Who is allowed to mint" above). Start with the room and
the cage's shell. The `[[...]]` block in the description runs per viewer
at look time, so the reserve figure is read fresh from
[`credits(me)`](../reference/softcode.md#fn-credits) on every look:

```text
@dig The Casino Floor
@teleport The Casino Floor
@create the cashier cage
drop the cashier cage
@desc the cashier cage = Brass bars over a marble sill. [[result = f'The reserve holds {credits(me)} credits.']]
```

The cage's [`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks) hook
reads the credits that just landed with
[`adata('amount')`](../reference/softcode.md#event-data-namespace) and
mints exactly that many chips, so the one-for-one backing is a single
line with nothing to fall out of step:

```text
@set the cashier cage/on_payment = '''
if target is me:  # ON_PAYMENT fires on EVERY object in the room, so guard it
    paid = adata('amount', 0)
    if paid > 0:
        stack = create_obj('casino chips', tags=['thing', 'chip'], location=enactor)
        set_attr(stack, 'chips', paid)  # mint exactly what was paid: 1:1 backing
        pemit(enactor, 'The teller slides ' + str(paid) + ' in chips under the bars.')
'''
```

The `$cashin` command melts chips back into credits. It is a
`$`-command, driven by player input rather than a room event, so it
needs no `target` guard. It sums the face value of every chip the player
carries, pays that out of the reserve with
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits), and
destroys the stacks only once the payout has cleared, so a failed
transfer can never vaporize a player's chips:

```text
@set the cashier cage/cmd_cashin = '''
$cashin:
stacks = [o for o in contents(enactor) if has_tag(o, 'chip')]
total = sum(get_attr(o, 'chips', 0) for o in stacks)
if total > 0 and transfer_credits(me, enactor, total):  # pay first, burn only if it cleared
    for o in stacks:
        destroy_obj(o)
    pemit(enactor, 'The teller counts ' + str(total) + ' in chips back into credits.')
else:
    pemit(enactor, 'You have no chips, or the cage cannot cover them.')
'''
```

Now the croupier and her wheel. First her shell, tagged `npc` so players
can `give` to her:

```text
@create Croupier Hazel
@tag Croupier Hazel = npc
drop Croupier Hazel
@desc Croupier Hazel = Green visor, quick hands, a wheel of numbered brass. Hand her chips to play double-or-nothing.
```

Her [`ON_RECEIVE`](../reference/softcode.md#lifecycle-hooks) hook is the
merge-spin-split routine. It gathers the loose chips just handed over,
finds the `house` bank in her own contents, refuses a stake the bank
cannot cover, and otherwise merges the stake in, spins once with
[`rand`](../reference/softcode.md#fn-rand), and on a win splits twice the
stake back out into a fresh stack for the player:

```text
@set Croupier Hazel/on_receive = '''
if target is me:  # ON_RECEIVE also fires on every object in the room, so guard it too
    stakes = [o for o in contents(me) if has_tag(o, 'chip') and not get_attr(o, 'house', 0)]
    wager = sum(get_attr(o, 'chips', 0) for o in stakes)
    rack = [o for o in contents(me) if has_tag(o, 'chip') and get_attr(o, 'house', 0)]
    bank = rack[0] if rack else None
    if wager > 0 and bank is not None:
        if get_attr(bank, 'chips', 0) < wager:
            for o in stakes:
                move_to(o, enactor)  # the bank cannot cover it, so hand the stake straight back
            pemit(enactor, 'Hazel pushes your chips back: the rack cannot cover that.')
        else:
            set_attr(bank, 'chips', get_attr(bank, 'chips', 0) + wager)  # merge the stake into the bank
            for o in stakes:
                destroy_obj(o)
            if rand(1, 100) <= 45:  # even money at 45%: a 10% house edge
                set_attr(bank, 'chips', get_attr(bank, 'chips', 0) - 2 * wager)
                won = create_obj('casino chips', tags=['thing', 'chip'], location=enactor)
                set_attr(won, 'chips', 2 * wager)  # split double the stake back out of the bank
                remit(here, 'Hazel spins the wheel... ' + name(enactor) + ' doubles up! ' + str(2 * wager) + ' in chips slide back.')
            else:
                remit(here, 'Hazel spins the wheel... the house rakes ' + str(wager) + ' in chips.')
'''
```

Finally, seed the house bank. The owner buys chips like anyone else,
flags the stack as the bank, and hands it over. Flag it *before* giving
it, because `@set` finds the objects you carry, not the contents of the
croupier:

```text
@eval adjust_credits(me, 500); result = credits(me)
pay 500 to the cashier cage
@set casino chips/house = 1
give casino chips to Croupier Hazel
```

That last `give` does not start a spin, because the stack it hands over
is flagged `house` and Hazel's hook excludes the bank from the stakes it
plays. To furnish the rest of the floor from this chapter, drop the
[slot machine](001_slot_machine.md) by the door (it plays in credits, so
it sits outside the chip economy on purpose), the
[card deck](099_card_deck.md) and [poker table](100_poker_table.md) on
the felt, and the [dueling stone](103_rock_paper_scissors.md) in the
corner. Same room, zero interference, because each machine owns its own
verbs and state and guards its own hooks.

## Try it

A patron buys in, plays a spin, and cashes out. The wheel line varies
with the roll, and this shows one winning outcome:

```text
> pay 100 to the cashier cage
The teller slides 100 in chips under the bars.

> inventory
casino chips

> give casino chips to Croupier Hazel
Hazel spins the wheel... Kess doubles up! 200 in chips slide back.

> cashin
The teller counts 200 in chips back into credits.
```

On a loss that middle line reads `Hazel spins the wheel... the house
rakes 100 in chips.` instead, and there is nothing to cash in. A stake
larger than the bank can cover is pushed straight back with `Hazel
pushes your chips back: the rack cannot cover that.` And `look the
cashier cage` reads the reserve live from the description block.

The audit runs any time, as the pit boss. It reads the cage's reserve
next to the face value of every chip in the world with
[`search_world`](../reference/softcode.md#fn-search_world):

```text
@eval cage = get('the cashier cage'); floor = sum(get_attr(o, 'chips', 0) for o in search_world(tag='chip')); result = [credits(cage), floor]
```

The two numbers match after every buy-in, every spin, and every
cash-out. If they ever diverge, some game on your floor is minting chips
it should have merged, so find it.

## Going further

- **An exit tax.** Have `$cashin` pay `total * 95 // 100`, the classic
  house rake, which shows up in the audit as the reserve outgrowing the
  chips.
- **Chip-side wagers everywhere.** Re-key the
  [dueling stone](103_rock_paper_scissors.md) or
  [wrestling table](106_arm_wrestling.md) escrows to `ON_RECEIVE` plus
  chip stacks instead of `ON_PAYMENT` plus credits, and the merge-split
  rule keeps the audit balanced.
- **Comp drinks.** Have Hazel track a `rake_<id>` per patron and add a
  `script_ticker` that comps big losers through the
  [bartender](064_bartender.md), which is retention casino style.
- **Zone announcements.** Tag the floor rooms into `zone:casino` and call
  `act(here, ..., targeting='zone')` on a big win, the
  [slot machine](001_slot_machine.md)'s advertising trick applied
  venue-wide.
