"""
The ``d20`` feature: D20: d20 plus modifier against AC.

Declares the combat ruleset; it is used only when ``combat`` is installed.
"""

from __future__ import annotations

from realm.features import Feature
from realm.games.d20.ruleset import D20Ruleset

feature = Feature('d20', requires=["rules", "combat"], doc='D20: d20 plus modifier against AC.')
feature.ruleset('d20', D20Ruleset, aliases=['dnd'])
