# 122. Recipe Crafting

> Checklist item 122 ([now]): *recipe validation, destroy/create, margin quality*

**What you'll build:** An assembly bench that turns tagged ingredients
into finished goods. `craft valve` checks what you carry against a
recipe, rolls your machining skill, consumes the inputs with
[`destroy_obj`](../reference/softcode.md#fn-destroy_obj), and mints the
product (or a lump of ruined scrap) with
[`create_obj`](../reference/softcode.md#fn-create_obj).

**Concepts:** recipes as data (one dict attribute per recipe: output,
skill, ingredient tags and counts), tags as ingredient types
(`has_tag(o, 'ingot')` means any ingot satisfies the recipe, no matter
which mine it came from), guard-chain validation with a specific
message per failure, consume-then-create committed together, and
failure that still costs you materials.

## How it works

An assembly bench is one object that reads a recipe and runs it. A
recipe is a dict attribute holding the output, the governing skill, and
the ingredients it needs; the craft command looks that dict up, checks
what you carry, rolls your skill, consumes the inputs, and mints the
result. This section covers each piece in turn: the recipe as data,
tags as the ingredient type, and why a failed craft still burns your
materials.

### A recipe is data; the bench reads it

`recipe_valve` holds everything the craft needs to know: the output's
name and tags, the governing skill, a difficulty `mod`, and a `needs`
map of tag to count. `$craft *` looks up `recipe_<arg>` and runs the
same script whatever the recipe says, so adding a product to the bench
is one `@set` and one entry in `menu`, never a script edit. This is the
[vending machine](002_vending_machine.md)'s prototype idiom with a skill
roll on top.

### Tags are the ingredient type

The recipe does not name objects, it names kinds: one `ingot`, one
`gasket`. Validation counts your carried items per tag with
[`contents`](../reference/softcode.md#fn-contents) and
[`has_tag`](../reference/softcode.md#fn-has_tag), so the shortfall
message lists exactly what is missing and how many
(`Short of materials: 1x gasket.`). Consumption then picks the first N
carried matches per tag and destroys them with `destroy_obj`. The bench
may destroy them because it controls them: `destroy_obj` only touches
objects the executor controls, which under REALM's authority rules
means objects it or its owner owns. The bench shares an owner with the
ore and gasket that owner minted, so it may burn them, whereas a
stranger's ingot (owned by someone else) would refuse.

### Attempting costs the materials

The roll happens after validation, using
[`margin_under`](../reference/softcode.md#fn-margin_under) on
[`roll`](../reference/softcode.md#fn-roll)`('3d6')` against your
[`get_attr`](../reference/softcode.md#fn-get_attr) of
`skill_<skill>` plus the recipe's mod. The inputs burn either way: a
success rings the output into the tray, a failure leaves
`a lump of ruined scrap` (tagged `scrap`, which the
[breaker bench](124_salvage.md) turns partly back into parts, so a botch
feeds the loop instead of deleting value). The output lands in the room,
not in your hands, because `create_obj` can only place a fresh object in
a room the bench controls, not inside another player. The tray is the
floor, and `get` is the last step.

## Build it

The bench and its catalogue. The `menu` list indexes the recipes for
the job-card browser, and `recipe_valve` is the recipe dict (`@set`
parses JSON, so the list and dict store as real values):

```text
@create assembly bench
drop assembly bench
@desc assembly bench = A scarred steel bench under a rack of torque drivers. A job card is chained to one leg.
@set assembly bench/menu = ["valve"]
@set assembly bench/recipe_valve = {"output": "a machined pressure valve", "tags": ["thing", "component"], "skill": "machining", "mod": 0, "needs": {"ingot": 1, "gasket": 1}}
```

The job-card browser walks `menu` and prints one line per recipe with
its ingredients spelled out, reaching the reader with
[`pemit`](../reference/softcode.md#fn-pemit):

```text
@set assembly bench/cmd_jobs = '''
$jobs:
for sel in V('menu', []):
    r = V('recipe_' + sel)
    needs = ', '.join(f'{n}x {t}' for t, n in r['needs'].items())
    pemit(enactor, f'  {sel} -> {r["output"]} (needs: {needs})')
'''
```

The craft itself, where `$craft *` captures the selection as `arg0`. It
guards the recipe name, counts your ingredients and reports any
shortfall, and only when everything is in hand does it roll, consume the
inputs, and mint the output. Success announces to the room with
[`remit`](../reference/softcode.md#fn-remit) and stamps the crafter's
[`name`](../reference/softcode.md#fn-name) on the line:

```text
@set assembly bench/cmd_craft = '''
$craft *:
sel = trim(arg0).lower()
r = V('recipe_' + sel)
if not r:
    pemit(enactor, 'The job card lists no such assembly. Try jobs.')
else:
    carried = contents(enactor)
    short = []
    for t, n in r['needs'].items():
        have = len([o for o in carried if has_tag(o, t)])
        if have < n:
            short.append(f'{n - have}x {t}')
    if short:
        pemit(enactor, 'Short of materials: ' + ', '.join(short) + '.')
    else:
        res = margin_under(roll('3d6'), get_attr(enactor, 'skill_' + r['skill'], 8) + r['mod'])
        # The attempt burns the inputs whether the roll makes or misses.
        for t, n in r['needs'].items():
            for o in [x for x in carried if has_tag(x, t)][:n]:
                destroy_obj(o)
        if res.success:
            create_obj(r['output'], r['tags'], here)
            remit(here, f'{name(enactor)} works the bench -- {r["output"]} drops into the tray. (margin +{res.margin})')
        else:
            create_obj('a lump of ruined scrap', ['thing', 'scrap'], here)
            remit(here, f'{name(enactor)} botches the assembly -- ruined scrap hits the tray. (rolled {res.roll} vs {r["skill"]} {res.effective})')
'''
```

## Try it

Stock up (ore from a [gathering node](121_gathering_nodes.md) via the
[smelter](123_refining_chain.md) in a full game, minted here for the
demo), read the card, and craft:

```text
> @set me/skill_machining = 11
> @eval (create_obj('a duralloy ingot', ['thing', 'ingot'], me), create_obj('a silicone gasket', ['thing', 'gasket'], me))
> jobs
    valve -> a machined pressure valve (needs: 1x ingot, 1x gasket)
> craft valve
  ... works the bench -- a machined pressure valve drops into the tray. (margin +2)
> get machined pressure valve
  You pick up a machined pressure valve.
> craft valve
  Short of materials: 1x ingot, 1x gasket.
> craft widget
  The job card lists no such assembly. Try jobs.
```

The margin line varies with the roll. A made roll drops the valve and
the ingot and gasket vanish from your pack; a botch instead leaves
`a lump of ruined scrap` and quotes the dice,
`... botches the assembly -- ruined scrap hits the tray. (rolled 18 vs machining 11)`,
with the materials burned all the same. Missing inputs never roll at
all: an empty-handed `craft valve` answers
`Short of materials: 1x ingot, 1x gasket.`, and `craft widget` gets
`The job card lists no such assembly. Try jobs.`

## Going further

- **Margin as quality:** stamp the output with the roll's margin and let
  it grade fine, good, or shoddy. Item [125](125_quality_tiers.md)
  builds exactly that on this bench's skeleton.
- **Recipe licenses:** gate `craft` on a `known_recipes` list studied
  from schematics. Item [126](126_blueprints.md).
- **Tool requirements:** add a recipe field listing tags that must be
  present in the room. Item [127](127_crafting_stations.md).
- **Kinder failure:** on a miss, refund the inputs on a second
  `margin_under` ("salvage the setup") instead of always burning them,
  or scale the scrap count to how badly the roll missed.
