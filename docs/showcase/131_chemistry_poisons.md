# 131. Chemistry & Poisons

> Checklist item 131 — [now] — *risky recipes, failure effects, skill prereqs*

**What you'll build:** A synthesis rig that mixes fictional reagents
into medicines and industrial acids — behind three locks (a studied
*pathway*, a certification-level skill floor, and reagents in hand) —
where a bad roll wastes the batch and a *terrible* one flashes back
in a caustic spray that keeps burning the mixer for four beats.

**Concepts:** **risk as margin bands** (success / inert sludge /
fumble at margin ≤ −5, each with its own consequence),
`damage_over_time` turned on the *crafter* (the
[dart trap](052_poison_dart_trap.md)'s proximity authority pointed
inward — the rig may burn whoever operates it), **restricted
knowledge via [126's](126_blueprints.md) pattern**
(`known_formulas` on the player, written by an admin-owned chip),
a **numeric skill prerequisite** distinct from the roll, and the
product as its own counterplay (mendicine gel cures the burn the rig
inflicts).

## How it works

**Three gates, then dice.** `$mix mend` refuses in order: unknown
formula (typo), unverified *pathway* (`no verified pathway for mend
in your neural index` — knowledge is an attribute studied from a
chip, exactly 126's admin-owned write), then certification (`CHEM-10
required (your chemistry: 0)` — a flat floor on `skill_chemistry`,
because some chemistry you shouldn't even *attempt* undertrained),
then reagent counts by tag ([122's](122_recipe_crafting.md)
arithmetic). Only a fully licensed, stocked mixer ever rolls.

**Failure has bands, and the worst band bites.** The roll is a
graded `margin_under`. Success fills the cradle. A miss by 1–4
curdles the batch — reagents gone, dice quoted, lesson cheap. A miss
by 5+ is a fumble: the rig sprays, `damage()` takes a bite, and
`apply_effect(enactor, 'damage_over_time', kind='chem_burn', ...)`
keeps ticking for four beats — a persistent, reboot-proof,
tagged condition, not a one-off message. The authority is proximity:
like a trap, the rig may hurt whoever stands at it.

**The medicine closes its own loop.** A successful `mend` batch is a
vial whose `$apply gel` strips `chem_burn` (`remove_effect`) and
heals 2 — stamped onto the vial by the rig at creation, master copy
on the rig (`gel_code`), the [galley](129_cooking_buffs.md)'s
stamp-the-spawn pattern. Effects reach room-mates only, so the vial
asks to be set down first. Everything stays fictional: mendicine,
kryl etchant, biomass, solvent — sci-fi glassware, no real-world
recipes.

## Build it

**As an admin** (the formula chip writes player sheets — 126's
authority rule). The rig, its formulas, and the gel's script:

```text
@create synthesis rig
drop synthesis rig
@desc synthesis rig = A fume-hooded synthesis rig of coiled glass and ceramic pumps. Its status ring idles amber. MIX here -- if you are licensed.
@set synthesis rig/menu = ["mend", "etch"]
@set synthesis rig/form_mend = {"name": "a vial of mendicine gel", "tags": ["thing", "medicine"], "needs": {"biomass": 1, "solvent": 1}, "min_skill": 10, "apply": true, "value": 40, "blurb": "Cold blue gel that knits burns and scrapes. APPLY GEL once it is set down."}
@set synthesis rig/form_etch = {"name": "a flask of kryl etchant", "tags": ["thing", "acid"], "needs": {"solvent": 2}, "min_skill": 12, "apply": false, "value": 25, "blurb": "Amber etchant that whispers against its glass. Industrial use only."}
@set synthesis rig/gel_code = $apply gel: pemit(enactor, 'Set the vial down first; the applicator wants a steady base.') if loc(me) == enactor else (remove_effect(enactor, 'chem_burn'), heal(enactor, 2), pemit(enactor, 'The gel knits skin cold and quick; the burning stops.'), remit(here, name(enactor) + ' smooths mendicine gel over the burns.'), destroy_obj(me))
@set synthesis rig/cmd_formulas = $formulas: [pemit(enactor, '  ' + s + ' -> ' + V('form_' + s)['name'] + ' (CHEM-' + str(V('form_' + s)['min_skill']) + '; needs: ' + ', '.join(f'{n}x {t}' for t, n in V('form_' + s)['needs'].items()) + ')') for s in V('menu', [])]
```

The mixer — the three gates, then the banded roll:

```text
@set synthesis rig/cmd_mix = $mix *: sel = trim(arg0).lower(); r = V('form_' + sel); known = get_attr(enactor, 'known_formulas', []); lvl = get_attr(enactor, 'skill_chemistry', 0); carried = contents(enactor) if r else []; short = [str(n - len([o for o in carried if has_tag(o, t)])) + 'x ' + t for t, n in (r['needs'].items() if r else []) if len([o for o in carried if has_tag(o, t)]) < n]; pemit(enactor, 'The rig lists no such formula. Try formulas.') if not r else None; pemit(enactor, f'The rig refuses: no verified pathway for {sel} in your neural index.') if r and sel not in known else None; pemit(enactor, f'The rig refuses: certification CHEM-{r["min_skill"]} required (your chemistry: {lvl}).') if r and sel in known and lvl < r['min_skill'] else None; pemit(enactor, 'Reagents short: ' + ', '.join(short) + '.') if r and sel in known and lvl >= r['min_skill'] and short else None; go = bool(r) and sel in known and lvl >= r['min_skill'] and not short; res = margin_under(roll('3d6'), lvl) if go else None; ([destroy_obj(o) for t, n in r['needs'].items() for o in [x for x in carried if has_tag(x, t)][:n]], ([(set_attr(v, 'cmd_apply', V('gel_code')) if r['apply'] else None, set_attr(v, 'value', r['value']), set_attr(v, 'desc_extras', [['', r['blurb']]]), remit(here, f'The rig cycles green; {r["name"]} fills in the cradle. (margin +{res.margin})')) for v in [create_obj(r['name'], r['tags'], here)]] if res.success else (remit(here, f'The mix curdles into inert sludge. (rolled {res.roll} vs chemistry {res.effective})') if res.margin > -5 else (remit(here, 'The rig shrieks -- the mix flashes back in a caustic spray!'), damage(enactor, roll('1d2')), apply_effect(enactor, 'damage_over_time', kind='chem_burn', damage=1, interval=1, duration=4, tick_msg='Caustic residue eats at your skin!', room_msg='{name} claws at smoking sleeves.', expire_msg='The last of the residue burns itself out.'))))) if go else None
```

And the pathway chip — 126's teaching pattern, minus the self-wipe
(a lab keeps its references):

```text
@create mend formula chip
drop mend formula chip
@desc mend formula chip = A ceramic data-chip etched MEND-7G. MEMORIZE CHIP to take the synthesis pathway.
@set mend formula chip/formula = mend
@set mend formula chip/cmd_memorize = $memorize chip: f = V('formula'); k = get_attr(enactor, 'known_formulas', []); pemit(enactor, f'You already hold the {f} pathway.') if f in k else (pemit(enactor, 'The chip blinks: WRITE REFUSED (unlicensed chip).') if not set_attr(enactor, 'known_formulas', k + [f]) else pemit(enactor, f'Cold data blooms behind your eyes: the {f} pathway is yours.'))
```

## Try it

As a fresh mixer with reagents in hand (`biomass`- and
`solvent`-tagged — stock your own lab shelf):

```text
mix mend
memorize chip
mix mend
```

The first `mix` bounces off the pathway gate; after `Cold data blooms
behind your eyes`, the second bounces off certification: `CHEM-10
required (your chemistry: 0)`. Train up (`@set me/skill_chemistry =
12` as your builder, or the `improve` command in play) and mix again:
on a made roll, `The rig cycles green; a vial of mendicine gel fills
in the cradle. (margin +3)` — `look` the vial for its blurb, `@examine`
for `value: 40`. An ordinary miss curdles: `The mix curdles into
inert sludge. (rolled 15 vs chemistry 12)` — reagents gone. A fumble
(miss by 5+) is the show: the spray, an immediate wound, and
`Caustic residue eats at your skin!` each beat for four beats — then
`apply gel` from a set-down vial stops it: `The gel knits skin cold
and quick; the burning stops.` `mix etch` needs its own chip *and*
CHEM-12 — restricted knowledge scales.

## Going further

- **Poisons with consent problems:** a `toxin`-tagged output can't be
  *used on* someone by softcode fiat — deliver it the trap way:
  coat a blade (`ON_ATTACK`), spike a bottle (a `$drink` that
  `apply_effect`s), or arm a [dart trap](052_poison_dart_trap.md).
- **Volatile stock:** `expire(v, 600)` on each vial — medicines with
  shelf lives, and a reason the [icebox](018_refrigerator.md) is lab
  equipment.
- **Signature accidents:** key the fumble on the formula — etchant
  fumbles eat the *rig* (`damage(me, ...)` and a `disabled` tag until
  repaired) instead of the mixer.
- **Black-market pathways:** chips as loot and heist objectives — the
  knowledge attribute is portable, findable, and steal-proof (it's on
  your sheet, not in your pack).
