# 107. Dart Board

> Checklist item 107 ([now]): *skill_check margins, CP practice awards*

**What you'll build:** A pub dart board where the *margin* of a 3d6 roll-under
throw picks the ring (bullseye, inner ring, fat single, rim, or the wall), with
a running score per thrower, a chalked house record, and a practice counter that
raises your `darts` skill every tenth throw.

**Concepts:** margin-graded resolution (a reducer that returns a `CheckResult`
carrying `.margin`, not a bool), margin bands mapped to ring scores, per-player
state kept under computed attribute keys, and an **admin-owned board** using its
owner's authority to write a player's character sheet (the practice award).

## How it works

The finished board is one object that answers `throw`. Each throw is a single
3d6 roll-under check, but where the dart lands tracks *how well* you beat your
number: a wide margin is the bullseye, a slim one is the rim, and a failure
thunks into the wall. The board keeps a running score per thrower, chalks the
house record into its own description, and every tenth throw nudges your `darts`
skill up by one. This section answers three questions: how a margin becomes a
ring, how the board writes a level onto your character sheet, and why it rolls
the raw reducer instead of the full engine check.

### How a margin becomes a ring

A pass/fail check throws away the interesting half of the result.
[`margin_under`](../reference/softcode.md#fn-margin_under) keeps it: given a
rolled total and a target, it returns a `CheckResult` whose `.margin` is how far
under the target you landed, rather than a bare bool. The board rolls
[`roll('3d6')`](../reference/softcode.md#fn-roll) against the thrower's level and
reads `r.margin`. Six or more is the bullseye (50 points), 3 to 5 the inner ring
(25), 1 or 2 a fat single (15), exactly on the number (margin 0) the rim (5), and
any failure scores nothing. [`switch`](../reference/softcode.md#fn-switch) then
maps the point value to the ring's name for the announce, which goes to the whole
room with [`remit`](../reference/softcode.md#fn-remit).

The level itself comes from the thrower's `skill_darts` attribute, read with
[`get_attr`](../reference/softcode.md#fn-get_attr) under an untrained default of
DX minus 4, which is the shape the game system gives its own thrown-and-aimed
skills such as guns and melee. The [dice roller](098_dice_roller.md) narrates the
same margin machinery against any skill you name.

### How the board trains you

Every throw counts toward practice, and every tenth throw raises the thrower's
`darts` skill by one. Raising `skill_darts` is a write to *someone else's*
character sheet, which [`controls`](../reference/softcode.md#fn-controls) forbids
an ordinary object. The board gets away with it because it is built by, and so
owned by, an admin: a script runs with its owner's authority, so an admin-owned
board can write a player's sheet, which is the sanctioned pattern for anything
that awards progression. On a board owned by an ordinary builder the
[`set_attr`](../reference/softcode.md#fn-set_attr) call returns `False` and the
award line never sends, so the mechanic fails closed. The new level is real
progression: the `points` command lists the skill, `improve` reads it, and every
darts check anywhere uses it. Totals, practice counts, and the record are all
plain attribute keys on the board, so `@examine a dart board` reads every one.

### Two verbs, and why neither needs a guard

`throw` and `chalk` are both `$`-commands, and a `$`-command runs only on the
object whose attribute matched, so neither needs the `if target is me:` guard
that a reactive `ON_<EVENT>` hook does. An event hook fires on every object in
the room and must check that it is the one the action targeted; a verb never
does, because the match already picked the object. See
[Guard on `target`](../reference/softcode.md#guard-on-target). The board carries
no reactive hook at all.

### Why the raw reducer, and when to reach for check_roll

The board rolls `margin_under` directly so it can set its own untrained default
(DX minus 4) rather than the neutral floor the engine gives a skill it does not
list. The trade-off is that a raw reducer does not fold in condition modifiers,
so a tipsy penalty on the thrower would go unseen. When you want those folded in,
[`check_roll`](../reference/softcode.md#fn-check_roll) runs the same roll through
the full check pipeline and hands back the same graded `CheckResult`, `check_mods`
and ruleset crit bands included. Swapping the one `margin_under` line for
`check_roll(enactor, 'darts')` is all it takes, at the cost of that custom
default. The pass/fail-only
[`skill_check`](../reference/softcode.md#fn-skill_check) is the third option, for
when you want a gate rather than a margin.

## Build it

Build this as an **admin**, because the practice award needs the owner's
authority over a player's sheet. Create the board, drop it, and give it a face
whose `[[...]]` block reads the house record fresh with
[`V`](../reference/softcode.md#fn-v) on every look:

```text
@create a dart board
drop a dart board
@desc a dart board = Cork and sisal, more hole than board. [[result = f'Chalked below: house record {V("record", 0)}.']]
```

The throw is the whole game. In order, it reads the thrower's level, rolls and
grades the margin, maps the band to a point value and the ring's name, announces
to the room, updates this thrower's running total and the house record, then
counts the throw and, on every tenth, raises the skill:

```text
@set a dart board/cmd_throw = '''
$throw:
lvl = get_attr(enactor, 'skill_darts', get_attr(enactor, 'dexterity', 10) - 4)  # untrained darts default to DX-4, the guns/melee shape
r = margin_under(roll('3d6'), lvl, skill='darts')
m = r.margin
if not r.success:
    pts = 0
elif m >= 6:
    pts = 50
elif m >= 3:
    pts = 25
elif m >= 1:
    pts = 15
else:
    pts = 5
spot = switch(pts, 50, 'BULLSEYE', 25, 'the inner ring', 15, 'a fat single', 5, 'the rim', 'the wall with a sad thunk')
remit(here, f'{name(enactor)} throws -- {spot}! ({pts} points)')
total = incr('total_' + enactor.id, pts)  # this thrower's running score, keyed by id
set_attr(me, 'record', max(V('record', 0), total))
n = incr('practice_' + enactor.id)
if n % 10 == 0 and set_attr(enactor, 'skill_darts', lvl + 1):  # admin-owned board writes the thrower's sheet
    pemit(enactor, f'Your arm is learning: darts rises to {lvl + 1}.')
'''
```

The scoring keys are computed per player (`total_<id>`, `practice_<id>`), so two
throwers never share a tally. [`incr`](../reference/softcode.md#fn-incr) bumps a
key on the board and hands back the new value:
[`name`](../reference/softcode.md#fn-name) fills the announce and
[`pemit`](../reference/softcode.md#fn-pemit) sends the private coaching line only
to the thrower.

The chalk line is a single read, so it stays a one-liner. It reports this
player's own total and dart count off the board's per-player keys:

```text
@set a dart board/cmd_chalk = $chalk: pemit(enactor, f'Your chalk line: {V("total_" + enactor.id, 0)} points over {V("practice_" + enactor.id, 0)} darts.')
```

## Try it

An untrained thrower rarely beats the wall, because darts defaults to DX minus 4
(a 6 at DX 10) and a 3d6 total rarely lands under it:

```text
> throw
Kess throws -- the wall with a sad thunk! (0 points)
```

Sheet writes are builder-gated, so an admin trains the demo skill, and the margin
starts paying:

```text
> @set Kess/skill_darts = 14
> throw
Kess throws -- a fat single! (15 points)

> chalk
Your chalk line: 15 points over 2 darts.
```

Only the ring and its points vary here, since they follow the roll: a 3d6 of 12
beats 14 by 2 for the fat single, while a lower roll widens the margin toward the
inner ring or the bullseye. On the tenth dart the practice award fires:

```text
> throw
Kess throws -- a fat single! (15 points)
Your arm is learning: darts rises to 15.
```

Because the board is admin-owned, that write lands on Kess's real sheet: `points`
now lists the higher darts, and `improve` and every darts check see it. The house
record rides live in the description:

```text
> look a dart board
Cork and sisal, more hole than board. Chalked below: house record 160.
```

## Going further

- **A proper 501:** start `total_<id>` at 501 and subtract each throw; first to
  exactly zero wins the leg, and the margin bands become your doubles.
- **Called shots:** an `$aim bull` verb sets a per-player target and shifts the
  bands so the bullseye needs margin 8 and everything else scores nothing, which
  is risk for reward in one attribute.
- **Drunk darts:** [`apply_effect(enactor, 'modifier_effect', kind='tipsy',
  check_mods={'darts': -3}, ...)`](../reference/softcode.md#fn-apply_effect) from
  the [bartender](064_bartender.md)'s taps penalizes the throw. The board's raw
  `margin_under` does not see it, but switching the throw to
  `check_roll(enactor, 'darts')` folds the penalty in.
- **League night:** a `script_ticker` that snapshots and resets every `total_*`
  key weekly, appending champions to a `seasons` list.
