"""
The ``d20`` feature: D20: d20 plus modifier against AC.

Declares the combat ruleset; it is used only when ``combat`` is installed.
"""

from __future__ import annotations

from realm.combat.rulesets.d20 import D20Ruleset
from realm.features import Feature

feature = Feature('d20', requires=["rules"], doc='D20: d20 plus modifier against AC.')
feature.ruleset('d20', D20Ruleset, aliases=['dnd'])
