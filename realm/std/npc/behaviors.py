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
import random
from typing import TYPE_CHECKING

from realm.core.action_types import ActionType
from realm.core.behaviors import Behavior
from realm.core.movement import has_dest_resolver, move_through_exit, resolve_exit_destination
from realm.core.perception import can_see
from realm.core.propagation import Action, propagate
from realm.core.world import get_world
from realm.permissions.roles import Role, get_role
from realm.std.economy.money import get_credits, transfer_credits
from realm.std.rules.checks import contest
from realm.std.stealth.hiding import HIDDEN_TAG, break_stealth
from realm.std.talk.verbs import speech_action

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)


async def _npc_say(npc: GameObject, message: str) -> None:
    """An NPC speaks through the propagation engine (real speech)."""
    if npc.location is None:
        return
    action = speech_action(npc, message)
    action.tags.add("npc")
    await propagate(action)


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
                await _npc_say(obj, self.get_param('spot_msg', "Hey! Who's there?"))
                if self.get_param('hostile', False):
                    manager = get_world().services.get("combat")
                    if manager is not None:
                        await manager.initiate(obj, actor)
            return

        challenge = self.get_param('challenge')
        if challenge and can_see(obj, actor):
            await _npc_say(obj, challenge)


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
    param_spec = {
        'route': ([], 'exit names walked in order, wrapping'),
        'pause': (3, 'world beats between steps'),
    }

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
            if candidate.is_exit and candidate.name.lower() == direction.lower():
                exit_obj = candidate
                break
        if exit_obj is None:
            # Lost (moved rooms, world changed): try the next step next time.
            obj.db.patrol_index = index + 1
            return

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


# NOTE: wandering and aggression already ship as `wandering` and
# `aggressive` in realm/std/combat/behaviors.py (zone-bounded roaming;
# disposition- and perception-aware attack-on-sight). The ROM importer maps
# ACT_STAY_AREA/ACT_AGGRESSIVE onto THOSE — this module only adds the
# scavenger, which had no equivalent.


class ScavengerBehavior(Behavior):
    """
    Eat corpses and pick up litter (ROM ACT_SCAVENGER / spec_fido).

    The beastly fido's day job: devour any corpse in the room (and whatever
    it held), else pocket a loose object. The importer maps it from the
    ACT_SCAVENGER flag and from ``spec_fido``/``spec_janitor``.

    Params:
        eat_corpses (bool): consume corpses in the room (default True).
        pick_up (bool): pocket a loose object otherwise (default True).
        chance (float): probability per tick of acting (default 0.5).
    """

    behavior_id = "scavenger"
    param_spec = {
        'eat_corpses': (True, 'devour corpses found in the room'),
        'pick_up': (True, 'pocket a loose object otherwise'),
        'chance': (0.5, 'probability per tick of scavenging'),
    }

    @property
    def should_tick(self) -> bool:
        return True

    async def tick(self, obj: GameObject, delta: float) -> None:
        if obj.location is None or obj.has_tag('in_combat'):
            return
        if random.random() > float(self.get_param('chance', 0.5)):
            return
        room = obj.location
        persistence = get_world().store

        if self.get_param('eat_corpses', True):
            corpse = next((c for c in room.contents
                           if 'corpse' in c.name.lower()), None)
            if corpse is not None:
                room.msg_contents(f"{obj.name} noses into {corpse.name} and "
                                  "devours it, bones and all.", exclude=[])
                for item in list(corpse.contents):
                    item.location = None
                    if persistence is not None:
                        await persistence.delete(item)
                corpse.location = None
                if persistence is not None:
                    await persistence.delete(corpse)
                return

        if self.get_param('pick_up', True):
            loot = next((c for c in room.contents
                         if c.has_tag('thing') and not c.is_exit
                         and not c.has_tag('fixed') and c is not obj
                         and 'corpse' not in c.name.lower()), None)
            if loot is not None:
                loot.location = obj
                room.msg_contents(f"{obj.name} snatches up {loot.name}.",
                                  exclude=[obj])


class StealBehavior(Behavior):
    """
    Pickpockets a little coin from a mortal in the room (ROM spec_thief).

    A quick stealth-vs-perception contest: win and a bit of gold vanishes
    unnoticed (and the thief may slip away); lose and the room hears the
    fumble. The importer maps it from ``spec_thief``.

    Params:
        skill (str): the thief's skill, contested against the mark's
            observation (default 'stealth').
        chance (float): probability per tick of trying (default 0.25).
        max_take (int): most coin lifted in one grab (default 50).
        flee (bool): slip out a random exit after a success (default True).
    """

    behavior_id = "steal"
    param_spec = {
        'skill': ('stealth', "the thief's skill vs the mark's observation"),
        'chance': (0.25, 'probability per tick of attempting a lift'),
        'max_take': (50, 'most currency lifted in one grab'),
        'flee': (True, 'slip out a random exit after a success'),
    }

    @property
    def should_tick(self) -> bool:
        return True

    async def tick(self, obj: GameObject, delta: float) -> None:
        if obj.location is None or obj.has_tag('in_combat'):
            return
        if random.random() > float(self.get_param('chance', 0.25)):
            return

        marks = [c for c in obj.location.contents
                 if c.is_player and get_role(c) <= Role.PLAYER
                 and get_credits(c) > 0]
        if not marks:
            return
        mark = random.choice(marks)
        skill = str(self.get_param('skill', 'stealth'))
        if contest(obj, skill, mark, 'observation'):
            take = min(int(self.get_param('max_take', 50)), get_credits(mark))
            take = random.randint(1, max(1, take))
            transfer_credits(mark, obj, take)
            if self.get_param('flee', True):
                await self._slip_away(obj)
        else:
            mark.msg(f"{obj.name} tries to pick your pocket!")
            obj.location.msg_contents(
                f"{obj.name} fumbles at {mark.name}'s purse!", exclude=[mark])

    async def _slip_away(self, obj: GameObject) -> None:
        exits = [c for c in obj.location.contents if c.is_exit
                 and not c.has_tag('closed')]
        random.shuffle(exits)
        for exit_obj in exits:
            destination = resolve_exit_destination(exit_obj)
            if destination is not None:
                await move_through_exit(obj, destination, exit_obj=exit_obj)
                return


__all__ = ["WatchfulBehavior", "PatrolBehavior", "ScavengerBehavior",
           "StealBehavior"]
