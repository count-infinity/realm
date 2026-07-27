# 121. Gathering Nodes

> Checklist item 121 ([now]): *depletion attrs, on_tick respawn, yield margins*

**What you'll build:** A seam of balthite crystal you can `mine`. Each swing
rolls prospecting, a better margin pries loose more ore, the vein runs dry
after a few loads, and a slow ticker grows it back while the miners are off
spending.

**Concepts:** a resource node as plain attributes (`ore_left` counting down,
`regrow_left` counting up), graded yield via
[`margin_under`](../reference/softcode.md#fn-margin_under) (the roll's *margin*
sizes the haul, not just pass or fail), spawning the take with
[`create_obj`](../reference/softcode.md#fn-create_obj), and a `script_ticker`
respawn, plus when the engine's native repop (`zone_reset`) is and is not the
right tool.

## How it works

A gathering node is one object that answers `mine` by rolling a skill, minting
ore in proportion to how well the roll went, and depleting until it is bare,
while a separate clock refills it on its own cadence. This section answers
three questions: where the node keeps its state, how the roll's margin becomes
a yield, and why the respawn is a ticker rather than the engine's native zone
repop.

### The node is a counter with a verb

`ore_left` is everything the vein knows about itself. The `$mine vein` command
reads it, rolls, decrements it, and mints ore chunks into the room with
[`create_obj`](../reference/softcode.md#fn-create_obj), the spawner vocabulary
from the [vending machine](002_vending_machine.md). The description is the
gauge: an inline `[[...]]` block reads `ore_left` with
[`V`](../reference/softcode.md#fn-v) so `look` tells a prospector whether the
seam is worth a swing. That block is a shallow read of the vein's own
attribute, so it stays cheap on every look.

### Margins, not booleans

[`skill_check`](../reference/softcode.md#fn-skill_check) answers yes or no,
whereas
[`margin_under`](../reference/softcode.md#fn-margin_under)`(`[`roll`](../reference/softcode.md#fn-roll)`('3d6'), skill)`
answers how well: it returns a graded `CheckResult` whose `.margin` is the
spare skill, while `.roll` and `.effective` carry the rolled total and the
target it was measured against. The expression `1 + margin // 3` turns that
into a yield, so a scrape-by success pries one chunk and a margin of 6 pries
three. Every failure text quotes the numbers (`rolled 15 vs prospecting 12`),
the house style for legible dice.

### Why the respawn is a ticker, not native repop

The engine does have native repop: the `zone_reset` behavior returns a whole
zone to its authored state on a timer. But zone reset is presence-gated, since
it never fires while a player stands anywhere in the zone, which is exactly
wrong for a working mine, because the one place guaranteed to have someone
loitering is the room with the ore. A vein regrows under the miners' boots, so
it keeps its own clock: a `script_ticker` whose
[`on_tick`](../reference/softcode.md#lifecycle-hooks) counts `regrow_left` down
only while the seam is spent, then refills `ore_left` from `ore_cap`. (For
nodes in a dungeon that should reset with the dungeon while nobody watches,
`zone_reset` is the better fit; see Going further.)

## Build it

The vein carries its gauge in the description. The `[[...]]` block reads
`ore_left` at look time and picks one of three readouts, so a prospector sees
at a glance whether the cut is worth working:

```text
@create balthite vein
drop balthite vein
@desc balthite vein = A seam of blue-green balthite crystal veining the rock face. [[left = V('ore_left', 0); result = 'It glitters, thick with ore.' if left > 2 else ('Only pale traces remain in the cut.' if left > 0 else 'It is hacked bare -- nothing but scarred rock.')]]
```

Its state is three plain numbers: how much ore a full vein holds, how much is
left now, and how many ticker steps a refill takes:

```text
@set balthite vein/ore_cap = 4
@set balthite vein/ore_left = 4
@set balthite vein/regrow_ticks = 3
```

The mining verb runs in one order: refuse a bare vein, roll the miner's
prospecting read by
[`get_attr`](../reference/softcode.md#fn-get_attr), quote the dice on a miss,
and on a hit mint ore sized to the margin, decrement the count with
[`decr`](../reference/softcode.md#fn-decr), announce the haul to the room with
[`remit`](../reference/softcode.md#fn-remit) and
[`name`](../reference/softcode.md#fn-name), and arm the regrowth clock if that
swing took the last of it. A `$`-command only ever runs on the vein whose name
matched, so it needs no `target` guard:

```text
@set balthite vein/cmd_mine = '''
$mine vein:
left = V('ore_left', 0)
if left < 1:
    pemit(enactor, 'The vein is hacked bare. Rock heals on its own clock; come back later.')
else:
    res = margin_under(roll('3d6'), get_attr(enactor, 'skill_prospecting', 8))
    if not res.success:
        pemit(enactor, 'Sparks, dust, no ore. (rolled ' + str(res.roll) + ' vs prospecting ' + str(res.effective) + ')')
    else:
        take = min(left, 1 + res.margin // 3)  # every 3 points of margin pries one more chunk
        decr('ore_left', take)
        for i in range(take):
            create_obj('a chunk of balthite ore', ['thing', 'ore'], here)
        remit(here, name(enactor) + ' swings at the vein -- ' + str(take) + ' chunk(s) of balthite clatter free.')
        if left - take < 1:  # that swing took the last ore, so start the regrowth clock
            set_attr(me, 'regrow_left', V('regrow_ticks', 3))
            remit(here, 'The seam splits and goes dark, spent.')
'''
```

[`pemit`](../reference/softcode.md#fn-pemit) sends the private lines back to
the miner, while `remit` announces the haul to everyone in the room.

The regrowth clock is a `script_ticker`, so its `on_tick` runs on the world
heartbeat. It does nothing while ore remains, counts `regrow_left` down while
the seam is spent, and on the last step refills `ore_left` from `ore_cap`,
clearing the counter with
[`set_attr`](../reference/softcode.md#fn-set_attr) and
[`del_attr`](../reference/softcode.md#fn-del_attr). At `interval:30` a step is
about two minutes at the default four-second beat, and a refill takes three
steps:

```text
@set balthite vein/on_tick = '''
left = V('ore_left', 0)
if left < 1:
    r = V('regrow_left', 0)
    if r > 1:
        decr('regrow_left')
    else:
        set_attr(me, 'ore_left', V('ore_cap', 4))
        del_attr(me, 'regrow_left')
        remit(here, 'Fresh balthite creeps glittering back across the rock face.')
'''
@behavior balthite vein = script_ticker, interval:30
```

## Try it

Give yourself a pick hand and swing. A strong roll pries several chunks loose
at once, though the exact count and the miss text both turn on the dice:

```text
> @set me/skill_prospecting = 12
> mine vein
<name> swings at the vein -- 3 chunk(s) of balthite clatter free.
```

A margin of 6 drops three `a chunk of balthite ore` objects onto the floor for
the taking, while a blown roll answers with the dice on the table: `Sparks,
dust, no ore. (rolled 15 vs prospecting 12)`. Keep swinging, because when the
last chunk comes loose you also get `The seam splits and goes dark, spent.`,
`look balthite vein` then reads `hacked bare`, and further mining refuses with
`The vein is hacked bare. Rock heals on its own clock; come back later.`

You can force the ticker by hand to watch it regrow. `on_tick` holds bare code,
so `@tr balthite vein/on_tick` fires it directly, whereas a `$`-command like
`mine` cannot be driven that way. Three beats in, the last step refills the
seam:

```text
> @tr balthite vein/on_tick
> @tr balthite vein/on_tick
> @tr balthite vein/on_tick
Fresh balthite creeps glittering back across the rock face.
```

The ore chunks are tagged `ore`, and that tag is the type system the whole
crafting chain keys on: the [assembly bench](122_recipe_crafting.md) counts
them and the [arc smelter](123_refining_chain.md) eats them.

## Going further

- **Native repop instead:** for a vein that should reset with its dungeon,
  only while nobody is inside, skip the ticker and let the zone master do it.
  Tag the rooms into a zone, crown a master, give it the `zone_reset` behavior,
  set the interval that gates the reset, and reseed the vein in the master's
  [`on_reset`](../reference/softcode.md#lifecycle-hooks) hook:

  ```text
  @zone here = mine
  @zone/master Mine Brain = mine
  @behavior Mine Brain = zone_reset
  @set Mine Brain/reset_interval = 600
  @set Mine Brain/on_reset = set_attr(get('balthite vein'), 'ore_left', 4)
  ```

  The presence gate that makes `zone_reset` wrong for a busy quarry makes it
  right for canonical content.
- **Tool gating:** require a `mining_laser`-tagged item in
  [`contents`](../reference/softcode.md#fn-contents)`(enactor)` before the roll,
  the exact tool-check pattern item [127](127_crafting_stations.md) builds out.
- **Rare seams:** roll a second `margin_under` against a target lowered by 4 on
  each successful swing and mint `a fleck of raw iridium` alongside the ore; the
  weighted-table alternative is the [loot crate](024_loot_crate.md)'s draw.
- **Node fields:** `@clone balthite vein` around a cavern and vary `ore_cap`
  and `regrow_ticks` per copy, since richness is data and the verb rides along
  free.
