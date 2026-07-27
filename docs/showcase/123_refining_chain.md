# 123. Refining Chain

> Checklist item 123 ([now]): *multi-stage pipelines, tag-gated stations*

**What you'll build:** An industrial corridor. An arc smelter takes raw
`ore` and pours `ingot`s, and a parts mill one room over takes `ingot`s
and cuts `component`s. The same script runs on both stations; only their
data differs. Ore enters at one end of the corridor and finished parts
leave from the other.

**Concepts:** a pipeline typed by tags (`ore` to `ingot` to
`component`, where each stage consumes one tag and emits the next), the
station as pure data (`eats`, `makes`, the counts, and the flavor text
are attributes, so the `$refine` script is identical on every station),
and composition, because this is [122's](122_recipe_crafting.md)
consume-and-create core with the recipe folded into the station itself.

## How it works

A refining chain is a row of near-identical stations, one per room, each
reading a small block of data to decide what it consumes and what it
produces. This section explains why one script serves every station, how
tags keep the stages apart, and why the stations roll no dice.

### Why one script serves every station

Both machines answer `refine`. If they shared a room they would collide,
because command-trigger lookup returns the first match it finds and the
second station's `refine` would never fire. The chain avoids that by
putting one station per room, so walking the corridor moves you from one
stage to the next. The script never names ore or ingots; it reads `eats`
and `makes` off `me`, the station itself. Commissioning a third stage
(component to assembly) is a `@clone`, four `@set`s of data, and a room,
with no script edit.

### How tags keep the stages apart

The smelter counts [`has_tag`](../reference/softcode.md#fn-has_tag)`(o,
'ore')` among what you carry, while the mill counts `ingot`. Feed the
mill raw ore and it refuses with a count, `The hopper wants 2x ingot; you
carry 0.`, because to the mill an ore chunk is not short stock, it is
simply not an ingot. The tag namespace is the contract between stages, so
anything else that mints those tags (a
[gathering node](121_gathering_nodes.md), a salvage bench, an import
crate) feeds the chain with no further wiring.

### Why the stations roll no dice

Refining here is deterministic conversion. The dice live at the crafting
bench (122) and the finishing lathe ([125](125_quality_tiers.md))
instead. Keeping the conversion stages predictable is what makes a long
chain pleasant to run, so add risk only at the stages where the player
makes a choice.

## Build it

First dig the smeltery, step into it, and stand up the furnace as a bare
object:

```text
@dig The Smeltery = smeltway, yard
smeltway
@create arc smelter
drop arc smelter
@desc arc smelter = A squat induction furnace, crucible glowing the color of a dying sun. Its hopper gapes for raw ore.
```

The furnace is pure data: what it eats and how many, what it makes and
with which tags and how many, plus a line of flavor text for the pour.
`@set` parses the JSON, so `makes_tags` stores as a real list:

```text
@set arc smelter/eats = ore
@set arc smelter/eats_count = 2
@set arc smelter/makes = a duralloy ingot
@set arc smelter/makes_tags = ["thing", "ingot"]
@set arc smelter/makes_count = 1
@set arc smelter/work_msg = The smelter roars; slag hisses off the pour, and
```

The `refine` command reads that data with
[`V`](../reference/softcode.md#fn-v) and runs the conversion. It counts
the enactor's carried stock of the eaten tag with
[`contents`](../reference/softcode.md#fn-contents); if that count falls
short it reports the shortfall with
[`pemit`](../reference/softcode.md#fn-pemit); otherwise it removes the
inputs with [`destroy_obj`](../reference/softcode.md#fn-destroy_obj),
mints the outputs into the room with
[`create_obj`](../reference/softcode.md#fn-create_obj), and announces the
pour to everyone present with
[`remit`](../reference/softcode.md#fn-remit). A `$`-command fires only
when a player types its name, so it needs no `target` guard:

```text
@set arc smelter/cmd_refine = '''
$refine:
t = V('eats')            # what this station consumes, read off the station itself
n = V('eats_count', 1)
k = V('makes_count', 1)
stock = [o for o in contents(enactor) if has_tag(o, t)]
if len(stock) < n:
    pemit(enactor, f'The hopper wants {n}x {t}; you carry {len(stock)}.')
else:
    for o in stock[:n]:
        destroy_obj(o)
    for i in range(k):
        create_obj(V('makes'), V('makes_tags', ['thing']), here)
    remit(here, f'{V("work_msg", "The station cycles, and")} {k}x {V("makes")} land(s) in the tray.')
'''
```

Now dig the machine shop one door down, step through, and stand up the
mill the same way:

```text
@dig The Machine Shop = shopway, smeltway
shopway
@create parts mill
drop parts mill
@desc parts mill = A gantry mill sleeved in coolant mist. A feed clamp waits for ingot stock.
```

Its data is the only thing that changes: it eats one `ingot` and makes
two `component`-tagged parts:

```text
@set parts mill/eats = ingot
@set parts mill/eats_count = 1
@set parts mill/makes = a precision servo part
@set parts mill/makes_tags = ["thing", "component"]
@set parts mill/makes_count = 2
@set parts mill/work_msg = The mill shrieks through the billet, and
```

Its `refine` command is the exact same script, since every difference
lives in the data above:

```text
@set parts mill/cmd_refine = '''
$refine:
t = V('eats')
n = V('eats_count', 1)
k = V('makes_count', 1)
stock = [o for o in contents(enactor) if has_tag(o, t)]
if len(stock) < n:
    pemit(enactor, f'The hopper wants {n}x {t}; you carry {len(stock)}.')
else:
    for o in stock[:n]:
        destroy_obj(o)
    for i in range(k):
        create_obj(V('makes'), V('makes_tags', ['thing']), here)
    remit(here, f'{V("work_msg", "The station cycles, and")} {k}x {V("makes")} land(s) in the tray.')
'''
```

Walk back to the smeltery, which is where the chain begins:

```text
smeltway
```

## Try it

Mint two loads of ore here (in a full game the ore comes from the
[vein](121_gathering_nodes.md)), then run each stage:

```text
> @eval [create_obj('a chunk of balthite ore', ['thing', 'ore'], me) for i in range(2)]
> refine
  The smelter roars; slag hisses off the pour, and 1x a duralloy ingot land(s) in the tray.
> get duralloy ingot
  You pick up a duralloy ingot.
> shopway
  The Machine Shop
> refine
  The mill shrieks through the billet, and 2x a precision servo part land(s) in the tray.
```

At the smelter your two ore chunks are consumed and one ingot lands in
the room. Pick it up, walk `shopway`, and `refine` again to cut two servo
parts. Feed a machine the wrong stock and it counts your goods without
touching them: `refine` at the mill with only ore in your pack answers
`The hopper wants 1x ingot; you carry 0.`

Those `component`-tagged parts are what the
[assembly bench](122_recipe_crafting.md), the
[tuning bench](127_crafting_stations.md), and the
[fabricator](126_blueprints.md) consume, so the chain ends where the
recipes begin.

## Going further

- **Byproducts:** a `waste` attr on the smelter (`"a cake of grey slag"`,
  tagged `scrap`) minted alongside each pour is free feedstock for the
  [breaker bench](124_salvage.md).
- **Hands-free conveyor:** put the consume-and-emit body into an
  `on_tick` that eats from `contents(here)` instead of the enactor, so
  you drop ore and come back later. The
  [conveyor belt](023_conveyor_belt.md) moves the goods between stations.
- **Batch throughput:** `eats_count` and `makes_count` are the balance
  levers, so a 3:1 smelter paired with a 1:4 mill prices ore against
  parts with no script edit.
- **A quality chain:** carry a `purity` attr on the intermediates
  (stamped by margin at the vein) and have each station average it into
  its output, so provenance travels the whole pipeline.
