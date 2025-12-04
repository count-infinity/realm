"""
Built-in combat rulesets for REALM.

Available rulesets:
- D20Ruleset: D&D 5e-style (d20 + modifier vs AC)
- GURPSRuleset: GURPS-style (3d6 roll-under skill)
"""

from realm.combat.rulesets.d20 import D20Ruleset
from realm.combat.rulesets.gurps import GURPSRuleset

__all__ = ["D20Ruleset", "GURPSRuleset"]
