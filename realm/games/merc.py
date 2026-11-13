"""
The ``merc`` feature: Merc/Diku: d20 against THAC0 minus AC.

Declares the combat ruleset; it is used only when ``combat`` is installed.
"""

from __future__ import annotations

from realm.combat.rulesets.merc import MercRuleset
from realm.features import Feature

feature = Feature('merc', requires=["rules"], doc='Merc/Diku: d20 against THAC0 minus AC.')
feature.ruleset('merc', MercRuleset, aliases=['diku'])
