"""
Ops on connections: boot.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.ops import Invalid, NotAllowed, OpResult, Refused

if TYPE_CHECKING:
    from realm.core.objects import GameObject


def check_boot(actor: GameObject | None, player: GameObject, sessions) -> None:
    from realm.permissions import has_entitlement
    from realm.permissions.entitlements import MODERATE
    if actor is not None and not has_entitlement(actor, MODERATE):
        raise NotAllowed("Disconnecting players needs moderator authority (MODERATE).")
    if not player.is_player:
        raise Invalid(f"{player.name} is not a player.")
    if actor is not None and player is actor:
        raise Refused("You can't boot yourself — use quit.")
    if sessions is None or sessions.get_session_by_player(player) is None:
        raise Invalid(f"{player.name} is not connected.")


async def boot(actor: GameObject | None, player: GameObject, sessions) -> OpResult:
    """Disconnect ``player``'s session; the character stays."""
    check_boot(actor, player, sessions)
    session = sessions.get_session_by_player(player)
    await session.send("You have been disconnected by an administrator.")
    await sessions.destroy_session(session)
    return OpResult(value=True)
