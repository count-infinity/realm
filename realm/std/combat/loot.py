"""
What a killer takes from the corpse (MUD_PLAN 11.2): the ``autoloot``,
``autogold`` and ``autosplit`` player settings, ROM's ``PLR_AUTO*`` bits.

An NPC's corpse holds what it carried and its money (``credits``). With
``autoloot`` on, the killer takes all of it at once; with ``autogold``
only the money; with ``autosplit`` too, money taken that way is shared
with the party in the room (``split``). Off, the corpse keeps everything
for ``get all from corpse``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.options import get_option
from realm.core.world import get_world
from realm.std.items.inventory import take_all, take_money

if TYPE_CHECKING:
    from realm.core.objects import GameObject

LOOT_OPTIONS = (
    ("autoloot", "Take everything from the corpses of what you kill."),
    ("autogold", "Take the money from the corpses of what you kill."),
    ("autosplit", "Share money you take from a kill with your party here."),
)


def offer_loot_options(world) -> None:
    """``on_install``: the three settings, when the world has ``config``."""
    options = world.services.get("options")
    if options is not None:
        for name, doc in LOOT_OPTIONS:
            options.toggle(name, doc, False)


async def loot_corpse(killer: GameObject, corpse: GameObject) -> None:
    """Apply ``killer``'s loot settings to the corpse of what they killed."""
    if get_option(killer, "autoloot"):
        _items, money = await take_all(killer, corpse)
    elif get_option(killer, "autogold"):
        money = take_money(killer, corpse)
    else:
        return
    economy = get_world().services.get("economy")
    if money > 1 and economy is not None and get_option(killer, "autosplit"):
        economy.split_money(killer, money)       # alone: "keep it all", unsaid


__all__ = ["LOOT_OPTIONS", "offer_loot_options", "loot_corpse"]
