# 125. Quality Tiers

> Checklist item 125 ([now]): *margin-driven output attrs*

**What you'll build:** A finishing lathe where the dice decide not just
*whether* you made a vibro-blade but how good it is. The roll's margin picks
fine, good, or shoddy, and the tier stamps real numbers on the blade: trade
value, edge durability, and a maker's-mark line every buyer can read.

**Concepts:** the graded `CheckResult` (where
[`margin_under`](../reference/softcode.md#fn-margin_under) hands back `.margin`,
not a bool), a **tier table as data** (`[min_margin, label, value_mult,
durability]` rows), stamping attributes onto a freshly
[`create_obj`](../reference/softcode.md#fn-create_obj)ed item, and `desc_extras`
detail rows for the grade lines a plain `look` shows.

## How it works

The finished lathe is one object that answers `forge blade`: one ingot goes in,
one graded blade comes out, and the *margin* of the roll, not merely its pass or
fail, sets the blade's quality tier and the numbers stamped on it. This section
answers three questions: how a margin becomes a tier, what the tier writes and
what reads those numbers, and when to reach for `check_roll` instead.

### How a margin becomes a tier

GURPS-shaped checks are roll-under, so success means the 3d6 total came in at or
under the skill, and the margin is how far under you landed.
[`margin_under`](../reference/softcode.md#fn-margin_under) keeps that number:
given a rolled total and a target it returns a `CheckResult` whose `.margin` is
`skill - roll`, the single value this whole item runs on. The lathe walks a
`tiers` table sorted best first and takes the first row whose threshold the
margin clears: `4+` is fine work, `0` to `3` is good, and a failed roll (a
negative margin) still produces a blade, a shoddy one worth a fraction and half
as tough. Quality replaces the pass/fail cliff with a slope, which is why
crafters keep pulling the lever.

### What the tier writes, and what reads it

`quality` is a label, but `value` is the number the
[shopkeeper](063_shopkeeper.md) and the [pawn shop](090_pawn_shop.md) price
from, because both derive their prices from an item's `value` attribute, and
`durability` is data the [repair bench](095_durability_repair.md) burns down.
The tier rows carry a multiplier and a durability, so a balance pass is an
`@set` on the table, never a script edit. The grade lines ride as `desc_extras`
detail rows so anyone who looks reads the blade's face, while `create_obj`'s own
`description=` argument sets the static line above them. Detail rows suit the tier-dependent text
because each blade carries different numbers, the same split the
[camera](008_camera.md) uses for its captured scene.

### margin_under or check_roll

This build derives the tier with `margin_under(roll('3d6'), skill_attr)`, a raw
graded roll that reads the trained skill directly and so ignores active
`check_mods` such as a fear penalty or a meal buff (see the
[cooking tutorial](129_cooking_buffs.md)). To let conditions reach a crafting
roll, swap it for
[`check_roll(enactor, 'smithing')`](../reference/softcode.md#fn-check_roll),
which returns the same graded `CheckResult` (`.margin`, `.success`) but *through*
the real `check()` pipeline, folding every modifier in. The pass/fail-only
[`skill_check`](../reference/softcode.md#fn-skill_check) is the third option, for
when you want a gate rather than a margin. The [dart board](107_dart_board.md)
weighs the same choice for its rings.

### Why the forge verb needs no guard

`forge` is a `$`-command, and a `$`-command runs only on the object whose
attribute matched, so it needs no `if target is me:` guard. That guard belongs
to a reactive `ON_<EVENT>` hook, which fires on every object in the room and
must check it is the one the action targeted; see
[Guard on `target`](../reference/softcode.md#guard-on-target). The lathe carries
no such hook at all.

## Build it

Create the lathe, drop it, and give it a face:

```text
@create finishing lathe
drop finishing lathe
@desc finishing lathe = A precision lathe behind a spotless splash guard. A brass plaque grades every blade it releases.
```

Set the base value and the tier table. Rows are `[min_margin, label,
value_mult, durability]`, best tier first, so the scan stops at the first row
the margin clears:

```text
@set finishing lathe/base_value = 50
@set finishing lathe/tiers = [[4, "fine", 3.0, 18], [0, "good", 1.0, 12], [-99, "shoddy", 0.4, 6]]
```

The forge verb takes one ingot and returns one graded blade. In order it
collects your ingots and refuses an empty chuck, rolls smithing and grades the
margin, walks the table best first for the tier, burns the ingot, mints the
blade with [`create_obj`](../reference/softcode.md#fn-create_obj), then stamps
`quality`, `value`, and `durability` plus two readable detail rows with
[`set_attr`](../reference/softcode.md#fn-set_attr) before announcing the grade to
the room with [`remit`](../reference/softcode.md#fn-remit):

```text
@set finishing lathe/cmd_forge = '''
$forge blade:
stock = [o for o in contents(enactor) if has_tag(o, 'ingot')]
if not stock:
    pemit(enactor, 'The chuck is empty: bring a duralloy ingot.')
else:
    res = margin_under(roll('3d6'), get_attr(enactor, 'skill_smithing', 8))
    tier = [row for row in V('tiers', []) if res.margin >= row[0]][0]  # first row the margin clears, best first
    value = int(V('base_value', 50) * tier[2])
    destroy_obj(stock[0])
    blade = create_obj('a duralloy vibro-blade', ['thing', 'blade'], here, description='A slender vibro-blade.')
    set_attr(blade, 'quality', tier[1])
    set_attr(blade, 'value', value)
    set_attr(blade, 'durability', tier[3])
    set_attr(blade, 'desc_extras', [['', f'The maker-stamp grades it {tier[1].upper()}.'], ['', f'Edge integrity: {tier[3]}. Trade value: {value} cr.']])
    remit(here, f'{name(enactor)} draws a {tier[1]} vibro-blade off the lathe. (margin {res.margin})')
'''
```

The blade lands in the room, not your hands, because softcode may not conjure
objects into another player, so `get` it off the floor afterward.

## Try it

Train the skill, mint three ingots, and forge:

```text
> @set me/skill_smithing = 12
> @eval [create_obj('a duralloy ingot', ['thing', 'ingot'], me) for i in range(3)]
> forge blade
Bilda draws a fine vibro-blade off the lathe. (margin 6)

> look duralloy vibro-blade
A slender vibro-blade.
The maker-stamp grades it FINE.
Edge integrity: 18. Trade value: 150 cr.
```

Only the grade and its numbers vary here, since they follow the roll. A 3d6
total of 6 against smithing 12 is a margin of 6, so the plaque reads FINE at 150
cr. A total of 12 lands margin 0 for a good blade at face value (50 cr), and a
botched roll (margin -6) still hands you the blade, a shoddy one worth 20 cr
with integrity 6, and the plaque says so to anyone who looks. `@examine` a blade
to read the raw stamps `quality`, `value`, and `durability`. Empty-handed, the
lathe refuses before any dice:

```text
> forge blade
The chuck is empty: bring a duralloy ingot.
```

## Going further

- **Sell the difference:** hand a fine and a shoddy blade to a
  [shopkeeper](063_shopkeeper.md); `sell` prices off `value`, so the 150/20
  split is already real money, and the [pawn shop](090_pawn_shop.md) reads the
  same number.
- **Crit fireworks:** GURPS crits (a 3d6 total of 3 or 4) deserve a `masterwork`
  tier above fine; check `res.roll <= 4` before the table scan.
- **Durability that matters:** have weapons burn 1 `durability` per fight and
  refuse at 0, and the [repair bench](095_durability_repair.md) closes that
  loop.
- **Signed work:** stamp `set_attr(blade, 'maker', name(enactor))` and show it
  in a detail row, so provenance turns quality into reputation.
