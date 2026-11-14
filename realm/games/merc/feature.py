"""
The ``merc`` feature: Merc/Diku: d20 against THAC0 minus AC.

Declares the combat ruleset; it is used only when ``combat`` is installed.
"""

from __future__ import annotations

from realm.features import Feature
from realm.games.merc.ruleset import MercRuleset

feature = Feature('merc', requires=["rules", "combat"],
                  doc='Merc/Diku: d20 against THAC0 minus AC.')
feature.ruleset('merc', MercRuleset, aliases=['diku'])
