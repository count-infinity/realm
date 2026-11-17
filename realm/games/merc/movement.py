"""
Movement costs movement (MUD_PLAN 2.5).

Under Merc a player pays for each step from the ``move`` pool: the
destination room's ``move_cost`` attribute, else the cost of its
``sector:<name>`` tag (ROM's ``movement_loss`` table; the ROM importer
writes these tags), else 1. A player who cannot pay stays put. NPCs and a
fleeing character walk free. Only a declared ``move`` pool is charged (Merc
declares it), so a ``move`` attribute meaning something else in another
system is left alone. A rider's mount pays from its own ``move`` pool.

The gate only asks whether the step can be paid for; the step is paid once
it has happened (``pay_for_step``, an after-traverse hook). As ROM's
``move_char`` checks the guild and the door before it charges, a move that
anything refuses (a locked bar, a closed door, a room's veto) costs nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.movement import resolve_exit_destination
from realm.core.pools import can_spend, declared_pools, settle, spend
from realm.core.world import get_world

if TYPE_CHECKING:
    from realm.core.objects import GameObject

#: ROM ``movement_loss`` by sector, with ``water`` for hand-built rooms.
SECTOR_COST: dict[str, int] = {
    "inside": 1, "city": 2, "field": 2, "forest": 3, "hills": 4,
    "mountain": 6, "water": 4, "water_swim": 4, "water_noswim": 1,
    "underwater": 6, "air": 10, "desert": 6,
}


def move_cost(room: GameObject | None) -> int:
    """What it costs to step into ``room``."""
    if room is None:
        return 1
    cost = room.db.get("move_cost")
    if cost is not None:
        return max(0, int(cost))
    for tag in room.tags:
        if tag.startswith("sector:"):
            return SECTOR_COST.get(tag[len("sector:"):], 1)
    return 1


def _payer(actor: GameObject) -> GameObject | None:
    """Who pays for ``actor``'s step, or None when nobody does: a rider's
    mount (the ``companions`` service says, MUD_PLAN 13.3), else the actor;
    only a player pays, and only from a declared ``move`` pool."""
    if not actor.is_player:
        return None
    companions = get_world().services.get("companions")
    payer = companions.payer(actor) if companions is not None else actor
    return payer if "move" in declared_pools(payer) else None


async def movement_gate(actor: GameObject, exit_obj: GameObject | None,
                        direction: str, *, fleeing: bool) -> str | None:
    """Refuse a step that cannot be paid for ("You are too exhausted.");
    charge nothing yet. A mount with no ``move`` pool carries its rider
    free."""
    payer = None if fleeing else _payer(actor)
    if payer is None:
        return None
    destination = resolve_exit_destination(exit_obj) if exit_obj is not None else None
    if not can_spend(payer, "move", move_cost(destination)):
        return "You are too exhausted." if payer is actor else "Your mount is too exhausted."
    return None


async def pay_for_step(actor: GameObject, origin: GameObject | None,
                       destination: GameObject, exit_obj: GameObject | None,
                       *, fleeing: bool) -> None:
    """``feature.after_traverse``: the step has happened; pay for it."""
    payer = None if fleeing else _payer(actor)
    if payer is None:
        return
    change = spend(payer, "move", move_cost(destination))
    if change is not None:
        await settle(change, source=actor)


__all__ = ["SECTOR_COST", "move_cost", "movement_gate", "pay_for_step"]
