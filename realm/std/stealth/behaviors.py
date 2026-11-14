"""
The ``stealth`` feature's behaviors: watchful observers who spot the hidden.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.action_types import ActionType
from realm.core.behaviors import Behavior
from realm.core.perception import can_see
from realm.core.propagation import Action
from realm.core.world import get_world
from realm.std.rules.checks import contest
from realm.std.stealth.stealth import HIDDEN_TAG, break_stealth

if TYPE_CHECKING:
    from realm.core.objects import GameObject


async def _say(npc: GameObject, text: str) -> None:
    """The NPC speaks, when the world has ``talk`` (``services["talk"]``)."""
    talk = get_world().services.get("talk")
    if talk is not None:
        await talk.npc_say(npc, text)


class WatchfulBehavior(Behavior):
    """
    An observer that challenges arrivals and contests sneaking.

    Params:
        perception (str): skill used to spot sneaks (default "observation").
        challenge (str): line said to visible arrivals (optional).
        spot_msg (str): line said on catching someone sneaking (default
            "Hey! Who's there?").
        alert_on_spot (bool): bump own db.alert_level on a spot (default True).
        hostile (bool): attack spotted sneaks — starts combat (default False).

    When a hidden character enters the room, the watcher contests
    perception vs their stealth; winning breaks the sneak and issues the
    spot line. Visible arrivals just get the challenge line.
    """

    behavior_id = "watchful"
    param_spec = {
        'perception': ('observation', 'skill rolled against a sneaker\'s stealth'),
        'alert_on_spot': (True, 'raise alert_level each time someone is spotted'),
        'spot_msg': ("Hey! Who's there?", 'line said on spotting a sneaker'),
        'hostile': (False, 'attack whoever it spots'),
        'challenge': (None, 'line said to anyone visible who walks in'),
    }

    async def on_react(self, obj: GameObject, action: Action) -> None:
        if action.action_type != ActionType.ON_ENTER:
            return
        actor = action.actor
        if actor is None or actor is obj:
            return
        # Only care about characters arriving where we stand.
        if obj.location is None or action.target is not obj.location:
            return
        if not (actor.is_player or actor.is_npc):
            return

        if actor.has_tag(HIDDEN_TAG):
            perception_skill = self.get_param('perception', 'observation')
            alertness = int(obj.db.get('alert_level') or 0)
            if contest(obj, perception_skill, actor, 'stealth',
                       actor_mod=alertness):
                break_stealth(actor, f"{obj.name} spots you!")
                if self.get_param('alert_on_spot', True):
                    obj.db.alert_level = alertness + 1
                await _say(obj, self.get_param('spot_msg', "Hey! Who's there?"))
                if self.get_param('hostile', False):
                    manager = get_world().services.get("combat")
                    if manager is not None:
                        await manager.initiate(obj, actor)
            return

        challenge = self.get_param('challenge')
        if challenge and can_see(obj, actor):
            await _say(obj, challenge)
