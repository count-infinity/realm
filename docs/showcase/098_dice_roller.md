# 098. Dice Roller

> Checklist item 98 ([now]): *roll(), margin_under(), the resolution primitives*

**What you'll build:** A dice cup that rolls any notation out loud
(`roll 3d6`, `roll 2d20kh1`, `roll 4dF`) and reads a 3d6 throw against a
skill with margin narration, alongside the engine's own check pipeline
and the `@rolls` debug echo, so the whole resolution stack sits on one
object.

**Concepts:** the dice kernel ([`roll()`](../reference/softcode.md#fn-roll),
notation to a total), the graded reducers
([`margin_under()`](../reference/softcode.md#fn-margin_under) returning a
`CheckResult` with `.success` / `.margin` / `.roll` / `.effective`), the
engine check layer ([`skill_check()`](../reference/softcode.md#fn-skill_check)
for a bool and its graded sibling
[`check_roll()`](../reference/softcode.md#fn-check_roll), both applying
untrained defaults, condition modifiers, and the ruleset's crit bands),
and `@rolls` for watching dice fall.

## How it works

The cup answers three kinds of question, and each one uses one more layer
of the resolver than the last: a bare notation roll, a margin read
against a skill, and a full engine check. REALM stacks those three layers,
and the cup puts one verb on each. This section walks them from the
bottom up, then explains why the top two can disagree.

### How does notation become a number?

[`roll('3d6')`](../reference/softcode.md#fn-roll) rolls an expression to a
total. The grammar covers `NdS`, `dS`, Fudge `NdF` (each die counts as
-1, 0, or +1), `!` exploding dice, `khK` / `klK` keep-highest / lowest,
and a trailing `+K` / `-K` modifier, so `2d20kh1` keeps the higher of two
d20s (advantage) and `4dF` runs from -4 to +4. This is the raw kernel
with no game rules attached, and malformed notation raises rather than
returning a number, which matters for the cup (see "Engine gaps").

### How does a number become a graded outcome?

[`margin_under(rolled, target)`](../reference/softcode.md#fn-margin_under)
is the GURPS-shaped reducer: it succeeds when `rolled <= target`, and its
`margin` tells you by how much. Its siblings grade other systems the same
way, so
[`margin_over`](../reference/softcode.md#fn-margin_over) is D20 roll-over,
[`band`](../reference/softcode.md#fn-band) is PbtA tiers,
[`highest`](../reference/softcode.md#fn-highest) is Blades, and
[`net_successes`](../reference/softcode.md#fn-net_successes) is a
dice-pool count. Every one of them returns a `CheckResult` rather than a
bare bool, because the margin is where narration lives.

### How does the engine run the whole rulebook?

[`skill_check(enactor, 'stealth')`](../reference/softcode.md#fn-skill_check)
is the whole stack at once: it reads the actor's `skill_<name>` attribute
(or the active game system's untrained default), folds in condition
modifiers (fear, darkness, a buff, all through the `check_mods`
pipeline), and applies the ruleset's crit bands (in GURPS, a 3 or 4
always succeeds and a 17 or 18 always fails). It returns a bool, which is
perfect for a gate and opaque for narration.
[`check_roll(enactor, 'stealth')`](../reference/softcode.md#fn-check_roll)
is its graded sibling: the identical pipeline, but it hands back the
`CheckResult` so you can narrate off `.margin` with every condition and
crit already applied.

### Why `try` and `check` can disagree

The cup's `$try` verb narrates margins from layers 1 and 2 directly: it
reads the skill attribute, rolls, reduces with `margin_under`, and words
the result off `r.margin`. Because it reads the trained level straight, it
does not fold in condition modifiers, so a fear-struck roller still rolls
as if calm. Its `$check` verb calls layer 3 (`skill_check`) instead and
lets `@rolls`, the builder's die-cam, echo the internals. That gap is the
lesson: use the kernel primitives when you want to narrate off data you
control, and the engine check when you want the whole rulebook (untrained
table, `check_mods`, crits) applied for you.

All three verbs are `$`-commands living on the cup, so each fires on the
cup itself when someone in the room types the matching word; there is no
reactive `ON_<EVENT>` hook here, so no `target is me` guard is needed (a
guard is for hooks that fire on every object in the room, like the
[slot machine](001_slot_machine.md)'s payment hook). The names `roll`,
`try`, and `check` are also safe because no built-in command claims them,
and built-ins dispatch before `$`-triggers.

## Build it

First the cup, dropped in the room, with a description that reads its last
throw fresh on every look through the inline
[`V`](../reference/softcode.md#fn-v) attribute read:

```text
@create a dice cup
drop a dice cup
@desc a dice cup = A leather cup, dice rattling inside. [[result = f'Last throw: {V("last", "--")}.']]
```

The notation roller. Dice are social, so the throw goes to the whole room
with [`remit`](../reference/softcode.md#fn-remit) (which reaches everyone
present, the thrower included), and each throw stamps its result onto the
cup with [`set_attr`](../reference/softcode.md#fn-set_attr) so the
description can remember it:

```text
@set a dice cup/cmd_roll = '''
$roll *:
expr = trim(arg0)
total = roll(expr)
set_attr(me, 'last', f'{expr} = {total}')  # the description reads this back
remit(here, f'{name(enactor)} rattles the cup and throws {expr}: {total}.')
'''
```

The margin narrator. The skill level comes from the roller's
`skill_<name>` attribute through
[`get_attr`](../reference/softcode.md#fn-get_attr), with a DX-5 house
default for the untrained (the script's own fallback, separate from the
engine's untrained table). The four narration bands are plain `r.margin`
arithmetic, written as an `if`/`elif` ladder:

```text
@set a dice cup/cmd_try = '''
$try *:
s = trim(arg0).lower()
# untrained falls back to DX-5 here, not the engine's untrained table
lvl = get_attr(enactor, 'skill_' + s, get_attr(enactor, 'dexterity', 10) - 5)
r = margin_under(roll('3d6'), lvl, skill=s)
if r.margin >= 6:
    word = 'critically nails'
elif r.success:
    word = 'makes'
elif r.margin >= -2:
    word = 'barely misses'
else:
    word = 'blows'
remit(here, f'{name(enactor)} rolls {r.roll} vs {s} {r.effective} -- {word} it (margin {r.margin}).')
'''
```

The engine check, one call with everything folded in. It tells the
roller privately with [`pemit`](../reference/softcode.md#fn-pemit) and the
rest of the room with [`oemit`](../reference/softcode.md#fn-oemit):

```text
@set a dice cup/cmd_check = '''
$check *:
s = trim(arg0).lower()
ok = skill_check(enactor, s)
pemit(enactor, 'The table holds its breath... ' + ('You pull it off.' if ok else 'No dice.'))
oemit(enactor, name(enactor) + ' tries a ' + s + ' check and ' + ('makes it.' if ok else 'fumbles.'))
'''
```

## Try it

With every die pinned to 4 so `3d6` totals 12, a throw plays like this:

```text
> roll 3d6
Bilda rattles the cup and throws 3d6: 12.

> roll 2d20kh1
Bilda rattles the cup and throws 2d20kh1: 4.

> roll 3d6+2
Bilda rattles the cup and throws 3d6+2: 14.

> look a dice cup
A leather cup, dice rattling inside. Last throw: 3d6+2 = 14.
```

The totals follow the dice, so only the numbers vary: live, `2d20kh1`
keeps the higher of two real d20s (advantage) and `4dF` runs from -4 to
+4. Now read a throw against a skill:

```text
> @set me/skill_stealth = 13
> try stealth
Bilda rolls 12 vs stealth 13 -- makes it (margin 1).

> try guns
Bilda rolls 12 vs guns 5 -- blows it (margin -7).
```

`try guns` is untrained, so it falls back to DX-5 (a 10 dexterity minus
5), and the margin says how ugly the miss was. Everyone in the room sees
these lines, because `remit` speaks to the whole room.

And the debug echo, as a builder:

```text
> @rolls on
Roll visibility ON.

> check stealth
[roll stealth: 12 vs 13 -> success (margin +1)]
The table holds its breath... You pull it off.
```

The bracketed line is `@rolls` echoing the engine check's dice, and
everyone else in the room sees only `Bilda tries a stealth check and makes
it.`, which is `oemit` doing its job. `try` and `check` can report
different outcomes for the same skill, because `try` reads the raw
attribute while `check` also folds in condition modifiers and crits.

## Going further

- **Other systems, same cup:**
  [`margin_over`](../reference/softcode.md#fn-margin_over)`(roll('d20') + 5, 15)`
  is D20; [`band`](../reference/softcode.md#fn-band)`(roll('2d6') + 1, 7, 10)`
  is PbtA (miss, then 7 to 9, then 10 or more);
  [`highest`](../reference/softcode.md#fn-highest)`(4)` is Blades. One
  reducer swap per genre.
- **Opposed throws:**
  [`contest`](../reference/softcode.md#fn-contest)`(enactor, 'brawn', get('Rook'), 'brawn')`
  rolls both sides and compares margins; see the
  [arm-wrestling table](106_arm_wrestling.md).
- **Graded engine results:** where `$try` re-derives a margin from the raw
  attribute, swap in `check_roll(enactor, s)` to narrate off a
  `CheckResult` that already carries the untrained table, `check_mods`,
  and crits.
- **A gambling cup:** bolt on `ON_PAYMENT` and the
  [slot machine](001_slot_machine.md)'s stake idiom to bet credits on a
  high roll.
- **House dice:** `@clone a dice cup` and change `$try`'s bands, giving
  the thieves' den a loaded cup that narrates failure as success.

**Engine gap:** [`roll()`](../reference/softcode.md#fn-roll) raises on
malformed notation, and there is no `valid_roll()` predicate to test an
expression first. So `roll garbage` does not fail silently, but it surfaces
a raw `Script error: ... bad dice expression: 'garbage'` to the player
rather than a friendly line. A forgiving roll variant, or a `valid_roll()`
guard, would let the cup answer "that is not dice" in its own voice.
