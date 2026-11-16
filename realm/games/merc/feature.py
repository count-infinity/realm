"""
The ``merc`` feature: Merc/Diku: d20 against THAC0 minus AC.

Declares the combat ruleset (used only when ``combat`` is installed) and
charges movement points for walking (``realm.games.merc.movement``).
"""

from __future__ import annotations

from realm.features import Feature
from realm.games.merc.movement import movement_gate
from realm.games.merc.ruleset import MercRuleset

feature = Feature('merc', requires=["rules", "combat"],
                  doc='Merc/Diku: d20 against THAC0 minus AC.')
feature.ruleset('merc', MercRuleset, aliases=['diku'])
feature.setting("LEVEL_CAP", 50,
                "The highest level a character reaches under the Merc rules; experience "
                "past it still counts but levels no further.")
feature.traversal_gate(movement_gate, reason="exhausted", attrs=["move_cost"])
