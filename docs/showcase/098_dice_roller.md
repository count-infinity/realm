# 098. Dice Roller

> Checklist item 98 — [now] — *roll(), margin_under(), the resolution primitives*

**What you'll build:** A dice cup that rolls any notation out loud
(`roll 3d6`, `roll 2d20kh1`, `roll 4dF`), and interprets a 3d6 throw
against a skill with margin narration — plus the engine's own check
pipeline and the `@rolls` debug echo, so you see the whole resolution
stack in one object.

**Concepts:** the dice kernel (`roll()` notation → total), the graded
reducers (`margin_under()` → a `CheckResult` with `.success` /
`.margin` / `.roll` / `.effective`), the engine check layer
(`skill_check()` with untrained defaults, condition modifiers, and the
game system's crit rules), and `@rolls` for watching dice fall.

## How it works

REALM resolves rolls in **three layers**, and the cup exposes each:

1. **Notation → number.** `roll('3d6')` rolls an expression to a total.
   The grammar covers `NdS`, `dS`, Fudge `NdF` (each die −1/0/+1), `!`
   exploding dice, `khK`/`klK` keep-highest/lowest, and a trailing
   `+K`/`-K` modifier. This is the raw kernel — no game rules attached.
2. **Number → graded outcome.** `margin_under(rolled, target)` is the
   GURPS-shaped reducer: success if `rolled <= target`, and a `margin`
   telling you *by how much*. Its siblings (`margin_over`, `band`,
   `highest`, `net_successes`) grade other systems the same way; all of
   them return a `CheckResult`, never a bare bool — the margin is where
   narration lives.
3. **The engine check.** `skill_check(enactor, 'stealth')` is the whole
   stack at once: the actor's `skill_<name>` attribute (or the game
   system's untrained default), condition modifiers (fear, darkness —
   the `check_mods` pipeline), and the active ruleset's crit bands
   (in GURPS, 3–4 always succeed, 17–18 always fail). It returns a
   bool — perfect for gates, opaque for narration.

The cup's `$try` verb narrates margins by using layers 1+2 directly:
read the skill attribute, roll, reduce, and word the result off
`r.margin`. Its `$check` verb calls layer 3 and lets `@rolls` (the
builder's die-cam: it echoes `[roll skill: 12 vs 8 -> failure
(margin -4)]` for every engine check you make) show the internals.

## Build it

The cup, with a memory of its last throw in the description:

```text
@create a dice cup
drop a dice cup
@desc a dice cup = A leather cup, dice rattling inside. [[result = f'Last throw: {V("last", "--")}.']]
```

The notation roller. Dice are social — the throw goes to the whole
room with `remit`:

```text
@set a dice cup/cmd_roll = $roll *: expr = trim(arg0); total = roll(expr); set_attr(me, 'last', f'{expr} = {total}'); remit(here, f'{name(enactor)} rattles the cup and throws {expr}: {total}.')
```

The margin narrator. Skill level comes from the roller's
`skill_<name>` attribute, with a DX−5 house default for the untrained;
the four narration bands are pure `r.margin` arithmetic:

```text
@set a dice cup/cmd_try = $try *: s = trim(arg0).lower(); lvl = get_attr(enactor, 'skill_' + s, get_attr(enactor, 'dexterity', 10) - 5); r = margin_under(roll('3d6'), lvl, skill=s); word = 'critically nails' if r.margin >= 6 else ('makes' if r.success else ('barely misses' if r.margin >= -2 else 'blows')); remit(here, f'{name(enactor)} rolls {r.roll} vs {s} {r.effective} -- {word} it (margin {r.margin}).')
```

The engine check — one call, everything folded in:

```text
@set a dice cup/cmd_check = $check *: s = trim(arg0).lower(); ok = skill_check(enactor, s); pemit(enactor, 'The table holds its breath... ' + ('You pull it off.' if ok else 'No dice.')); oemit(enactor, name(enactor) + ' tries a ' + s + ' check and ' + ('makes it.' if ok else 'fumbles.'))
```

## Try it

```text
roll 3d6            -> "Bilda rattles the cup and throws 3d6: 12."
roll 2d20kh1        -> advantage, D&D-style: two d20s, keep the best
roll 4dF            -> Fudge dice: -4..+4
roll 3d6+2          -> flat modifier
@set me/skill_stealth = 13
try stealth         -> "Bilda rolls 12 vs stealth 13 -- makes it (margin 1)."
try guns            -> untrained: vs DX-5, and the margin says how ugly
look a dice cup     -> the description remembers your last throw
```

And the debug echo, as a builder:

```text
@rolls on
check stealth       -> "[roll stealth: 12 vs 13 -> success (margin +1)]"
                       ...then "The table holds its breath... You pull it off."
```

`try` and `check` can disagree — `try` reads the raw attribute, while
`check` also folds in condition modifiers and crits. That gap *is* the
lesson: use kernel primitives when you need margins to narrate, the
engine check when you need the whole rulebook applied.

## Going further

- **Other systems, same cup:** `margin_over(roll('d20') + 5, 15)` is
  D20; `band(roll('2d6') + 1, 7, 10)` is PbtA (miss / 7–9 / 10+);
  `highest(4)` is Blades. One reducer swap per genre.
- **Opposed throws:** `contest(enactor, 'brawn', get('Rook'), 'brawn')`
  rolls both sides and compares margins — see the
  [arm-wrestling table](106_arm_wrestling.md).
- **A gambling cup:** bolt on `ON_PAYMENT` and the
  [slot machine](001_slot_machine.md)'s ledger idiom to stake credits
  on a high roll.
- **House dice:** `@clone a dice cup` and change `$try`'s bands — a
  loaded cup for the thieves' den that narrates failure as success.

**Engine gaps:** two, precise. (1) `skill_check()`/`contest()` return
bare bools — no softcode function returns the *graded* `CheckResult` of
a full engine check (untrained defaults + condition modifiers + ruleset
crits), so margin narration must re-derive from kernel primitives and
silently loses `check_mods`. A `check_roll()` returning the CheckResult
would close it. (2) `roll()` raises on malformed notation, which kills
the script silently — `roll garbage` gives the player no feedback; a
forgiving variant (or a `valid_roll()` predicate) would let the cup
answer "that is not dice."
