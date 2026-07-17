# 127. Crafting Stations

> Checklist item 127 — [now] — *environment tag checks in recipes*

**What you'll build:** A tuning bench whose recipe needs more than
ingredients — it needs an **arc welder** and a **micro vice** at the
work site. The bench checks the room and your hands for tool tags and
reports a per-tool readiness list (`arc_welder (MISSING)`) before it
will touch your materials.

**Concepts:** **tools as environment**, found by tag in
`contents(here) + contents(enactor)` (on the floor, on the bench, or
in someone's hand — all equally "present"), a recipe dict grown a
`tools` field ([122's](122_recipe_crafting.md) data shape, extended
not replaced), and failure text that enumerates each requirement with
its status plus a count — never a bare "you can't".

## How it works

**The bench itself is the first requirement.** The `$tune` verb
*lives on* the tuning bench, and `$`-commands only fire from objects
in your room, your inventory, or your zone — so "you must be at a
tuning bench" costs nothing to enforce. Everything beyond that is the
`tools` list.

**Presence is a tag scan, not an inventory slot.** For each tag in
`recipe['tools']` the script asks whether *anything* in
`contents(here) + contents(enactor)` carries it. The welder can sit
on the floor, hang on the wall, or ride in your own toolbelt — but if
it's not in the room with you (or on you), it isn't present; a tool
zipped inside a colleague's pack is *their* tool, not the room's. This
is the same location-is-truth reasoning as the
[refrigerator](018_refrigerator.md)'s decay rate: no bookkeeping, the
world *is* the state. Tools are consulted, never consumed — only the
`needs` ingredients burn.

**Diagnostics are a list, with arithmetic.** When tools are missing
the bench prints every requirement with its status — `Tool check --
arc_welder (ready), micro_vice (MISSING): 1 of 2 present.` — so the
fix is legible from the error. Ingredient shortfalls get their own
count the same way. Only when both gates pass does anything get
destroyed or created.

## Build it

The bench, with a recipe that names its tooling:

```text
@create tuning bench
drop tuning bench
@desc tuning bench = A vibration-damped bench ruled into a calibration grid. Etched under the lamp: TOOLS MAKE THE MACHINIST.
@set tuning bench/recipe_gyro = {"output": "a balanced gyro assembly", "tags": ["thing", "gyro"], "needs": {"component": 1}, "tools": ["arc_welder", "micro_vice"]}
@set tuning bench/cmd_tune = $tune *: sel = trim(arg0).lower(); r = V('recipe_' + sel); near = contents(here) + contents(enactor) if r else []; stat = [t + (' (ready)' if [o for o in near if has_tag(o, t)] else ' (MISSING)') for t in r['tools']] if r else []; miss = [t for t in r['tools'] if not [o for o in near if has_tag(o, t)]] if r else []; stock = [o for o in contents(enactor) if has_tag(o, 'component')] if r else []; pemit(enactor, 'No such job is chalked on this bench.') if not r else None; pemit(enactor, 'Tool check -- ' + ', '.join(stat) + ': ' + str(len(r['tools']) - len(miss)) + ' of ' + str(len(r['tools'])) + ' present.') if r and miss else None; pemit(enactor, 'The jig wants 1x component; you carry ' + str(len(stock)) + '.') if r and not miss and not stock else None; (destroy_obj(stock[0]), create_obj(r['output'], r['tags'], here), remit(here, name(enactor) + ' clamps, welds, and spins a gyro assembly true on the bench.')) if r and not miss and stock else None
```

The tools — ordinary objects wearing the tags the recipe names. Note
the vice starts in your hand and the welder on the floor: both count:

```text
@create arc welder
@tag arc welder = arc_welder
drop arc welder
@create micro vice
@tag micro vice = micro_vice
```

## Try it

With a `component`-tagged part in your pack (mint one or mill one at
[123](123_refining_chain.md)):

```text
tune gyro
```

Everything present: `... clamps, welds, and spins a gyro assembly
true on the bench.` — the component burns, the tools don't, and the
gyro waits in the tray. Now send the arc welder somewhere else
(`@teleport arc welder = The Corridor`, or let a colleague walk off
with it) and try again:

```text
tune gyro
```

`Tool check -- arc_welder (MISSING), micro_vice (ready): 1 of 2
present.` — no roll, no loss, and the message *is* the shopping list.
Bring the welder back (floor or your own hand, either satisfies the
scan) and the job runs. `tune flux` gets `No such job is chalked on
this bench.`, and with tools ready but empty pockets: `The jig wants
1x component; you carry 0.`

## Going further

- **Tool wear:** burn 1 `durability` off a consulted tool per job
  ([125](125_quality_tiers.md) stamps it) — tools become an economy,
  not scenery.
- **The station as a tool:** give the *bench* a tag other recipes
  name in `tools` — a portable field kit that finds "any bench" wherever
  it goes.
- **Quality from tooling:** count surplus tools (a `laser_gauge`
  present but not required) as a `+1` on
  [125's](125_quality_tiers.md) margin — good shops make good work.
- **Powered stations:** add a `powered` tag the room only carries
  while the [generator](056_self_destruct.md)-style machinery runs —
  environment checks compose with any world state you can tag.
