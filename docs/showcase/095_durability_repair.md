# 095. Item durability & repair

> Checklist item 95 ([now]): *durability attrs, zone-master ON_DAMAGE bookkeeping, $repair*

**What you'll build:** gear that wears out and a bench that charges to fix it.
Weapons lose condition with every combat swing and armour with every blow it
stops, a witness object in the room does that bookkeeping, tools lose condition
on every `use`, ruined gear refuses to be readied, and the repair bench burns
the fee so it is a true money sink.

**Concepts:** a `condition` attribute as the wear state; which engine events
can honestly drive wear (and how the event payload decides); a global witness
object doing `combat:on_attack` and `combat:on_damage` bookkeeping;
[`target`](../reference/softcode.md#guard-on-target) and
[`adata('damage')`](../reference/softcode.md#event-data-namespace) as the
difference between "someone was hit" and "*they* were hit for *this much*";
a guarded self-mutating `ON_USE` on a tool; gated `item:on_wield` and
`item:on_wear` refused by an `on_check` ward;
[`$repair`](../reference/softcode.md#lifecycle-hooks) with
[`adjust_credits(me, -cost)`](../reference/softcode.md#fn-adjust_credits) as an
explicit credit burn.

## How it works

The finished yard has three moving parts: gear that carries a `condition`
number, a witness object that docks that number as fights play out, and a bench
that charges to restore it. Nothing in the engine knows what `condition` means;
it is an attribute you define, and every rule below is softcode reading and
writing it. This section answers four questions: which engine events can
honestly drive wear, why the attacker's swing and the defender's bruise are two
different events, where the refusal to ready broken gear lives, and why repair
destroys money instead of moving it.

### Which events can honestly drive wear?

Durability systems die of wishful thinking, so start from the engine's real
event surface. The propagation model (see
[action phases](../design/action-phases.md) and
[245 for a tour](245_event_bus_tour.md)) gives you three honest hooks:

- **Combat swings.** Every attack propagates `combat:on_attack` before the
  to-hit roll, so a whiff wears the blade just as a hit does. It is witnessed
  by the room, its contents, and any zone masters, so a witness object standing
  in the room hears every swing.
- **Landed blows.** A hit that deals damage propagates `combat:on_damage`, and
  its payload carries both the `target` who took it and
  [`adata('damage')`](../reference/softcode.md#event-data-namespace), how hard.
  That is the armour event.
- **Deliberate use.** The `use` builtin propagates `item:on_use` at the thing
  used, so a tool can carry the [`ON_USE`](../reference/softcode.md#lifecycle-hooks)
  that wears it.

What cannot drive wear: walking, carrying, and the passage of time fire no item
events at all, so if you want age, put it on a ticker (see Going further).

### Why the swing and the bruise are two events

The payload is what makes each of these honest. A reactive script gets the same
names a ward gets: `actor` (who swung), `target` (who it landed on), and
`adata(key)` for the action's data. Read the two combat hooks side by side and
the design falls out. `combat:on_attack` fires per swing and names the
attacker, so it wears the **weapon** by a flat amount, whiffs included, because
the blade is levered whether or not it connects. `combat:on_damage` fires per
landed blow and names the victim and the number, so it wears the **armour** by
the damage it stopped. If you only had `enactor`, you would know who attacked
but never whose armour to dock, which is exactly why the defender-side event
carries `target`. Wear that scales with what actually hit you is the honest
booking, and the payload is what makes it sayable.

### Where the bookkeeping lives, and where the refusal lives

The bookkeeping lives on a witness; the refusal lives on the item. The wear
master is a plain object dropped in the room. A reactive `ON_<EVENT>` hook fires
on every object that witnessed the action, and the master witnessed the whole
fight without being either side of it, so it is a **global witness** (like a
scoreboard) and takes no [`target is me`](../reference/softcode.md#guard-on-target)
guard: it is meant to watch everyone. Its `ON_ATTACK` finds the attacker's
`wielded`-tagged weapon in
[`contents(enactor)`](../reference/softcode.md#fn-contents) and knocks 5 off,
and its `ON_DAMAGE` does the mirror on `contents(target)` for `worn` gear. One
consequence of the global-witness pattern: drop two wear masters in one room and
every swing is counted twice, so keep one per combat zone.

The items themselves carry the *refusal*. `item:on_wield` and `item:on_wear`
are gated events, so an `on_check` ward on the weapon or the vest can
[`block()`](../reference/softcode.md#event-data-namespace) readying it at
condition 0. An `on_check` ward runs only on the object the action actually
targets, never on bystanders, so a broken blade lying on the floor cannot veto
readying a sound one and the ward needs no guard. A blade broken while already
in hand keeps swinging its ruined swings, and a shredded vest already worn keeps
being worn, because the engine has no per-swing equipment check pass; only
readying or donning is gated. Once lowered or taken off, neither comes back
until the bench trues it, so say as much to your players. (Item 117,
[armor degradation](117_armor_degradation.md), builds the same wear on the
defence side alone.)

### Why the tool's ON_USE needs a guard when the master's does not

The arc welder wears itself: it is the target of its own `item:on_use`, so its
`ON_USE` can dock its own condition without any master. But that same event
reaches every object in the room, and a second welder lying on the floor would
hear the first one being used and wear itself down too, even messaging the user
about a tool they never touched. So the welder's `ON_USE` opens with
`if target is me:` before it mutates, the standard guard for a reactive hook
that reacts to its own business. The wear master needs no such guard precisely
because it is nobody's own business; it is the deliberate global witness that
watches the whole room. The two hooks show both halves of the rule at once.

### Why repair is a sink, not a transfer

The bench takes the fee with
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits), which is also
the wallet check, then *burns* it with `adjust_credits(me, -cost)`, so the
credits leave the economy entirely. Faucets such as job wages and interest need
matching drains or prices inflate forever, and repair is the classic drain
because breakage scales with activity. The `repair` command is a `$`-trigger,
which fires only on the bench and only for the player who typed it, so it needs
no guard.

## Build it

Dig the yard and drop the two fixtures: the wear master (a plain witness object;
drop one per combat zone, or tag a zone master the same way) and the bench.

```text
@dig The Sparring Yard
@teleport The Sparring Yard
@create the wear master
drop the wear master
@create the repair bench
drop the repair bench
```

The per-swing bookkeeping. On every attack the master witnesses, it walks the
attacker's inventory with [`contents`](../reference/softcode.md#fn-contents),
finds the `wielded` weapon with
[`has_tag`](../reference/softcode.md#fn-has_tag), reads and rewrites its
condition down 5 with [`get_attr`](../reference/softcode.md#fn-get_attr) and
[`set_attr`](../reference/softcode.md#fn-set_attr), and announces to the room
with [`remit`](../reference/softcode.md#fn-remit) at the battered threshold and
at zero:

```text
@set the wear master/ON_ATTACK = '''
for o in contents(enactor):
    if has_tag(o, 'wielded'):
        c = max(0, get_attr(o, 'condition', 100) - 5)
        set_attr(o, 'condition', c)
        if c == 25:
            remit(here, f'{name(o)} is looking battered.')
        if c == 0:
            remit(here, f'{name(o)} gives out with a crack!')
'''
```

And the mirror hook for armour. `ON_DAMAGE` only fires when a blow actually
lands, so this walks `contents(target)`, the *victim's* pack rather than the
attacker's, and wears the `worn` gear by `adata('damage', 1)`, the size of the
blow the plate just soaked. (`contents(target)` is safe on a hook that somehow
arrives without a target: `contents(None)` is the empty list, so the loop simply
does nothing.)

```text
@set the wear master/ON_DAMAGE = '''
for o in contents(target):
    if has_tag(o, 'worn'):
        c = max(0, get_attr(o, 'condition', 100) - adata('damage', 1))
        set_attr(o, 'condition', c)
        if c == 25:
            remit(here, f'{name(o)} is scarred and dented.')
        if c == 0:
            remit(here, f'{name(o)} comes apart at the seams!')
'''
```

A weapon that starts sound and refuses to be readied once ruined. The ward runs
in the gated `item:on_wield` check pass, and because `on_check` fires only on
the targeted item, it reads its own condition with
[`V`](../reference/softcode.md#fn-v) and needs no guard:

```text
@create a mono blade
@set a mono blade/value = 40
@set a mono blade/condition = 100
@set a mono blade/on_check = block('The mono blade is a ruin of snapped segments. It needs a bench.') if atype == 'item:on_wield' and V('condition', 100) <= 0 else None
```

Its defensive counterpart. The `wearable` tag is what lets the `wear` builtin
accept it, and the ward gates `item:on_wear` exactly as the blade's gates
`item:on_wield`:

```text
@create a flak vest
@tag a flak vest = wearable
@set a flak vest/value = 30
@set a flak vest/condition = 100
@set a flak vest/on_check = block('The flak vest is split webbing and loose plate. It needs a bench.') if atype == 'item:on_wear' and V('condition', 100) <= 0 else None
```

A tool that wears itself on every `use`, with no master needed because the tool
is the target of `item:on_use`:

```text
@create an arc welder
@set an arc welder/condition = 20
```

The `if target is me:` guard is essential: the event reaches every object in the
room, so without it a second welder on the floor would wear itself on your swipe
and message you about it. A ward at the bottom refuses use at zero:

```text
@set an arc welder/ON_USE = '''
if target is me:  # item:on_use reaches every object in the room, so gate on the target
    c = max(0, V('condition', 100) - 10)
    set_attr(me, 'condition', c)
    pemit(enactor, f'The welder spits a bead of blue flame. (condition {c})')
'''
@set an arc welder/on_check = block('The welder is burnt out. It needs a bench.') if atype == 'item:on_use' and V('condition', 100) <= 0 else None
```

Finally the bench command. It finds the named item in your pack, prices the fee
at half the missing condition, takes the fee as the wallet check, then burns the
fee and trues the item. The single `else` covers both an empty match and a
wallet too short, since the transfer is the last term of the `if` and does not
run when the earlier terms are false:

```text
@set the repair bench/cmd_repair = '''
$repair *:
matches = [o for o in contents(enactor) if name(o).lower() == arg0.strip().lower()]
item = matches[0] if matches else None
c = get_attr(item, 'condition', 100) if item else 100
cost = max(1, (100 - c) // 2)
if item and c < 100 and transfer_credits(enactor, me, cost):
    set_attr(item, 'condition', 100)
    adjust_credits(me, -cost)  # burn the fee so repair is a sink, not a transfer
    pemit(enactor, f'The bench grinds, reseats and trues {name(item)}: good as new for {cost} credits.')
else:
    pemit(enactor, 'Nothing to repair, or you cannot cover the fee.')
'''
```

## Try it

Wield the blade and pick a fight in the yard. Every swing, the master ticks the
blade down 5, so `@examine` it between rounds to watch it fall:

```text
> wield a mono blade
You ready a mono blade.
> attack training dummy
(the fight runs on beats; @examine the blade between rounds: condition 95, 90, ...)
```

At 25 the room hears the battered warning, and at 0 the break notice, after
which the ward refuses to ready it until the bench trues it:

```text
(condition reaches 25)
a mono blade is looking battered.
(condition reaches 0)
a mono blade gives out with a crack!
> unwield
You lower a mono blade.
> wield a mono blade
The mono blade is a ruin of snapped segments. It needs a bench.
> repair a mono blade
The bench grinds, reseats and trues a mono blade: good as new for 50 credits.
> wield a mono blade
You ready a mono blade.
```

The 50 credits are *gone*: the bench balance stays flat, so the economy shrank
by exactly the fee. The welder tells the same story faster. Two uses take it
from 20 to 0, and a third is refused by its own ward until the bench revives it:

```text
> use an arc welder
The welder spits a bead of blue flame. (condition 10)
> use an arc welder
The welder spits a bead of blue flame. (condition 0)
> use an arc welder
The welder is burnt out. It needs a bench.
> repair an arc welder
The bench grinds, reseats and trues an arc welder: good as new for 50 credits.
```

Now stand still and let something hit *you*. The vest drops by the damage each
blow does, announces at 25 and at 0, and then refuses to go back on until
repaired:

```text
> wear a flak vest
You put on a flak vest.
(a partner in the yard swings back and lands a blow; the vest drops by the damage)
(condition reaches 25)
a flak vest is scarred and dented.
(condition reaches 0)
a flak vest comes apart at the seams!
```

Note the asymmetry, and that it is deliberate: the blade wears on every swing
you *throw*, the vest only on blows that actually *land*. A fight you dominate
ruins your weapon and leaves your armour untouched.

## Going further

- **Time and weather age.** A zone master's `on_tick` sweeping
  [`search_world(tag='rusts')`](../reference/softcode.md#fn-search_world) for -1
  condition per pulse gives you the wear event you do not have, built from the
  heartbeat you do.
- **Condition prices the resale.** A shopkeeper (see
  [063](063_shopkeeper.md)) can buy at `value * condition / 100`, so one
  multiplication makes wear economically real everywhere at once.
- **Break consequences.** At 0 the master could also strip the weapon's `value`
  to scrap, or emit an `act(me, ..., action_type='event:weapon_broke')` for any
  `ON_WEAPON_BROKE` drama in the room.
- **Field kits.** A carried `$patch *` tool that restores 20 condition, costs a
  use of *itself*, and works only out of combat gives you bench economics at a
  wilderness price.
