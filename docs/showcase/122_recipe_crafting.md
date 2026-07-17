# 122. Recipe Crafting

> Checklist item 122 — [now] — *recipe validation, destroy/create, margin quality*

**What you'll build:** An assembly bench that turns tagged ingredients
into finished goods: `craft valve` checks what you're carrying against
a recipe, rolls your machining, consumes the inputs with
`destroy_obj()`, and mints the product — or a lump of ruined scrap —
with `create_obj()`.

**Concepts:** **recipes as data** (one dict attribute per recipe:
output, skill, ingredient tags and counts), **tags as ingredient
types** (`has_tag(o, 'ingot')` — any ingot satisfies the recipe, no
matter which mine it came from), guard-chain validation with a numeric
message per failure, consume-then-create as one committed tuple, and
failure that costs you materials.

## How it works

**A recipe is a dict; the bench is an interpreter.** `recipe_valve`
holds everything the craft needs to know: the output's name and tags,
the governing skill, and a `needs` map of `tag -> count`. `$craft *`
looks up `recipe_<arg>` and runs the same script whatever the recipe
says — adding a product to the bench is one `@set` and one entry in
`menu`, never a script edit. That's the
[vending machine](002_vending_machine.md)'s prototype idiom grown a
skill roll.

**Tags are the type system.** The recipe doesn't name objects, it
names *kinds*: one `ingot`, one `gasket`. Validation counts your
carried items per tag; the shortfall message lists exactly what's
missing and how many (`Short of materials: 1x gasket.`). Consumption
picks the first N carried matches per tag and `destroy_obj()`s them —
the bench may destroy them because it *controls* them (same owner as
the mine and smelter that minted them; a stranger's heirloom ingot
would refuse).

**Attempting costs the materials.** The roll happens after
validation, and the inputs burn either way — success rings the output
into the tray, failure leaves `a lump of ruined scrap` (tagged
`scrap`, which the [breaker bench](124_salvage.md) can partially
recover — failure feeds the loop instead of deleting value). The
output lands in the room, not your hands: softcode may not conjure
objects *into* another player, so the tray is the floor and `get` is
the last step.

## Build it

The bench and its catalogue (one recipe to start — `menu` indexes it
for the browser):

```text
@create assembly bench
drop assembly bench
@desc assembly bench = A scarred steel bench under a rack of torque drivers. A job card is chained to one leg.
@set assembly bench/menu = ["valve"]
@set assembly bench/recipe_valve = {"output": "a machined pressure valve", "tags": ["thing", "component"], "skill": "machining", "mod": 0, "needs": {"ingot": 1, "gasket": 1}}
```

The job-card browser — one line per recipe, ingredients spelled out:

```text
@set assembly bench/cmd_jobs = $jobs: [pemit(enactor, '  ' + s + ' -> ' + V('recipe_' + s)['output'] + ' (needs: ' + ', '.join(f'{n}x {t}' for t, n in V('recipe_' + s)['needs'].items()) + ')') for s in V('menu', [])]
```

And the craft itself — guards first (unknown recipe, shortfall), then
the roll, then one tuple that consumes and creates together:

```text
@set assembly bench/cmd_craft = $craft *: sel = trim(arg0).lower(); r = V('recipe_' + sel); carried = contents(enactor) if r else []; short = [str(n - len([o for o in carried if has_tag(o, t)])) + 'x ' + t for t, n in (r['needs'].items() if r else []) if len([o for o in carried if has_tag(o, t)]) < n]; pemit(enactor, 'The job card lists no such assembly. Try jobs.') if not r else None; pemit(enactor, 'Short of materials: ' + ', '.join(short) + '.') if r and short else None; res = margin_under(roll('3d6'), get_attr(enactor, 'skill_' + r['skill'], 8) + r['mod']) if r and not short else None; ([destroy_obj(o) for t, n in r['needs'].items() for o in [x for x in carried if has_tag(x, t)][:n]], (create_obj(r['output'], r['tags'], here), remit(here, f'{name(enactor)} works the bench -- {r["output"]} drops into the tray. (margin +{res.margin})')) if res.success else (create_obj('a lump of ruined scrap', ['thing', 'scrap'], here), remit(here, f'{name(enactor)} botches the assembly -- ruined scrap hits the tray. (rolled {res.roll} vs {r["skill"]} {res.effective})'))) if r and not short else None
```

## Try it

Stock up (ore from a [gathering node](121_gathering_nodes.md) via the
[smelter](123_refining_chain.md) in a full game; minted here for the
demo) and read the card:

```text
@set me/skill_machining = 11
@eval (create_obj('a duralloy ingot', ['thing', 'ingot'], me), create_obj('a silicone gasket', ['thing', 'gasket'], me))
jobs
craft valve
```

`jobs` prints `valve -> a machined pressure valve (needs: 1x ingot, 1x
gasket)`. A successful craft rings out `... works the bench -- a
machined pressure valve drops into the tray. (margin +2)`, the ingot
and gasket vanish from your pack, and `get machined pressure valve`
claims the goods. On a failed roll you get the dice —
`botches the assembly -- ruined scrap hits the tray. (rolled 18 vs
machining 11)` — and the scrap where your materials were. Missing
inputs never roll at all: `craft valve` empty-handed answers `Short of
materials: 1x ingot, 1x gasket.`, and `craft widget` gets `The job
card lists no such assembly. Try jobs.`

## Going further

- **Margin as quality:** stamp the output with the roll's margin and
  let it set fine/good/shoddy — item
  [125](125_quality_tiers.md) builds exactly that on this bench's
  skeleton.
- **Recipe licenses:** gate `craft` on a `known_recipes` list studied
  from schematics — item [126](126_blueprints.md).
- **Tool requirements:** a recipe field listing tags that must be
  present in the room — item [127](127_crafting_stations.md).
- **Kinder failure:** on a miss, refund the inputs on a second
  `margin_under` ("salvage the setup") instead of always burning them
  — or scale scrap count to how badly the roll missed.
