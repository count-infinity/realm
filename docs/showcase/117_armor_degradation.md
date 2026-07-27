# 117. Armor degradation

> Checklist item 117 ([now]): *ON_DAMAGE bookkeeping, DR attrs, repair sinks*

**What you'll build:** A flak vest that actually stops bullets, using the
ruleset's native damage-resistance stat, and wears out doing it: every hit
costs the vest exactly the damage it stopped, a shredded vest stops nothing, and
an armorer's bench with a real skill roll is the repair sink.

**Concepts:** the native soak model (`damage_resistance` on the combatant),
`ON_WEAR` and `ON_REMOVE` as the equip hooks, an `ON_DAMAGE` hook on the wearer
as the wear bookkeeping, reading the in-flight action with
[`adata('damage')`](../reference/softcode.md#event-data-namespace), and admin
owner authority for writing player sheets. [Durability repair](095_durability_repair.md)
builds the mirror of this on a room witness instead.

## How it works

The finished outfitter has three moving parts: a flak vest that grants real
damage resistance when worn, a bookkeeping hook that spends the vest's ceramic
as blows land on the wearer, and a bench that restores the ceramic with a skill
roll. Nothing in the engine knows what "plating" means; it is an attribute the
vest defines, and every rule below is softcode reading and writing it. This
section answers five questions: what the ruleset reads for armor, how wearing
the vest installs that stat, why the bookkeeping lives on the wearer rather than
the vest, how the hook tells the wearer's own wound from a neighbour's, and why
this has to be an admin build.

### What does the ruleset read for armor?

The GURPS ruleset reads one stat at damage time: `damage_resistance` on the
defender. It is flat DR subtracted from every damage roll before the type
multipliers, exactly GURPS's armor line. That is the whole native model, a
single number on the combatant. There is no built-in plumbing from worn gear to
that stat, because the `wear` command natively grants tags through
`grants_tags`, never stats, which is the gap this tutorial's softcode fills.

### How wearing the vest installs the soak

The vest is an ordinary `wearable` in the `torso` slot, so players ready it with
the real `wear` and `remove` commands, and those fire the vest's gated `ON_WEAR`
and `ON_REMOVE` [hooks](../reference/softcode.md#lifecycle-hooks) with the wearer
as `enactor`. On wear, the vest writes three things onto its wearer with
[`set_attr`](../reference/softcode.md#fn-set_attr): `damage_resistance` (the
native soak), `armor_plating` (a copy of the vest's remaining ceramic), and an
`on_damage` hook. On removal it copies the surviving plating back onto the vest
and clears all three.

### Why the bookkeeping lives on the wearer

The `on_damage` hook runs as the wearer, and players control themselves, so it
can spend the wearer's `armor_plating` and, at zero, clear the wearer's own
`damage_resistance`. A bystander who hears the same event can write none of
that. The rule worth learning is to put bookkeeping on the object that owns the
state, not on whoever happened to witness the event. The hook could never write
the vest, because players do not own it, which is why the plating is copied onto
the wearer while the vest is worn and copied back on removal.

### How the hook tells your wound from a neighbour's

`combat:on_damage` is a witnessed event: it fires the `ON_DAMAGE`
[hook](../reference/softcode.md#lifecycle-hooks) of every object in the room, not
only whoever got hit. So the wearer's hook also runs when the person beside them
takes a sword. `me` is still the wearer, because it is still the wearer's hook,
but the blow was not theirs. `target` is the defender, and
[`target is me`](../reference/softcode.md#guard-on-target) is the only thing that
separates the two. Leave it out and the vest wears from other people's wounds:
stand in a busy room and the ceramic is gone before anyone touches the wearer.
Write `is`, not `==`, because it is an identity check.

With the guard settled, `ON_DAMAGE` carries the payload:
[`adata('damage')`](../reference/softcode.md#event-data-namespace) is the damage
roll and `adata('damage_types')` its breakdown by type. That is what makes the
wear point-accurate: the vest spends `min(DR, damage)`, exactly the points of
ceramic that stood between the wearer and the wound. A graze for 1 costs one
point; a shell for 20 costs the full DR 3 and no more, because 3 is all the vest
ever stopped.

### Why this is an admin build

`ON_WEAR` runs as the vest, and the vest writes its wearer's sheet, three
attributes on a player. Softcode wields its owner's authority, and only admins
control other players, so the outfitter's stock must be admin-owned.
[`set_attr`](../reference/softcode.md#fn-set_attr) on a player from a
builder-owned vest returns False and writes nothing, silently and correctly.

### When the hook runs relative to the wound

`ON_DAMAGE` fires per hit that got through active defenses, after the damage is
rolled but before it is applied, and `damage_resistance` is read at apply time
(see the [before, apply, after trio](../design/action-phases.md)). So the hook
and the wound land in the same instant: the blow that spends the vest's last
point is the first one that gets through, because the hook zeroed the DR just
before the ruleset subtracted it.

## Build it

As an admin. First the room, the vest, and its numbers. Here `plating` is points
of ceramic, not a plate count: the number of damage points this carrier can eat
before it is gravel.

```text
@dig The Outfitter = outfitter, out
outfitter
@create flak vest
@tag flak vest = wearable
@set flak vest/slot = torso
@set flak vest/dr = 3
@set flak vest/plating = 9
@desc flak vest = Ceramic plates in a webbing carrier. [[p = V('plating', 0); result = 'The plates look factory-fresh.' if p >= 9 else ('Cracks spider across the plates.' if p > 0 else 'The carrier is full of ceramic gravel. It will stop nothing.')]]
```

Wearing installs the soak and the bookkeeping. The
[`target is me`](../reference/softcode.md#guard-on-target) guard matters even
here, because `item:on_wear` reaches every object in the room, so a second vest
lying nearby would otherwise install its own numbers onto the wearer. When the
plating is spent the vest reports itself shredded and installs nothing:

```text
@set flak vest/on_wear = '''
if target is me:  # item:on_wear reaches every room object; only the worn vest installs
    p = V('plating', 0)
    if p <= 0:
        pemit(enactor, 'The vest is shredded -- it will stop nothing until it is repaired.')
    else:
        set_attr(enactor, 'damage_resistance', V('dr', 3))
        set_attr(enactor, 'armor_plating', p)
        set_attr(enactor, 'on_damage', V('degrade'))
        pemit(enactor, 'You cinch the flak vest tight. (DR ' + str(V('dr', 3)) + ', ' + str(p) + ' points of plating)')
'''
```

The wear bookkeeping is stored on the vest under the inert name `degrade` and
copied onto the wearer as their live `on_damage` at wear time. Running as the
wearer, it reads the DR it installed with [`V`](../reference/softcode.md#fn-v),
spends `min(DR, blow)` of ceramic with [`decr`](../reference/softcode.md#fn-decr)
(which lowers the attribute and returns the new value in one call), and at zero
clears the wearer's DR so the breaking blow lands undefended:

```text
@set flak vest/degrade = '''
if target is me:  # combat:on_damage fires on every room object; only bill wounds to me
    soak = min(V('damage_resistance', 0), adata('damage', 0))
    p = V('armor_plating', 0)
    if soak > 0 and p > 0:
        if soak >= p:
            set_attr(me, 'armor_plating', 0)
            set_attr(me, 'damage_resistance', 0)
            pemit(me, 'Your vest takes the brunt -- and comes apart at the seams. It will stop nothing more.')
        else:
            pemit(me, 'Your vest soaks ' + str(soak) + ' -- ' + str(decr('armor_plating', soak)) + ' points of plating left.')
'''
```

Removing is the mirror. It copies the surviving plating back onto the vest with
[`get_attr`](../reference/softcode.md#fn-get_attr), then clears the three
attributes off the wearer with
[`del_attr`](../reference/softcode.md#fn-del_attr). It carries the same guard,
so a spare vest in the room does not steal the sync:

```text
@set flak vest/on_remove = '''
if target is me:  # sync the surviving plating back to the vest, then clear the wearer
    set_attr(me, 'plating', get_attr(enactor, 'armor_plating', 0))
    set_attr(enactor, 'damage_resistance', 0)
    del_attr(enactor, 'armor_plating')
    del_attr(enactor, 'on_damage')
    pemit(enactor, 'You shrug out of the vest.')
'''
drop flak vest
```

The repair bench is the sink that restores the ceramic. Create it and give it a
face:

```text
@create mending bench
drop mending bench
@desc mending bench = A scarred workbench of clamps and rivet guns. Drop armor here and REPAIR VEST.
```

Its `$`-command finds the dropped vest in the room, checks it is actually on the
bench with [`loc`](../reference/softcode.md#fn-loc), rolls the wearer's Armoury
with [`skill_check`](../reference/softcode.md#fn-skill_check), and on success
resets the plating and announces to the room with
[`remit`](../reference/softcode.md#fn-remit) and
[`name`](../reference/softcode.md#fn-name):

```text
@set mending bench/cmd_repair = '''
$repair vest:
v = get('flak vest')
if not (v and loc(v) is loc(me)):
    pemit(enactor, 'Lay the vest on the bench first -- drop it here.')
elif skill_check(enactor, 'armoury'):
    set_attr(v, 'plating', 9)
    remit(loc(me), name(enactor) + ' hammers the plating flat and rivets in fresh ceramic.')
else:
    pemit(enactor, 'You bend a plate the wrong way. No good.')
'''
```

## Try it

Put the vest on someone and let a thug (a flat 3 a swing) work them over:

```text
> get flak vest
> wear flak vest
You cinch the flak vest tight. (DR 3, 9 points of plating)
```

Hits one and two soak clean, because DR 3 eats the whole blow and the vest is
billed the 3 it stopped, so HP does not move:

```text
> attack pit thug
Your vest soaks 3 -- 6 points of plating left.
(the next hit)
Your vest soaks 3 -- 3 points of plating left.
```

On hit three the ceramic runs out:

```text
Your vest takes the brunt -- and comes apart at the seams. It will stop nothing more.
```

The hook runs while the damage is still in flight, so the blow that spends the
last of the ceramic is the first one that gets through: HP moves on hit three
and on every hit after. Change the thug's weapon and the arithmetic follows the
fiction. A 1-point graze buys nine grazes; a 20-point slug still spends only 3,
because 3 is what the vest stopped. Afterwards the wear syncs back onto the vest,
a shredded vest refuses to soak, and the bench trues it with an Armoury check:

```text
> remove flak vest
You shrug out of the vest.
> wear flak vest
The vest is shredded -- it will stop nothing until it is repaired.
> remove flak vest
> drop flak vest
> repair vest
Nia hammers the plating flat and rivets in fresh ceramic.
> get flak vest
> wear flak vest
You cinch the flak vest tight. (DR 3, 9 points of plating)
```

**Engine gap (reported):** there is no native plumbing from worn gear to a
combat stat, since `wear` grants tags through `grants_tags` and never stats, so
installing `damage_resistance` at all requires admin-owned softcode. The
`ON_DAMAGE` payload carries `target` and
[`adata(...)`](../reference/softcode.md#event-data-namespace), which is exactly
what the point-accurate `degrade` hook above spends.

## Going further

- **Soak as a ward instead of DR.** The wearer's `on_check` can `mod(-3)` a
  `combat:on_damage` in flight (a decision-only reducer that runs on the target),
  giving armor that composes with, or replaces, the native DR stat.
- **Priced repairs.** Make the bench demand `pay` first: an `ON_PAYMENT` till
  (see the [bartender](064_bartender.md)) that banks one repair credit per 20
  paid.
- **Damage-type plating.** `adata('damage_types')` is the roll broken down by
  type (`{'burning': 6}`), so ceramic can hate lasers: spend
  `2 * adata('damage_types', {}).get('burning', 0)` alongside the ordinary soak,
  and the same vest that shrugs off bullets cooks through in two shots.
- **Weapon wear.** The mirror build. `combat:on_attack` carries
  `adata('weapon')` and `target`, so a room witness (the
  [arena](115_arena_spectators.md), the [combat replay log](120_combat_replay.md))
  can bill the right weapon for the right swing. The attacker's own hooks never
  fire on their own swing, so a witness is how you reach it.
