# 121. Gathering Nodes

> Checklist item 121 — [now] — *depletion attrs, on_tick respawn, yield margins*

**What you'll build:** A seam of balthite crystal you can `mine` — each
swing rolls prospecting, better margins pry loose more ore, the vein
runs dry after a few loads, and a slow ticker grows it back while the
miners are off spending.

**Concepts:** a resource node as **plain attributes** (`ore_left` down,
`regrow_left` up), graded yield via `margin_under()` (the roll's
*margin* sizes the haul, not just pass/fail), spawning the take with
`create_obj()`, and a `script_ticker` respawn — plus when the engine's
*native* repop (`zone_reset`) is and isn't the right tool.

## How it works

**The node is a counter with a verb.** `ore_left` is everything the
vein knows about itself. `$mine vein` reads it, rolls, decrements it,
and mints ore chunks into the room with `create_obj()` — the spawner
vocabulary from the [vending machine](002_vending_machine.md). The
description is the gauge: an inline `[[...]]` block reads `ore_left`
so `look` tells a prospector whether the seam is worth a swing.

**Margins, not booleans.** `skill_check()` answers yes/no;
`margin_under(roll('3d6'), skill)` answers *how well* — a graded
`CheckResult` whose `.margin` is spare skill. `1 + margin // 3` turns
that into yield: a scrape-by success pries one chunk, a margin of 6
pries three. Every failure text quotes the numbers (`rolled 15 vs
prospecting 12`), the house style for legible dice.

**Respawn is a ticker, deliberately.** The engine *does* have native
repop — the `zone_reset` behavior returns a whole zone to its authored
state on a timer. But zone reset is **presence-gated**: it never fires
while a player stands anywhere in the zone, which is exactly wrong for
a working mine — the one place guaranteed to have someone loitering in
it is the room with the ore. A vein regrows *under* the miners'
boots, so it keeps its own clock: a `script_ticker` whose `on_tick`
counts `regrow_left` down only while the seam is spent, then refills
`ore_left` from `ore_cap`. (For nodes in a dungeon that should reset
canonically with the dungeon — while nobody watches — `zone_reset` is
the better fit; see Going further.)

## Build it

The vein, with its gauge in the description (interval 30 ≈ two minutes
per regrowth step at the default 4s tick; we regrow in 3 steps):

```text
@create balthite vein
drop balthite vein
@desc balthite vein = A seam of blue-green balthite crystal veining the rock face. [[left = V('ore_left', 0); result = 'It glitters, thick with ore.' if left > 2 else ('Only pale traces remain in the cut.' if left > 0 else 'It is hacked bare -- nothing but scarred rock.')]]
@set balthite vein/ore_cap = 4
@set balthite vein/ore_left = 4
@set balthite vein/regrow_ticks = 3
```

The mining verb — guard, roll, yield, deplete, and announce, in that
order. Note the margin arithmetic and the numeric failure text:

```text
@set balthite vein/cmd_mine = $mine vein: left = V('ore_left', 0); res = margin_under(roll('3d6'), get_attr(enactor, 'skill_prospecting', 8)); take = min(left, 1 + max(0, res.margin) // 3); pemit(enactor, 'The vein is hacked bare. Rock heals on its own clock; come back later.') if left < 1 else None; pemit(enactor, 'Sparks, dust, no ore. (rolled ' + str(res.roll) + ' vs prospecting ' + str(res.effective) + ')') if left > 0 and not res.success else None; (decr('ore_left', take), [create_obj('a chunk of balthite ore', ['thing', 'ore'], here) for i in range(take)], remit(here, name(enactor) + ' swings at the vein -- ' + str(take) + ' chunk(s) of balthite clatter free.'), (set_attr(me, 'regrow_left', V('regrow_ticks', 3)), remit(here, 'The seam splits and goes dark, spent.')) if left - take < 1 else None) if left > 0 and res.success else None
```

The regrowth clock — dormant while any ore remains, counting while the
seam is spent:

```text
@set balthite vein/on_tick = left = V('ore_left', 0); r = V('regrow_left', 0); (decr('regrow_left') if r > 1 else (set_attr(me, 'ore_left', V('ore_cap', 4)), del_attr(me, 'regrow_left'), remit(here, 'Fresh balthite creeps glittering back across the rock face.'))) if left < 1 else None
@behavior balthite vein = script_ticker, interval:30
```

## Try it

Give yourself a pick hand and swing:

```text
@set me/skill_prospecting = 12
mine vein
```

A good roll (say margin 6) rings out `... swings at the vein -- 3
chunk(s) of balthite clatter free.` and three `a chunk of balthite
ore` objects hit the floor for the taking. A bad one answers with the
dice on the table: `Sparks, dust, no ore. (rolled 15 vs prospecting
12)`. Keep swinging: when the last chunk comes loose you also get
`The seam splits and goes dark, spent.`, `look balthite vein` reads
`hacked bare`, and further mining refuses. Then wait three ticker
beats (or force them with `@tr balthite vein/on_tick` three times) —
`Fresh balthite creeps glittering back across the rock face.` and the
gauge glitters again.

The ore chunks are tagged `ore` — that tag is the *type system* the
whole crafting chain keys on: the [assembly bench](122_recipe_crafting.md)
counts them, the [arc smelter](123_refining_chain.md) eats them.

## Going further

- **Native repop instead:** for a vein that should reset with its
  dungeon — only while nobody's inside — skip the ticker and let the
  zone master do it: `@zone here = mine`, `@zone/master Mine Brain =
  mine`, `@behavior Mine Brain = zone_reset`, `@set Mine Brain/ON_RESET
  = set_attr(get('balthite vein'), 'ore_left', 4)`. The presence gate
  that makes `zone_reset` wrong for a busy quarry makes it perfect for
  canonical content.
- **Tool gating:** require a `mining_laser`-tagged item in
  `contents(enactor)` before the roll — the exact tool-check pattern
  item [127](127_crafting_stations.md) builds out.
- **Rare seams:** roll a second `margin_under` at `-4` on each
  successful swing and mint `a fleck of raw iridium` alongside the
  ore — the weighted-table alternative is the
  [loot crate](024_loot_crate.md)'s draw.
- **Node fields:** `@clone balthite vein` around a cavern and vary
  `ore_cap`/`regrow_ticks` per copy — richness is data, the verb rides
  along free.
