# 095. Item durability & repair

> Checklist item 95 — [now] — *durability attrs, master ON_ATTACK bookkeeping, $repair*

**What you'll build:** gear that wears out and a bench that charges to
fix it: weapons lose condition with every combat swing and armour with
every blow it stops (a room-master's `ON_ATTACK` and `ON_DAMAGE` do the
bookkeeping), tools lose it on every `use` (their own `ON_USE` does),
ruined gear refuses to be readied (an `on_check` ward), and the repair
bench burns credits — a true money sink.

**Concepts:** a `condition` attribute as the wear state; **which engine
events can honestly drive wear** (and how the event payload decides);
witness-side `ON_ATTACK`/`ON_DAMAGE` bookkeeping on a master; `target`
and `adata('damage')` as the difference between "someone was hit" and
"*they* were hit for *this much*"; self-mutating `ON_USE` on tools;
gated `item:on_wield` / `item:on_wear` refused by an `on_check` ward;
`$repair` with `adjust_credits(me, -cost)` as an explicit credit burn.

## How it works

**Be honest about what fires.** Durability systems die of wishful
thinking, so start from the engine's actual event surface:

- **Combat swings**: every attack propagates `combat:on_attack` (before
  the to-hit roll — a whiff still wears the blade), witnessed by the
  room, its contents, and zone masters. A *wear master* standing in the
  room hears every swing.
- **Landed blows**: a hit that does damage propagates `combat:on_damage`
  — and its payload carries both `target` (who took it) and
  `adata('damage')` (how hard). That's the armour event.
- **Deliberate use**: the `use` builtin propagates `item:on_use` at the
  target — the tool itself can carry the `ON_USE` that wears it.
- **`$`-verb tools** (a welding rig's own `$weld *`): the verb script
  can decrement its own condition inline — self-mutation is always
  within an object's authority.

**The payload is what makes each of these honest.** An observer script
gets the same names a ward gets: `actor` (who swung), `target` (who it
landed on), and `adata(key)` for the action's data. That is precisely
what defender-side wear needs — `enactor` alone would only ever tell you
who *attacked*, so armour would have nowhere to hang. Read the two hooks
side by side and the design falls out: `ON_ATTACK` fires per *swing* and
knows the attacker, so it wears the **weapon** by a flat amount (whiffs
included — the blade is levered whether or not it connects). `ON_DAMAGE`
fires per *landed blow* and knows the victim and the number, so it wears
the **armour** by the damage it stopped. Wear that scales with what
actually hit you is the honest booking, and the payload is what makes it
sayable.

What still **cannot** drive wear: walking, carrying, and time fire no
item events at all; if you want age, put it on a ticker (see Going
further).

**The bookkeeping lives on a witness, the gate lives on the item.** The
wear master's `ON_ATTACK` finds the enactor's `wielded`-tagged item and
knocks 5 off its `condition` (admin authority may mutate a player's
gear); its `ON_DAMAGE` does the mirror image on `contents(target)` for
`worn`-tagged items. Both announce at the battered threshold and at
zero. One witness object, two hooks, every piece of gear in the room
accounted for. The items themselves carry the *refusal*: `item:on_wield`
and `item:on_wear` are gated events, so an `on_check` ward on the weapon
or the vest vetoes readying it at condition 0. A broken blade already in
hand keeps swinging its ruined swings, and a shredded vest already worn
keeps being worn — the engine has no per-swing equipment check pass —
but once lowered or taken off, neither comes back until repaired. Say so
to your players; honest rules beat leaky ones.

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

And the mirror hook for armour. `ON_DAMAGE` only fires when a blow
actually lands, so this is `contents(target)` — the *victim's* pack, not
the attacker's — and the wear is `adata('damage')`, the size of the blow
the plate just soaked:

```text
@set the wear master/ON_DAMAGE = [(set_attr(o, 'condition', c), remit(here, f'{name(o)} is scarred and dented.') if c == 25 else None, remit(here, f'{name(o)} comes apart at the seams!') if c == 0 else None) for o in contents(target) if has_tag(o, 'worn') for c in [max(0, get_attr(o, 'condition', 100) - adata('damage', 1))]]
```

(`contents(target)` is safe on a hook that somehow arrives without one:
`contents(None)` is the empty list, so the comprehension simply does
nothing.)

A weapon that starts sound and refuses to be readied once ruined — the
ward runs in the gated `item:on_wield` check pass:

```text
@create a mono blade
@set a mono blade/value = 40
@set a mono blade/condition = 100
@set a mono blade/on_check = block('The mono blade is a ruin of snapped segments. It needs a bench.') if atype == 'item:on_wield' and V('condition', 100) <= 0 else None
```

And its defensive counterpart — `wearable` is what makes the `wear`
builtin accept it, and the ward gates `item:on_wear` exactly as the
blade's gates `item:on_wield`:

```text
@create a flak vest
@tag a flak vest = wearable
@set a flak vest/value = 30
@set a flak vest/condition = 100
@set a flak vest/on_check = block('The flak vest is split webbing and loose plate. It needs a bench.') if atype == 'item:on_wear' and V('condition', 100) <= 0 else None
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

Now stand still and let something hit *you*:

```text
wear a flak vest            -> You put on the a flak vest.
(something in the yard swings back)
                            -> the vest drops by the damage each blow does
```

At 25 the room hears "a flak vest is scarred and dented."; at 0, "a flak
vest comes apart at the seams!" — and `remove a flak vest` then `wear a
flak vest` gets the vest's own refusal until the bench trues it. Note
the asymmetry, and that it's deliberate: the blade wears on every swing
you *throw*, the vest only on blows that actually *land*. A fight you
dominate ruins your weapon and leaves your armour untouched.

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
