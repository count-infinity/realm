"""
The ``companions`` feature's behaviors: the ward every companion carries,
and the ``charmed`` effect.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.action_tags import HOSTILE
from realm.core.behaviors import Behavior
from realm.core.world import get_world
from realm.std.effects.behaviors import TimedEffectBehavior

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.core.propagation import Action


class CompanionBehavior(Behavior):
    """
    The ward a companion carries while it has a master: it never acts
    hostile toward that master (CoffeeMud's "You like them too much.").
    ``set_master`` attaches it and releasing removes it.
    """

    behavior_id = "companion"

    async def on_check(self, obj: GameObject, action: Action) -> None:
        if action.actor is not obj or HOSTILE not in action.tags:
            return
        target = action.target
        if target is not None and target.id == obj.db.get("master"):
            from realm.std.companions.companions import the
            action.block(f"You like {the(target, capital=False)} too much.")


class CharmedBehavior(TimedEffectBehavior):
    """
    A charm (ROM's charm person, CoffeeMud's Spell_Charm): while it lasts
    its bearer is the caster's companion. When it wears off the bond is
    released ("<name>'s free will returns.") and, with ``turns_hostile``,
    the creature attacks its former master if it is in the room.

    Apply it through an ability's ``charm`` effect (or the ``companions``
    service's ``charm``), which checks the limit and bonds first.
    """

    behavior_id = "charmed"
    param_spec = {
        'kind': ('charmed', 'the condition name, mirrored as a tag'),
        'turns_hostile': (False, 'attack the former master when it wears off'),
    }

    @property
    def kind(self) -> str:
        return "charmed"

    def detach(self, obj: GameObject) -> None:
        """Removed early (``remove_effect``, a respawn's cleanup): the bond
        goes with it."""
        from realm.std.companions.companions import unbind
        source = self.get_param('source_id')
        if source and obj.db.get("master") == source:
            unbind(obj)
        super().detach(obj)

    async def _expire(self, obj: GameObject) -> None:
        from realm.std.companions.companions import master_of, set_master, the
        former = master_of(obj)
        if former is not None and former.id == self.get_param('source_id'):
            await set_master(obj, None, reason="charm_ended")
        await super()._expire(obj)
        if obj.location is not None:
            obj.location.msg_contents(f"{the(obj)}'s free will returns.")
        if (self.get_param('turns_hostile') and former is not None
                and former.location is obj.location and obj.location is not None):
            combat = get_world().services.get("combat")
            if combat is not None:
                await combat.initiate(obj, former)


__all__ = ["CharmedBehavior", "CompanionBehavior"]
