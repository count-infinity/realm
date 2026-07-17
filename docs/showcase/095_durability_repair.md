# 095. Item durability & repair

> Checklist item 95 — [now] — *durability attrs, master ON_ATTACK bookkeeping, $repair*

**What you'll build:** gear that wears out and a bench that charges to
fix it: weapons lose condition with every combat swing (a room-master
`ON_ATTACK` does the bookkeeping), tools lose it on every `use` (their
own `ON_USE` does), ruined gear refuses to be readied (an `on_check`
ward), and the repair bench burns credits — a true money sink.

**Concepts:** a `condition` attribute as the wear state; **which engine
events can honestly drive wear** (and which can't); witness-side
`ON_ATTACK` bookkeeping on a master; self-mutating `ON_USE` on tools;
gated `item:on_wield` refused by an `on_check` ward; `$repair` with
`adjust_credits(me, -cost)` as an explicit credit burn.

## How it works

**Be honest about what fires.** Durability systems die of wishful
thinking, so start from the engine's actual event surface:

- **Combat swings**: every attack propagates `combat:on_attack` (before
  the to-hit roll — a whiff still wears the blade), witnessed by the
  room, its contents, and zone masters. A *wear master* standing in the
  room hears every swing.
- **Deliberate use**: the `use` builtin propagates `item:on_use` at the
  target — the tool itself can carry the `ON_USE` that wears it.
- **`$`-verb tools** (a welding rig's own `$weld *`): the verb script
  can decrement its own condition inline — self-mutation is always
  within an object's authority.

What **cannot** honestly drive wear today: armor on the *defender*. An
event trigger binds only the enactor (the attacker) into its namespace —
`combat:on_damage` reaches witnesses, but they cannot see *who took the
hit* (the action's target isn't bound, the same no-payload limitation as
`ON_PAYMENT`'s missing amount). So this build wears the attacker's
wielded weapon per swing — knowable from `enactor` alone — and leaves
defender-side armor wear as an engine gap, noted below. Walking,
carrying, and time don't fire item events either; if you want age, put
it on a ticker (see Going further).

**The bookkeeping lives on a witness, the gate lives on the item.** The
wear master's `ON_ATTACK` finds the enactor's `wielded`-tagged item and
knocks 5 off its `condition` (admin authority may mutate a player's
gear), announcing at the battered threshold and at zero. The item
itself carries the *refusal*: `item:on_wield` is a gated event, so an
`on_check` ward on the weapon vetoes readying it at condition 0. A
broken blade already in hand keeps swinging its ruined swings — the
engine has no per-swing weapon check pass — but once lowered it will
not come back up until repaired. Say so to your players; honest rules
beat leaky ones.

**Repair is a sink, not a transfer.** The bench takes the fee with
`transfer_credits` (which is also the wallet check), then *burns it*
with `adjust_credits(me, -cost)` — the credits leave the economy
entirely. Faucets (job wages, interest) need matching drains or prices
inflate forever; repair is the classic drain because breakage scales
with activity.

## Build it

The yard, the wear master (a plain witness object — drop one per combat
zone, or tag a zone master the same way), and the bench:

```text
@dig The Sparring Yard
@teleport The Sparring Yard
@create the wear master
drop the wear master
@create the repair bench
drop the repair bench
```

The per-swing bookkeeping. On every attack witnessed, find the
attacker's readied weapon and wear it — with a battered warning at 25
and a break notice at 0:

```text
@set the wear master/ON_ATTACK = [(set_attr(o, 'condition', c), remit(here, f'{name(o)} is looking battered.') if c == 25 else None, remit(here, f'{name(o)} gives out with a crack!') if c == 0 else None) for o in contents(enactor) if has_tag(o, 'wielded') for c in [max(0, get_attr(o, 'condition', 100) - 5)]]
```

A weapon that starts sound and refuses to be readied once ruined — the
ward runs in the gated `item:on_wield` check pass:

```text
@create a mono blade
@set a mono blade/value = 40
@set a mono blade/condition = 100
@set a mono blade/on_check = block('The mono blade is a ruin of snapped segments. It needs a bench.') if atype == 'item:on_wield' and V('condition', 100) <= 0 else None
```

A tool that wears itself on every `use` — no master needed, the target
of `item:on_use` witnesses its own event, and its ward refuses use at
zero:

```text
@create an arc welder
@set an arc welder/condition = 20
@set an arc welder/ON_USE = c = max(0, V('condition', 100) - 10); set_attr(me, 'condition', c); pemit(enactor, f'The welder spits a bead of blue flame. (condition {c})')
@set an arc welder/on_check = block('The welder is burnt out. It needs a bench.') if atype == 'item:on_use' and V('condition', 100) <= 0 else None
```

And the bench: fee scales with missing condition, the transfer is the
wallet check, and the burn makes it a sink:

```text
@set the repair bench/cmd_repair = $repair *:itm = [o for o in contents(enactor) if name(o).lower() == arg0.strip().lower()]; c = get_attr(itm[0], 'condition', 100) if itm else 100; cost = max(1, (100 - c) // 2); ok = bool(itm) and c < 100 and transfer_credits(enactor, me, cost); [(set_attr(o, 'condition', 100), adjust_credits(me, -k), pemit(enactor, f'The bench grinds, reseats and trues {name(o)}: good as new for {k} credits.')) for g, o, k in [[ok, itm[0] if itm else None, cost]] if g]; pemit(enactor, 'Nothing to repair, or you cannot cover the fee.') if not ok else None
```

## Try it

Wield the blade and pick a fight in the yard; every beat you swing, the
master ticks the blade down 5:

```text
wield a mono blade
attack training dummy       -> the fight runs on beats; @examine the
                               blade between rounds: condition 95, 90...
```

At 25 the room hears "a mono blade is looking battered."; at 0, "a mono
blade gives out with a crack!" — and once you lower it:

```text
unwield
wield a mono blade          -> The mono blade is a ruin of snapped
                               segments. It needs a bench.
repair a mono blade         -> ...good as new for 50 credits.
wield a mono blade          -> You ready a mono blade.
```

The 50 credits are *gone* — the bench balance stays flat, the economy
shrank. The welder tells the same story faster: `use an arc welder`
twice (20 → 10 → 0), then a third `use` is refused by its own ward
until `repair an arc welder` (10 credits) revives it.

**Engine gap (noted for the integrator):** event triggers bind only the
enactor — a witness of `combat:on_damage` cannot identify the defender,
so armor wear on the *receiving* side can't be booked from a master.
Binding the action's target (and payload, e.g. damage amount) into the
trigger namespace — as wards get via `adata` — would unlock it; today
armor wear needs the audit's zone-master pattern *plus* that binding.

## Going further

- **Time and weather age.** A zone master's `on_tick` sweeping
  `search_world(tag='rusts')` for -1 condition per pulse — the wear
  event you don't have, built from the heartbeat you do.
- **Condition prices the resale.** Shopkeepers (063) buy at
  `value * condition / 100` — one multiplication makes wear economically
  real everywhere at once.
- **Break consequences.** At 0, the master could also strip the
  `wielded` tag's *benefits* by swapping the weapon's `value` to scrap —
  or emit an `act(me, ..., action_type='event:weapon_broke')` for any
  `ON_WEAPON_BROKE` drama in the room.
- **Field kits.** A carried `$patch *` tool that restores 20 condition,
  costs a use of *itself* (the welder's self-wear), and works only out
  of combat — bench economics with a wilderness price.
