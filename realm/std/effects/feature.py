"""
The ``effects`` feature.

Timed effects: damage over time, modifiers, regeneration.
"""

from __future__ import annotations

from realm.behaviors.effects import (
    DamageOverTimeBehavior,
    ModifierEffectBehavior,
    RegenerationBehavior,
)
from realm.features import Feature
from realm.std.effects import softcode

feature = Feature(
    'effects',
    requires=['rules'],
    doc='Timed effects: damage over time, modifiers, regeneration.',
)

for _cls in (DamageOverTimeBehavior, ModifierEffectBehavior, RegenerationBehavior):
    feature.behavior(_cls)


# --- softcode ------------------------------------------------------------------

feature.softfn(softcode.apply_effect, group='Combat & effects', harm=True)
feature.softfn(softcode.remove_effect, group='Combat & effects', harm=True)
