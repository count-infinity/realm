# 123. Refining Chain

> Checklist item 123 — [now] — *multi-stage pipelines, tag-gated stations*

**What you'll build:** An industrial corridor: an **arc smelter** that
eats raw `ore` and pours `ingot`s, and a **parts mill** one room over
that eats `ingot`s and cuts `component`s. Same script on both — only
their data differs. Ore walks in one end; parts walk out the other.

**Concepts:** a **pipeline typed by tags** (`ore -> ingot ->
component`; each stage consumes one tag and emits the next), **the
station as pure data** (`eats`, `makes`, counts and flavor text are
attributes; the `$refine` script is identical on every station), and
composition — this is [122's](122_recipe_crafting.md) consume/create
core with the recipe flattened into the station itself.

## How it works

**One verb, many stations.** Both machines answer `refine`. That
would collide if they shared a room — `$`-command lookup takes the
first match — so the chain *is* the floor plan: one station per room,
and walking the corridor is walking the process. The script never
names ore or ingots; it reads `eats`/`makes` off `me`. Commissioning a
third stage (component → assembly) is `@clone`, four `@set`s of data,
and a room.

**Tags gate the stages.** The smelter counts `has_tag(o, 'ore')`
among what you carry; the mill counts `ingot`. Feed the mill raw ore
and it refuses with arithmetic — `The hopper wants 2x ingot; you carry
0.` — because to the mill, ore isn't *short*, it's *invisible*. The
tag namespace is the contract between stages, and anything else that
mints those tags (a [gathering node](121_gathering_nodes.md), a
salvage bench, an import crate) plugs into the chain for free.

**No dice at the smelter.** Refining here is deterministic
conversion — the interesting rolls live at the crafting bench (122)
and the finishing lathe ([125](125_quality_tiers.md)). Keeping stages
boring is what makes long chains playable; add risk only where a
choice lives.

## Build it

The smeltery and its furnace — configuration is all data:

```text
@dig The Smeltery = smeltway, yard
smeltway
@create arc smelter
drop arc smelter
@desc arc smelter = A squat induction furnace, crucible glowing the color of a dying sun. Its hopper gapes for raw ore.
@set arc smelter/eats = ore
@set arc smelter/eats_count = 2
@set arc smelter/makes = a duralloy ingot
@set arc smelter/makes_tags = ["thing", "ingot"]
@set arc smelter/makes_count = 1
@set arc smelter/work_msg = The smelter roars; slag hisses off the pour, and
@set arc smelter/cmd_refine = $refine: t = V('eats'); n = V('eats_count', 1); stock = [o for o in contents(enactor) if has_tag(o, t)]; k = V('makes_count', 1); pemit(enactor, f'The hopper wants {n}x {t}; you carry {len(stock)}.') if len(stock) < n else ([destroy_obj(o) for o in stock[:n]], [create_obj(V('makes'), V('makes_tags', ['thing']), here) for i in range(k)], remit(here, f'{V("work_msg", "The station cycles, and")} {k}x {V("makes")} land(s) in the tray.'))
```

The machine shop, one door down — the *same* `cmd_refine` line, new
data around it:

```text
@dig The Machine Shop = shopway, smeltway
shopway
@create parts mill
drop parts mill
@desc parts mill = A gantry mill sleeved in coolant mist. A feed clamp waits for ingot stock.
@set parts mill/eats = ingot
@set parts mill/eats_count = 1
@set parts mill/makes = a precision servo part
@set parts mill/makes_tags = ["thing", "component"]
@set parts mill/makes_count = 2
@set parts mill/work_msg = The mill shrieks through the billet, and
@set parts mill/cmd_refine = $refine: t = V('eats'); n = V('eats_count', 1); stock = [o for o in contents(enactor) if has_tag(o, t)]; k = V('makes_count', 1); pemit(enactor, f'The hopper wants {n}x {t}; you carry {len(stock)}.') if len(stock) < n else ([destroy_obj(o) for o in stock[:n]], [create_obj(V('makes'), V('makes_tags', ['thing']), here) for i in range(k)], remit(here, f'{V("work_msg", "The station cycles, and")} {k}x {V("makes")} land(s) in the tray.'))
smeltway
```

## Try it

Walk two loads of ore down the chain (mint them here; a real game's
come from the [vein](121_gathering_nodes.md)):

```text
@eval [create_obj('a chunk of balthite ore', ['thing', 'ore'], me) for i in range(2)]
refine
get duralloy ingot
shopway
refine
```

At the smelter: `The smelter roars; slag hisses off the pour, and 1x a
duralloy ingot land(s) in the tray.` — your two ore chunks are gone.
Pick up the ingot, walk `shopway`, `refine` again: `The mill shrieks
through the billet, and 2x a precision servo part land(s) in the
tray.` Feed either machine the wrong stock and it counts your goods
without touching them: `refine` at the mill with only ore in your pack
answers `The hopper wants 1x ingot; you carry 0.`

Those `component`-tagged parts are what the
[assembly bench](122_recipe_crafting.md), the
[tuning bench](127_crafting_stations.md), and the
[fabricator](126_blueprints.md) all consume — chains end where
recipes begin.

## Going further

- **Byproducts:** a `waste` attr on the smelter (`"a cake of grey
  slag"`, tagged `scrap`) spawned alongside each pour — free feedstock
  for the [breaker bench](124_salvage.md).
- **Hands-free conveyor:** put the station's consume/emit into an
  `on_tick` that eats from `contents(here)` instead of the enactor —
  drop ore, come back later. The [conveyor belt](023_conveyor_belt.md)
  moves the goods between stations.
- **Batch throughput:** `eats_count`/`makes_count` are the balance
  levers — a 3:1 smelter with a 1:4 mill prices ore against parts
  without touching a script.
- **A quality chain:** carry a `purity` attr on the intermediates
  (stamped by margin at the vein) and have each station average it
  into its output — provenance travels the pipeline.
