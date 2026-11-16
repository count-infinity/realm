"""
Player corpses (MUD_PLAN 2.4).

Under ``PLAYER_DEATH = "respawn"`` a defeated player leaves ``corpse of
<name>`` where they fell, holding everything they carried except what is
``soulbound``. For ``CORPSE_LOCK_SECONDS`` only the player (and whoever has
``LOCK_BYPASS``) may take from it: the ``corpse_claim`` behavior vetoes
anyone else's ``get``. The corpse is tagged ``player_corpse``, which
scavengers leave alone, and rots with the ``decay`` behavior when the
world has one.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from realm.core.behaviors import Behavior, BehaviorRegistry
from realm.core.objects import GameObject
from realm.std.items.actions import ItemAction

if TYPE_CHECKING:
    from realm.core.propagation import Action

SOULBOUND = "soulbound"
PLAYER_CORPSE = "player_corpse"


class CorpseClaimBehavior(Behavior):
    """Keep others' hands off a fresh player corpse until ``until``."""

    behavior_id = "corpse_claim"
    param_spec = {
        'owner_id': (None, 'the id of the player whose corpse this is'),
        'until': (0, 'epoch seconds after which anyone may loot it'),
    }

    async def on_check(self, obj: GameObject, action: Action) -> None:
        if action.blocked or action.action_type != ItemAction.ON_GET:
            return
        target, actor = action.target, action.actor
        if actor is None or target is None:
            return
        if target is not obj and target.location is not obj:
            return
        if actor.id == self.get_param('owner_id'):
            return
        if time.time() >= float(self.get_param('until') or 0):
            return
        from realm.permissions.entitlements import LOCK_BYPASS
        from realm.permissions.roles import has_entitlement
        if has_entitlement(actor, LOCK_BYPASS):
            return
        owner = obj.owner.name if obj.owner is not None else "someone else"
        action.block(f"That corpse belongs to {owner}.")


async def leave_player_corpse(player: GameObject, room: GameObject, *,
                              lock_seconds: float, store) -> GameObject:
    """Make ``corpse of <player>`` in ``room`` and move into it everything
    the player carries that is not soulbound."""
    corpse = GameObject(name=f"corpse of {player.name}",
                        tags=['thing', 'no_group', 'container', PLAYER_CORPSE])
    corpse.db.article = "the"
    corpse.db.description = f"The lifeless body of {player.name}."
    corpse.owner = player
    for item in list(player.contents):
        if not item.has_tag(SOULBOUND):
            item.location = corpse
    corpse.location = room
    if lock_seconds and float(lock_seconds) > 0:
        corpse.add_behavior(CorpseClaimBehavior(owner_id=player.id,
                                                until=time.time() + float(lock_seconds)))
    if BehaviorRegistry.get("decay") is not None:
        corpse.add_behavior(BehaviorRegistry.create("decay", ticks=150))
    if store is not None:
        await store.save(corpse)
    return corpse


__all__ = ["CorpseClaimBehavior", "leave_player_corpse", "SOULBOUND", "PLAYER_CORPSE"]
