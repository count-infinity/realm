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
call it by name from any rule or script:

```python
# mygame/bindings.py
from realm.scripting import softcode_function

@softcode_function
def exploding_pool(pool, tn):
    ...            # arbitrary native Python — fast, complex, whatever

# config.py:  import bindings   → softcode/OLC can now call exploding_pool(...)
```

```python
    resolve_rule = "exploding_pool(attr('pool'), 4)"
```

**The trust boundary (important):** a binding is unsandboxed native code,
so registering one is a **deploy-time act by the operator** — the game's
`config.py` imports the module. It is *never* something a builder types at
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
