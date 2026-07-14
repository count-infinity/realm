"""
NPC behaviors for living worlds: guards that watch, guards that walk.

Design rules (REALM architecture):
- Behaviors are stateless logic; ALL state lives in ``owner.db.*`` so it
  persists with the object and is inspectable via ``@examine``.
- Behaviors act back on the world through propagated actions (their
  speech is real speech — listen scripts, perception masking, and
  other behaviors all apply).
- Everything is parameterized via behavior params, so builders attach
  and tune without code.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from realm.core.behaviors import Behavior, BehaviorRegistry
from realm.core.checks import contest
from realm.core.perception import break_stealth, can_see
from realm.core.propagation import Action, propagate

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)


async def _npc_say(npc: GameObject, message: str) -> None:
    """An NPC speaks through the propagation engine (real speech)."""
    if npc.location is None:
        return
    from realm.core.verbs import speech_action
    action = speech_action(npc, message)
    action.tags.add("npc")
    await propagate(action)


@BehaviorRegistry.register
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

    async def on_react(self, obj: GameObject, action: Action) -> None:
        if action.action_type != "event:on_enter":
            return
        actor = action.actor
        if actor is None or actor is obj:
            return
        # Only care about characters arriving where we stand.
        if obj.location is None or action.target is not obj.location:
            return
        if not (actor.has_tag('player') or actor.has_tag('npc')):
            return

        if actor.has_tag('hidden'):
            perception_skill = self.get_param('perception', 'observation')
            alertness = int(obj.db.get('alert_level') or 0)
            if contest(obj, perception_skill, actor, 'stealth',
                       actor_mod=alertness):
                break_stealth(actor, f"{obj.name} spots you!")
                if self.get_param('alert_on_spot', True):
                    obj.db.alert_level = alertness + 1
                await _npc_say(obj, self.get_param('spot_msg', "Hey! Who's there?"))
                if self.get_param('hostile', False):
                    from realm.combat.manager import get_combat_manager
                    manager = get_combat_manager()
                    if manager is not None:
                        await manager.initiate(obj, actor)
            return

        challenge = self.get_param('challenge')
        if challenge and can_see(obj, actor):
            await _npc_say(obj, challenge)


@BehaviorRegistry.register
class PatrolBehavior(Behavior):
    """
    Walk a route of exit names, one step every few ticks.

    Params:
        route (list[str]): exit names to take, in order, looping —
            e.g. ["north", "north", "south", "south"]. Topology-safe:
            the patrol takes real exits through the movement gate, so
            closed doors and locks stop it like anyone else.
        pause (int): ticks to wait between steps (default 3).

    State in owner.db: patrol_index (next step), patrol_wait (countdown).
    """

    behavior_id = "patrol"

    @property
    def should_tick(self) -> bool:
        return True

    async def tick(self, obj: GameObject, delta: float) -> None:
        route: list[str] = self.get_param('route') or []
        if not route or obj.location is None:
            return

        wait = int(obj.db.get('patrol_wait') or 0)
        if wait > 0:
            obj.db.patrol_wait = wait - 1
            return
        obj.db.patrol_wait = int(self.get_param('pause', 3))

        index = int(obj.db.get('patrol_index') or 0) % len(route)
        direction = route[index]

        exit_obj = None
        for candidate in obj.location.contents:
            if candidate.has_tag('exit') and candidate.name.lower() == direction.lower():
                exit_obj = candidate
                break
        if exit_obj is None:
            # Lost (moved rooms, world changed): try the next step next time.
            obj.db.patrol_index = index + 1
            return

        from realm.core.movement import (
            has_dest_resolver,
            move_through_exit,
            resolve_exit_destination,
        )
        destination = resolve_exit_destination(exit_obj)
        if destination is None and not has_dest_resolver(exit_obj):
            obj.db.patrol_index = index + 1
            return

        # A deferred exit (wilderness cell edge) resolves inside
        # move_through_exit; a mob is refused where no cell exists yet.
        moved = await move_through_exit(obj, destination, exit_obj=exit_obj)
        if moved:
            obj.db.patrol_index = index + 1
        # If blocked (closed door, lock), stay and retry after the pause.


__all__ = ["WatchfulBehavior", "PatrolBehavior"]
