# 125. Quality Tiers

> Checklist item 125 — [now] — *margin-driven output attrs*

**What you'll build:** A finishing lathe where the dice don't just
decide *whether* you made a vibro-blade — they decide how good it is.
The roll's margin picks **fine / good / shoddy**, and the tier stamps
real numbers on the output: trade value, edge durability, and a
maker's-mark description every buyer can read.

**Concepts:** the graded `CheckResult` (`margin_under(...)` hands back
`.margin`, not a bool — the single number this whole item runs on), a
**tier table as data** (`[min_margin, label, value_mult, durability]`
rows), stamping attributes onto a freshly `create_obj()`ed thing, and
`desc_extras` as the spawned item's face (things minted by softcode
can't be `@desc`ed by script — detail rows are the workshop-standard
workaround, from the [camera](008_camera.md)).

## How it works

**Margin is quality.** GURPS-shaped checks are roll-under: margin =
skill − roll, how much better you did than you needed to. The lathe
walks a `tiers` table sorted best-first and takes the first row whose
threshold the margin clears: `4+` is fine work, `0..3` is good, and a
failed roll (negative margin) still produces a blade — a `shoddy` one
worth a fraction and half as tough. Quality replaces the pass/fail
cliff with a slope, which is why crafters keep pulling the lever.

**Tiers write real attributes.** `quality` is a label, but `value`
is the number the [shopkeeper](063_shopkeeper.md) and the pawn shop
(item 90) actually price from (`db.value` is the engine's economy
convention), and `durability` is data for a repair system (item 95) to
burn down. The tier rows carry a multiplier and a durability so a
balance pass is an `@set` on the table, never a script edit.

**On graded rolls and conditions.** This build derives the tier with
`margin_under(roll('3d6'), skill_attr)` — a fine way to get a *raw*
graded roll, and what this tutorial teaches. Note the one thing it does
*not* do: it reads the trained skill directly, so it ignores active
`check_mods` (fear, a meal buff — see the
[cooking tutorial](129_cooking_buffs.md)). If you want conditions to
reach a crafting roll, swap it for `check_roll(enactor, 'smithing')`,
which returns the same graded `CheckResult` (`.margin`, `.success`) but
*through* the real `check()` pipeline, folding every modifier in. (This
was once an engine gap; `check_roll` closed it 2026-07-17.)

## Build it

The lathe and its tier table (rows are `[min_margin, label,
value_mult, durability]`, best tier first; base value 50):

```text
@create finishing lathe
drop finishing lathe
@desc finishing lathe = A precision lathe behind a spotless splash guard. A brass plaque grades every blade it releases.
@set finishing lathe/base_value = 50
@set finishing lathe/tiers = [[4, "fine", 3.0, 18], [0, "good", 1.0, 12], [-99, "shoddy", 0.4, 6]]
```

The forge verb — one ingot in, one graded blade out. The tier lookup
is a first-match scan of the table; the stamped `desc_extras` rows
make the grade readable on a plain `look`:

```text
@set finishing lathe/cmd_forge = $forge blade: stock = [o for o in contents(enactor) if has_tag(o, 'ingot')]; pemit(enactor, 'The chuck is empty: bring a duralloy ingot.') if not stock else None; res = margin_under(roll('3d6'), get_attr(enactor, 'skill_smithing', 8)) if stock else None; tier = [row for row in V('tiers', []) if res.margin >= row[0]][0] if stock else None; (destroy_obj(stock[0]), [(set_attr(b, 'quality', tier[1]), set_attr(b, 'value', int(V('base_value', 50) * tier[2])), set_attr(b, 'durability', tier[3]), set_attr(b, 'desc_extras', [['', f'A slender vibro-blade. The maker-stamp grades it {tier[1].upper()}.'], ['', f'Edge integrity: {tier[3]}. Trade value: {int(V("base_value", 50) * tier[2])} cr.']]), remit(here, f'{name(enactor)} draws a {tier[1]} vibro-blade off the lathe. (margin {res.margin})')) for b in [create_obj('a duralloy vibro-blade', ['thing', 'blade'], here)]]) if stock else None
```

(The `[... for b in [create_obj(...)]]` shape is the one-line *bind*
idiom — make the blade once, then stamp it five ways.)

## Try it

```text
@set me/skill_smithing = 12
@eval [create_obj('a duralloy ingot', ['thing', 'ingot'], me) for i in range(3)]
forge blade
forge blade
forge blade
```

Three pulls, three grades, dice willing. A margin of 6 announces
`... draws a fine vibro-blade off the lathe. (margin 6)`; `look
duralloy vibro-blade` reads `The maker-stamp grades it FINE. Edge
integrity: 18. Trade value: 150 cr.` A margin of 0 makes a `good`
blade at face value; a botch (`margin -6`) still hands you the
blade — `shoddy`, 20 cr, integrity 6, and the plaque says so to
anyone who looks. `@examine` a blade to see the raw stamps:
`quality`, `value`, `durability`. Empty-handed, the lathe refuses
before any dice: `The chuck is empty: bring a duralloy ingot.`

## Going further

- **Sell the difference:** hand a fine and a shoddy blade to a
  [shopkeeper](063_shopkeeper.md) — `sell` prices off `db.value`, so
  the 150/20 split is already real money; the pawn shop (item 90)
  reads the same number.
- **Crit fireworks:** GURPS crits (roll 3–4) deserve a `masterwork`
  tier above fine — check `res.roll <= 4` before the table scan.
- **Durability that matters:** have weapons burn 1 `durability` per
  fight and refuse at 0 — item 95's repair bench closes that loop.
- **Signed work:** stamp `set_attr(b, 'maker', name(enactor))` and
  show it in the detail rows — provenance turns quality into
  reputation.
