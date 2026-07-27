# 127. Crafting Stations

> Checklist item 127 ([now]): *environment tag checks in recipes*

**What you'll build:** A tuning bench whose recipe needs more than
ingredients. It also needs an arc welder and a micro vice at the work
site. Before it touches your materials the bench scans the room and
your hands for those tools and reports a per-tool readiness list, so a
missing tool reads as `arc_welder (MISSING)` rather than a bare refusal.

**Concepts:** tools treated as environment, found by tag across
[`contents(here)`](../reference/softcode.md#fn-contents) and
`contents(enactor)` (on the floor, on the bench, or in a hand all count
as present), a recipe dict grown a `tools` field on top of
[122's](122_recipe_crafting.md) data shape, and a failure message that
enumerates each requirement with its status and a running count.

## How it works

The finished bench is a recipe dict that carries one extra field and a
`$`-command that reads it. When you type `tune gyro` the bench looks up
the recipe, scans for the tools it names, and either enumerates what is
missing or consumes the ingredient and mints the product. This section
answers three questions: why
standing at the bench is already the first requirement, how the bench
decides a tool is present, and what the failure text owes the player.

### Why is standing at the bench the first requirement?

The `$tune` command lives on the tuning bench itself, and a `$`-command
fires only from objects in your room, your inventory, or your zone.
Because of that, "you must be at a tuning bench" costs no code: away
from the bench there is no `tune` command to run. Everything past that
gate is the recipe's `tools` list.

### How does the bench decide a tool is present?

Presence is a tag scan, not an inventory slot. For each tag name in
`recipe['tools']` the script asks whether anything in
`contents(here) + contents(enactor)` carries that tag with
[`has_tag`](../reference/softcode.md#fn-has_tag). The welder can rest on
the floor, hang on a rack, or ride in your own toolbelt, and any of
those satisfies the scan, because all of them share your location. A
welder zipped inside a colleague's pack is that colleague's tool, not
the room's, so it does not count. This is the same location-decides-it
reasoning the [refrigerator](018_refrigerator.md) uses for its decay
rate, where the holder publishes the value and nothing is bookkept.
Tools are consulted, never consumed: only the `component` ingredient
burns.

### What does the failure text owe the player?

A vague refusal makes the fix a guessing game, so when tools are missing
the bench [`pemit`](../reference/softcode.md#fn-pemit)s every requirement
with its status, for example
`Tool check -- arc_welder (ready), micro_vice (MISSING): 1 of 2
present.`, and the message is the shopping list. An ingredient shortfall
gets its own count the same way. Only when the tool gate and the
ingredient gate both pass does anything get destroyed with
[`destroy_obj`](../reference/softcode.md#fn-destroy_obj) or created with
[`create_obj`](../reference/softcode.md#fn-create_obj).

## Build it

Create the bench, set it down, and describe it:

```text
@create tuning bench
drop tuning bench
@desc tuning bench = A vibration-damped bench ruled into a calibration grid. Etched under the lamp: TOOLS MAKE THE MACHINIST.
```

The recipe is one dict attribute. Alongside 122's `output`, `tags`, and
`needs`, it grows a `tools` list of the tag names that must be present:

```text
@set tuning bench/recipe_gyro = {"output": "a balanced gyro assembly", "tags": ["thing", "gyro"], "needs": {"component": 1}, "tools": ["arc_welder", "micro_vice"]}
```

The `$tune` command reads that recipe, builds the per-tool status list
and the missing-tool list from one scan, then runs the two gates in
order: tools first, ingredient second, craft last. The scan spans the
room and your inventory so a tool on the floor counts the same as one in
your hand:

```text
@set tuning bench/cmd_tune = '''
$tune *:
sel = trim(arg0).lower()
r = V('recipe_' + sel)
if not r:
    pemit(enactor, 'No such job is chalked on this bench.')
else:
    near = contents(here) + contents(enactor)  # room plus your hands: either location counts as present
    stat = [t + (' (ready)' if [o for o in near if has_tag(o, t)] else ' (MISSING)') for t in r['tools']]
    miss = [t for t in r['tools'] if not [o for o in near if has_tag(o, t)]]
    stock = [o for o in contents(enactor) if has_tag(o, 'component')]
    if miss:
        pemit(enactor, 'Tool check -- ' + ', '.join(stat) + ': ' + str(len(r['tools']) - len(miss)) + ' of ' + str(len(r['tools'])) + ' present.')
    elif not stock:
        pemit(enactor, 'The jig wants 1x component; you carry ' + str(len(stock)) + '.')
    else:
        destroy_obj(stock[0])
        create_obj(r['output'], r['tags'], here)
        remit(here, name(enactor) + ' clamps, welds, and spins a gyro assembly true on the bench.')
'''
```

The tools are ordinary objects wearing the tags the recipe names. Drop
the welder on the floor and keep the vice in hand, so the build proves
both locations satisfy the scan:

```text
@create arc welder
@tag arc welder = arc_welder
drop arc welder
@create micro vice
@tag micro vice = micro_vice
```

## Try it

With a `component`-tagged part in your pack (mint one, or mill one at
[123](123_refining_chain.md)), run the job with both tools present, the
welder on the floor and the vice in your hand:

```text
> tune gyro
Bilda clamps, welds, and spins a gyro assembly true on the bench.
```

The component burns, the tools stay, and the gyro waits in the tray.
Now send the arc welder somewhere else and try again:

```text
> @teleport arc welder = The Corridor
> tune gyro
Tool check -- arc_welder (MISSING), micro_vice (ready): 1 of 2 present.
```

No roll and no loss: the message names exactly which tool to fetch.
Bring the welder back (floor or your own hand, either satisfies the
scan) and the job runs. An unknown job and empty pockets each answer
plainly:

```text
> tune flux
No such job is chalked on this bench.

> tune gyro
The jig wants 1x component; you carry 0.
```

## Going further

- **Tool wear:** burn 1 `durability` off a consulted tool per job
  ([125](125_quality_tiers.md) stamps that attribute), so tools become
  an economy rather than scenery.
- **The station as a tool:** give the bench a tag that other recipes
  name in `tools`, making a portable field kit that satisfies "any
  bench" wherever it travels.
- **Quality from tooling:** count a surplus tool that is present but not
  required (a `laser_gauge`) as a `+1` on [125](125_quality_tiers.md)'s
  margin, so a well-equipped shop does better work.
- **Powered stations:** add a `powered` tag the room carries only while
  [generator](056_self_destruct.md)-style machinery runs, since an
  environment check composes with any world state you can tag.
