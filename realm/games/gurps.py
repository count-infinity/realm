"""
The ``gurps`` feature: GURPS 4e: 3d6 roll-under combat.

Declares the combat ruleset; it is used only when ``combat`` is installed.
"""

from __future__ import annotations

from realm.combat.rulesets.gurps import GURPSRuleset
from realm.features import Feature

feature = Feature('gurps', requires=["rules"], doc='GURPS 4e: 3d6 roll-under combat.')
feature.ruleset('gurps', GURPSRuleset, aliases=['3d6'])
