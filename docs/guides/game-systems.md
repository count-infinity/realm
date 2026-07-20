# Game Systems (GURPS / D20 / your own)

A **GameSystem** is the swappable rules package. It bundles every rules
decision in one place — chargen, skills, how skill checks resolve,
character advancement, the combat ruleset, and the currency name — so
the engine never asks "is this GURPS?".

## Choosing one

`config.py` sets `GAME_SYSTEM` **before the first character is created**.
It's a **dotted import path** to a GameSystem subclass — one greppable
value a developer can follow straight to the source:

```python
GAME_SYSTEM = "rules.GameRules"            # your own system — the scaffolded default
GAME_SYSTEM = "realm.systems.GurpsSystem"  # a built-in, unmodified (or ".D20System")
```

`realm init` writes the first form: the path points at your `GameRules`
class in `rules.py`, so what it subclasses is the *only* place the rules
are decided — there's no id string to fall out of sync with it.

Two systems ship in-box:

| | **GURPS** (`gurps`) | **D20** (`d20`) |
|---|---|---|
| Skill checks | 3d6 roll-UNDER effective skill | d20 + skill bonus vs DC 15 (roll-HIGH) |
| Chargen | pick a template + bonus skill | pick a class |
| Combat | 3d6 vs skill; AoA/AoD/Feint | d20 + ability mod + proficiency vs AC |
| Advancement | flat 4 CP / skill level | escalating cost |
| Currency | credits | gold |
| Derived | HP from ST, dodge from DX/HT | HP from HT, AC 10 + DEX mod |

The whole package swaps: under `d20`, `stealth` and `persuade` roll a
d20 too — not just combat. (This wiring was completed 2026-07-07;
before that, non-combat checks ignored the system.)

## Changing systems after launch — don't

`GAME_SYSTEM` is a **boot-time deployment choice, not a live toggle.**
Characters are stamped with the system they were created under
(`db.game_system`). If you change the config and restart:

- Existing characters keep their attributes, but those attributes were
  authored under the old rules (a GURPS soldier's ST 12 means nothing
  to D20's AC-based combat). On login they get a warning:
  *"[!] Rook was created under 'gurps' but this server now runs 'd20'."*
- There is **no migration** — sheets are not recomputed. Pick your
  system before opening to players.

Mid-character-generation swaps are guarded (the flow won't crash) but
will hand a half-made character the new system's prompts. Again: choose
once.

## Writing your own

If you want rules unlike GURPS or D20, subclass `GameSystem` directly
instead of a built-in. Put it in `rules.py` (replacing the scaffolded
`GameRules`) and point `config.py` at it — same as any game system:

```python
# rules.py
from realm.systems.base import GameSystem, ChoiceStep

class SavageSystem(GameSystem):
    system_id = "savage"
    ruleset_name = "d20"          # reuse a combat ruleset, or ship your own
    currency_name = "scrip"

    def skill_defaults(self):
        return {"shooting": ("dexterity", -4), "notice": ("intelligence", -5)}

    def resolve_check(self, obj, skill, modifier):
        # your dice here — return a CheckResult
        from realm.core.checks import default_resolver
        return default_resolver(obj, skill, modifier)

    def improve_cost(self, skill, current_level):
        return 2

    def chargen_steps(self):
        return [ChoiceStep("archetype", "Pick your archetype:",
                           {"gunslinger": "fast draw", "medic": "field surgery"},
                           self._apply)]
```

```python
# config.py
GAME_SYSTEM = "rules.SavageSystem"
```

The `resolve_check`, `improve_cost`, `death_award`, and `chargen_steps`
methods are the seams; everything else inherits sensible defaults. Ship a
custom combat ruleset by registering it with `RulesetRegistry` and
pointing `ruleset_name` at it.

For a full worked build — a percentile (d100) system with range-based combat
and condition-scaled armor, both the `GameSystem` *and* the combat `Ruleset`
end to end — follow [Creating Your Own System](creating-your-own-system.md).
