"""
The ``sight`` feature.

Darkness and light, nightvision, invisibility, and the ``glowing``,
``magic`` and ``invisible`` markers (``realm/std/sight/sight.py``).
"""

from __future__ import annotations

from realm.features import Feature
from realm.std.sight import sight

feature = Feature(
    'sight',
    doc='Darkness and light, nightvision, invisibility; the glowing, magic and '
        'invisible markers.',
)

feature.sight_rule(sight.invisibility)
feature.sight_rule(sight.darkness)
feature.marker(sight.glowing_marker)
feature.marker(sight.magic_marker)
feature.marker(sight.invisible_marker)


@feature.on_install
def _offer_sight(world) -> None:
    """Other features ask ``world.services["sight"]`` whether a viewer can
    see inside a room (``can_see_room``) or a room is lit (``room_is_lit``),
    and treat its absence as light."""
    world.services["sight"] = sight
