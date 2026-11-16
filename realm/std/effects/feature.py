"""
The ``effects`` feature.

Timed effects: damage over time, modifiers, regeneration.
"""

from __future__ import annotations

from realm.features import Feature
from realm.std.effects import softcode
from realm.std.effects.behaviors import (
    DamageOverTimeBehavior,
    ModifierEffectBehavior,
    RegenerationBehavior,
)

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


@feature.on_install
def _offer_effects(world) -> None:
    """``world.services["effects"]``: other features end a character's
    timed effects (``clear(obj)``, as ``respawn`` does) without importing
    this one."""
    from realm.std.effects import service
    world.services["effects"] = service
