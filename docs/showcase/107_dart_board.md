# 107. Dart Board

> Checklist item 107 — [now] — *skill_check margins, CP practice awards*

**What you'll build:** A pub dart board where the *margin* of a
3d6-under-skill throw picks the ring — bullseye, inner ring, fat
single, rim, or the wall — with per-player running scores, a chalked
house record, and a practice counter that raises your `darts` skill
every ten throws.

**Concepts:** margin-graded resolution (`margin_under()` returning a
`CheckResult`, not a bool), margin bands → ring scores, per-player
state in computed attribute keys, and an **admin-owned master** using
owner authority to write a player's sheet (the practice award).

## How it works

**Rings are margins.** A dart throw is one roll-under check, but pass/
fail is boring — where the dart *lands* should track how well you beat
your number. `margin_under(roll('3d6'), lvl)` grades exactly that:
make it by 6+ and it's the bullseye (50), by 3–5 the inner ring (25),
by 1–2 a fat single (15), exactly (margin 0) the rim (5), and a miss
thunks into the wall. The skill level reads `skill_darts` with a DX−4
untrained default — the same shape the game system's own table uses.
(`skill_check()` would fold in condition modifiers and crits but
returns only a bool — margins force us down to the kernel primitive;
see the gap note.)

**Practice writes the sheet — with the owner's authority.** Every
throw ticks `practice_<id>` on the board; every tenth throw the board
raises the thrower's `skill_darts` by one. That's a mutation of
*someone else's* character, which `controls()` forbids for ordinary
objects — so the board must be built by (owned by) an **admin**: an
admin-owned master wields admin authority, which is precisely the
sanctioned pattern for masters that award progression. On a
builder-owned copy the `set_attr` simply returns `False` and the award
line never sends — fail-closed.

**Everything is auditable.** Totals, practice counts, the record —
attribute keys on the board. `@examine a dart board` is the chalk.

## Build it

As an **admin** (the practice award needs owner authority over
players):

```text
@create a dart board
drop a dart board
@desc a dart board = Cork and sisal, more hole than board. [[result = 'Chalked below: house record ' + str(get_attr(me, 'record', 0)) + '.']]
```

The throw — one roll, margin to ring, tallies, and the ten-throw
coaching branch:

```text
@set a dart board/cmd_throw = $throw: lvl = get_attr(enactor, 'skill_darts', get_attr(enactor, 'dexterity', 10) - 4); r = margin_under(roll('3d6'), lvl, skill='darts'); m = r.margin; pts = 50 if r.success and m >= 6 else (25 if r.success and m >= 3 else (15 if r.success and m >= 1 else (5 if r.success else 0))); spot = switch(pts, 50, 'BULLSEYE', 25, 'the inner ring', 15, 'a fat single', 5, 'the rim', 'the wall with a sad thunk'); remit(here, name(enactor) + ' throws -- ' + spot + '! (' + str(pts) + ' points)'); t = 'total_' + enactor.id; total = get_attr(me, t, 0) + pts; set_attr(me, t, total); set_attr(me, 'record', max(get_attr(me, 'record', 0), total)); k = 'practice_' + enactor.id; n = get_attr(me, k, 0) + 1; set_attr(me, k, n); (pemit(enactor, 'Your arm is learning: darts rises to ' + str(lvl + 1) + '.') if set_attr(enactor, 'skill_darts', lvl + 1) else None) if n % 10 == 0 else None
```

The chalk line:

```text
@set a dart board/cmd_chalk = $chalk: pemit(enactor, 'Your chalk line: ' + str(get_attr(me, 'total_' + enactor.id, 0)) + ' points over ' + str(get_attr(me, 'practice_' + enactor.id, 0)) + ' darts.')
```

## Try it

```text
throw            -> "Kess throws -- the wall with a sad thunk! (0 points)"
                    (untrained: DX 10 gives darts 6 -- rough night)
@set me/skill_darts = 12
throw            -> "Kess throws -- the inner ring! (25 points)"
chalk            -> "Your chalk line: 25 points over 2 darts."
look a dart board -> the house record, live in the description
```

Keep throwing: on your tenth dart —

```text
throw            -> "...(15 points)"
                    "Your arm is learning: darts rises to 13."
```

The award is real sheet progression: `improve`/`points` sees the new
level, and every darts check anywhere uses it.

## Going further

- **A proper 501:** start `total_<id>` at 501 and subtract; first to
  exactly zero wins the leg — the margin bands become your doubles.
- **Called shots:** `$aim bull` sets a per-player target and shifts
  the bands (bullseye needs margin 8, everything else scores 0) — risk
  for reward, one attribute.
- **Drunk darts:** `apply_effect(enactor, 'modifier_effect',
  kind='tipsy', check_mods={'darts': -3}, ...)` from the
  [bartender](064_bartender.md)'s taps — though note the board's raw
  `margin_under` won't see it (the gap below); a `skill_check` gate on
  top would.
- **League night:** a `script_ticker` that snapshots and resets all
  `total_*` keys weekly, appending champions to a `seasons` list.

**Engine gaps:** same as [item 98](098_dice_roller.md), felt harder
here: no softcode call returns the graded `CheckResult` of the *full*
engine check pipeline — `skill_check()` collapses to bool, so ring
scoring must re-derive the roll via `margin_under()` and thereby loses
condition modifiers (`check_mods`) and ruleset crit bands. A
`check_roll(obj, skill, mod)` returning the CheckResult would let this
board honor the tipsy penalty above.
