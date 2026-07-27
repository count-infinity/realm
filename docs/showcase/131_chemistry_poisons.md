# 131. Chemistry & Poisons

> Checklist item 131 ([now]): *risky recipes, failure effects, skill prereqs*

**What you'll build:** A synthesis rig that mixes fictional reagents
into medicines and industrial acids behind three locks (a studied
*pathway*, a certification-level skill floor, and reagents in hand). A
bad roll wastes the batch, and a worse one flashes back in a caustic
spray that keeps burning the mixer.

**Concepts:** risk as margin bands (success, inert sludge, or a fumble
on a miss by 5 or more, each with its own consequence), the effect
machinery ([`apply_effect`](../reference/softcode.md#fn-apply_effect)
with `damage_over_time`) turned on the *crafter* so the
[dart trap](052_poison_dart_trap.md)'s proximity authority points
inward and the rig may burn whoever operates it, restricted knowledge
via [126's](126_blueprints.md) pattern (`known_formulas` on the
player, written by an admin-owned chip), a numeric skill prerequisite
distinct from the roll, and the product as its own counterplay
(mendicine gel cures the burn the rig inflicts).

## How it works

The finished rig answers `mix mend` in two stages: three refusals that
never touch the dice, then a single graded roll whose worst outcome
bites back. A licensed, stocked mixer rolls their chemistry, and a made
roll fills a vial, a near miss wastes the batch, and a bad miss sprays
the mixer with a lingering burn that the vial itself can cure. This
section answers three questions: how the three gates order themselves,
why the fumble is an engine effect rather than a message, and how the
medicine reaches the person holding it.

### The three gates, in order

`$mix mend` refuses in a fixed order before it ever rolls. First an
unknown formula (a typo). Then an unverified *pathway* (`no verified
pathway for mend in your neural index`), because the knowledge is an
attribute the player studies from a chip, exactly [126's](126_blueprints.md)
admin-owned write. Then certification (`CHEM-10 required (your
chemistry: 0)`), a flat floor on
[`get_attr`](../reference/softcode.md#fn-get_attr)`(enactor,
'skill_chemistry')`, because some chemistry a mixer should not even
attempt undertrained. Then the reagent counts by tag, the same
[122](122_recipe_crafting.md) arithmetic that counts
[`contents`](../reference/softcode.md#fn-contents)`(enactor)` with
[`has_tag`](../reference/softcode.md#fn-has_tag). Only a fully
licensed, stocked mixer ever reaches the dice.

### Why the fumble is an engine effect, not a message

The roll is a graded [`margin_under`](../reference/softcode.md#fn-margin_under)
of [`roll`](../reference/softcode.md#fn-roll)`('3d6')` against your
chemistry. A success fills the cradle with a vial minted by
[`create_obj`](../reference/softcode.md#fn-create_obj). A miss by 1 to
4 curdles the batch: the reagents are already spent by
[`destroy_obj`](../reference/softcode.md#fn-destroy_obj), the dice are
quoted, and the lesson is cheap. A miss by 5 or more is a fumble: the
rig sprays, [`damage`](../reference/softcode.md#fn-damage) takes a
bite, and `apply_effect(enactor, 'damage_over_time', kind='chem_burn',
...)` attaches a ticking, tagged condition that persists across a
reboot rather than printing a one-off line. The authority is
proximity, the same license the [dart trap](052_poison_dart_trap.md)
uses: an object may hurt whoever stands at it, and here that reaches
the mixer at the bench.

### How the medicine reaches its user

A successful `mend` batch is a vial whose own `$apply gel` strips
`chem_burn` with [`remove_effect`](../reference/softcode.md#fn-remove_effect)
and restores 2 HP with [`heal`](../reference/softcode.md#fn-heal). The
rig stamps that command onto the vial at creation with
[`set_attr`](../reference/softcode.md#fn-set_attr) and keeps the master
copy in its own `gel_code`, the [galley](129_cooking_buffs.md)'s
stamp-the-spawn pattern. The vial refuses while you hold it
(`loc(me) == enactor`) and asks to be set down first, a deliberate gate
rather than a reach limit, so once it rests in the room it heals the
room-mate who applies it. Everything stays fictional: mendicine, kryl
etchant, biomass, and solvent are sci-fi glassware, not real recipes.

## Build it

Build the whole lab as an admin, because the formula chip writes a
player's own sheet and that write carries owner authority
([126's](126_blueprints.md) rule). Start with the rig, its catalogue,
and the two formulas as data:

```text
@create synthesis rig
drop synthesis rig
@desc synthesis rig = A fume-hooded synthesis rig of coiled glass and ceramic pumps. Its status ring idles amber. MIX here -- if you are licensed.
@set synthesis rig/menu = ["mend", "etch"]
@set synthesis rig/form_mend = {"name": "a vial of mendicine gel", "tags": ["thing", "medicine"], "needs": {"biomass": 1, "solvent": 1}, "min_skill": 10, "apply": true, "value": 40, "blurb": "Cold blue gel that knits burns and scrapes. APPLY GEL once it is set down."}
@set synthesis rig/form_etch = {"name": "a flask of kryl etchant", "tags": ["thing", "acid"], "needs": {"solvent": 2}, "min_skill": 12, "apply": false, "value": 25, "blurb": "Amber etchant that whispers against its glass. Industrial use only."}
```

The gel's `$apply` command lives on the rig as `gel_code`, the master
copy the rig stamps onto every vial it mints. It refuses while the vial
is in hand, then strips the burn and heals the applier:

```text
@set synthesis rig/gel_code = '''
$apply gel:
if loc(me) == enactor:
    pemit(enactor, 'Set the vial down first; the applicator wants a steady base.')
else:
    remove_effect(enactor, 'chem_burn')
    heal(enactor, 2)
    pemit(enactor, 'The gel knits skin cold and quick; the burning stops.')
    remit(here, name(enactor) + ' smooths mendicine gel over the burns.')
    destroy_obj(me)
'''
```

The catalogue browser prints one line per formula, with its
certification and reagents spelled out:

```text
@set synthesis rig/cmd_formulas = $formulas: [pemit(enactor, '  ' + s + ' -> ' + V('form_' + s)['name'] + ' (CHEM-' + str(V('form_' + s)['min_skill']) + '; needs: ' + ', '.join(f'{n}x {t}' for t, n in V('form_' + s)['needs'].items()) + ')') for s in V('menu', [])]
```

The mixer runs the three gates as an `if`/`elif` chain, and only the
final `else` reaches the reagents, the roll, and the banded outcome.
Consumption burns the inputs before the roll, so every attempt costs
materials:

```text
@set synthesis rig/cmd_mix = '''
$mix *:
sel = trim(arg0).lower()
r = V('form_' + sel)
known = get_attr(enactor, 'known_formulas', [])
lvl = get_attr(enactor, 'skill_chemistry', 0)
if not r:
    pemit(enactor, 'The rig lists no such formula. Try formulas.')
elif sel not in known:
    pemit(enactor, f'The rig refuses: no verified pathway for {sel} in your neural index.')
elif lvl < r['min_skill']:
    pemit(enactor, f'The rig refuses: certification CHEM-{r["min_skill"]} required (your chemistry: {lvl}).')
else:
    carried = contents(enactor)
    short = [str(n - len([o for o in carried if has_tag(o, t)])) + 'x ' + t for t, n in r['needs'].items() if len([o for o in carried if has_tag(o, t)]) < n]
    if short:
        pemit(enactor, 'Reagents short: ' + ', '.join(short) + '.')
    else:
        for t, n in r['needs'].items():
            for o in [x for x in carried if has_tag(x, t)][:n]:
                destroy_obj(o)
        res = margin_under(roll('3d6'), lvl)
        if res.success:
            v = create_obj(r['name'], r['tags'], here)
            if r['apply']:  # only mendicine carries the applicator command
                set_attr(v, 'cmd_apply', V('gel_code'))
            set_attr(v, 'value', r['value'])
            set_attr(v, 'desc_extras', [['', r['blurb']]])
            remit(here, f'The rig cycles green; {r["name"]} fills in the cradle. (margin +{res.margin})')
        elif res.margin > -5:
            remit(here, f'The mix curdles into inert sludge. (rolled {res.roll} vs chemistry {res.effective})')
        else:
            remit(here, 'The rig shrieks -- the mix flashes back in a caustic spray!')
            damage(enactor, roll('1d2'))
            apply_effect(enactor, 'damage_over_time', kind='chem_burn', damage=1, interval=1, duration=4, tick_msg='Caustic residue eats at your skin!', room_msg='{name} claws at smoking sleeves.', expire_msg='The last of the residue burns itself out.')
'''
```

Last, the pathway chip. It teaches [126's](126_blueprints.md) way,
minus the self-wipe, since a lab keeps its references:

```text
@create mend formula chip
drop mend formula chip
@desc mend formula chip = A ceramic data-chip etched MEND-7G. MEMORIZE CHIP to take the synthesis pathway.
@set mend formula chip/formula = mend
```

Its `$memorize` command writes the studied formula onto the player's
`known_formulas` list. The write returns `False` on a chip without
owner authority, which is the branch that reports a refusal:

```text
@set mend formula chip/cmd_memorize = '''
$memorize chip:
f = V('formula')
k = get_attr(enactor, 'known_formulas', [])
if f in k:
    pemit(enactor, f'You already hold the {f} pathway.')
elif not set_attr(enactor, 'known_formulas', k + [f]):  # False = no owner authority
    pemit(enactor, 'The chip blinks: WRITE REFUSED (unlicensed chip).')
else:
    pemit(enactor, f'Cold data blooms behind your eyes: the {f} pathway is yours.')
'''
```

## Try it

Play a fresh mixer with reagents in hand (`biomass`- and
`solvent`-tagged, stocked on your own lab shelf). The first `mix`
bounces off the pathway gate, and `memorize chip` clears it:

```text
> mix mend
The rig refuses: no verified pathway for mend in your neural index.

> memorize chip
Cold data blooms behind your eyes: the mend pathway is yours.
```

The second `mix` now bounces off certification, because a fresh mixer
has chemistry 0:

```text
> mix mend
The rig refuses: certification CHEM-10 required (your chemistry: 0).
```

Train up (`@set me/skill_chemistry = 12` as the builder, or the
`improve` command in play) and mix again. The outcome is 3d6 against
your chemistry, so a made roll fills the cradle, a near miss curdles,
and a bad miss sprays. On a made roll:

```text
> mix mend
The rig cycles green; a vial of mendicine gel fills in the cradle. (margin +3)
```

The quoted margin and roll vary with your dice. `look` the vial for
its blurb and `@examine` it for `value: 40`. An ordinary miss wastes
the reagents and puts the dice on the record:

```text
> mix mend
The mix curdles into inert sludge. (rolled 15 vs chemistry 12)
```

A fumble (a miss by 5 or more) is the show: an immediate wound and a
ticking burn that reads `Caustic residue eats at your skin!` on each of
three beats, then clears itself on the fourth:

```text
> mix mend
The rig shrieks -- the mix flashes back in a caustic spray!
```

A vial set down earlier is the counterplay, any time before the burn
runs out:

```text
> apply gel
The gel knits skin cold and quick; the burning stops.
```

`mix etch` needs its own chip and CHEM-12, so restricted knowledge
scales one formula at a time.

## Going further

- **Poisons with consent problems:** a `toxin`-tagged output cannot be
  *used on* someone by softcode fiat, so deliver it the trap way. Coat
  a blade (`ON_ATTACK`), spike a bottle (a `$drink` that calls
  `apply_effect`), or arm a [dart trap](052_poison_dart_trap.md).
- **Volatile stock:** [`expire`](../reference/softcode.md#fn-expire)`(v,
  600)` on each vial gives medicines a shelf life, and a reason the
  [icebox](018_refrigerator.md) is lab equipment.
- **Signature accidents:** key the fumble on the formula, so etchant
  fumbles eat the *rig* (`damage(me, ...)` and a `disabled` tag until
  repaired) instead of the mixer.
- **Black-market pathways:** chips as loot and heist objectives,
  because the knowledge attribute is portable, findable, and
  steal-proof: it lives on your sheet, not in your pack.
