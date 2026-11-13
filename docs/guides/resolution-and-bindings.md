# How-To: Define Resolution & Add Native Bindings

A game system's **resolution rule** — how a check succeeds or fails — is
not hardcoded. It's a one-line expression over neutral **dice
primitives**, so you can express GURPS, D20, Shadowrun, PbtA, Blades, or
FATE as *data*. And when softcode isn't enough, a `@softcode_function`
binding drops to native Python. Background:
[the rules kernel](../design/rules-kernel.md).

## The primitives

`realm/core/dice.py` provides genre-neutral pieces, all available in
softcode. They take numbers, never objects — so a ship and a person use
the identical machinery.

| primitive | does |
|---|---|
| `roll("3d6")` | roll a dice expression → total. Supports `NdS`, Fudge `NdF`, explode `!`, keep `khK`/`klK`, `+K`/`-K` |
| `margin_under(rolled, target)` | roll-under (GURPS, CoC) — graded by margin |
| `margin_over(rolled, target)` | roll-over (D20) |
| `net_successes(pool, tn)` | dice-pool success-counting (Shadowrun, WoD) |
| `highest(pool)` | highest-die tiers (Blades): 6 / 4-5 / 1-3 |
| `band(value, 7, 10)` | tiered outcome (PbtA): miss / 7-9 / 10+ |

Each returns a **graded** `CheckResult` — `.success` plus `.margin` (the
degree: margin of success, net hits, or tier). Never a bare bool.

## A game system as a rule

Set `resolve_rule` on your `GameSystem` (in `rules.py`) — an expression in
which `skill(name=…)` is the actor's skill level, `attr(name)` a raw
attribute, and `mod` the folded modifier:

```python
class MyRules(GameSystem):
    system_id = "mygame"
    resolve_rule = "margin_under(roll('3d6'), skill() + mod)"   # GURPS
    # or:  "net_successes(attr('pool'), 4)"                      # a pool system
    # or:  "band(roll('2d6') + attr('cool'), 7, 10)"            # PbtA
```

That's the whole ruleset's resolution — editable, no Python resolver. It's
also **entity-agnostic**: a rule using `attr('gunnery')` resolves a
starship's attack through the same path as a character's, because it binds
by name over whatever data the entity carries — no `hp`/`melee`
assumptions.

## When softcode isn't enough: a native binding

For speed or complexity beyond softcode, register a native function and
call it by name from softcode:

```python
# mygame/game.py — the game's feature, listed in config.py's FEATURES
from realm.features import Feature

feature = Feature("mygame")

@feature.function(group="Dice & skill checks", readonly=True)
def exploding_pool(pool, tn):
    ...            # arbitrary native Python — fast, complex, whatever
```

A function declared on a feature exists only while that feature is in
`FEATURES`. (A module that calls `realm.scripting.softcode_function` at
import time also works; such a function is always visible, like a built-in.)

```python
    resolve_rule = "exploding_pool(attr('pool'), 4)"
```

A native function joins the same registry as the built-in functions, so
its flags decide where it is visible:

| Flag | Meaning | Visible in |
|---|---|---|
| *(none)* | may change the world | scripts (`$`-commands, `^`-listens, `ON_<EVENT>`, `on_tick`, `@eval`) and inline `[[...]]` blocks |
| `readonly=True` | only reads, rolls or formats | everywhere: scripts, inline blocks, `on_check` wards, locks, `@detail` conditions and resolution rules |
| `harm=True` | can hurt a target the executor need not control, or mint money | scripts and inline blocks, and only when the script's owner chain holds the HARM entitlement (builders do; mortal players do not) |

Mark a function `readonly` only when it truly changes nothing: a lock or a
ward runs on the decision path, where a side effect would fire even when
the action is refused. `group` is its section in the
[softcode reference](../reference/softcode.md) (default `"Game"`).

A name can be registered once. Declaring a name that is already taken
(including a built-in such as `controls`) raises `FeatureError` naming both
owners; pass `replace=True` to override it on purpose. Inside a `resolve_rule`, the
rule's own names (`skill`, `attr`, `mod`, `skill_name`) win over a
function with the same name.

**The trust boundary (important):** a binding is unsandboxed native code,
so registering one is a **deploy-time act by the operator** — the game's
`config.py` lists the feature that declares it. It is *never* something a builder types at
an in-game prompt. Sandboxed softcode **composes** bindings; it cannot
register them. Operators extend the vocabulary; builders compose it. This
is also the performance escape hatch — a rule that's too slow in softcode
simply *becomes* a binding.

## Testing it

Use the [Simulator](../development/testing.md) — pass your system and run
real checks:

```python
from realm.testing import Simulator
from realm.core.checks import check

sim = Simulator(game_system="mygame.rules.MyRules")
hacker = sim.obj("Hacker", pool=10)
assert check(hacker, "intrusion").success in (True, False)   # graded result
```
