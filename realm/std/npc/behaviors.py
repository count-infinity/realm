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
from realm.core.propagation import Action
from realm.core.world import get_world

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)




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
            # A player's corpse (tag ``player_corpse``) holds their gear
            # until they come back for it: ROM's fido eats NPC corpses only.
            corpse = next((c for c in room.contents
                           if 'corpse' in c.name.lower()
                           and not c.has_tag('player_corpse')), None)
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




__all__ = ["PatrolBehavior", "ScavengerBehavior"]


class GuardBehavior(Behavior):
    """
    Blocks movement for those without permission.

    Parameters:
        guard_tags: tags marking who to block (default ['player'])
        allow_tags: tags marking who passes (default ['guard', 'admin'])
        challenge_message: the block reason shown
    """

    behavior_id = "guard"
    param_spec = {
        'guard_tags': (['player'], 'tags marking who to block'),
        'allow_tags': (['guard', 'admin'], 'tags marking who passes'),
        'allow_disposition': (2, 'disposition at or above which one passes'),
        'challenge_message': ('Halt! You shall not pass!',
                              'the block reason shown'),
    }

    async def on_check(self, obj: GameObject, action: Action) -> None:
        if action.action_type not in (ActionType.ON_ENTER, ActionType.ON_LEAVE):
            return

        mover = action.actor
        if not mover or mover == obj:
            return

        allow_tags = self.get_param('allow_tags', ['guard', 'admin'])
        if any(mover.has_tag(tag) for tag in allow_tags):
            return

        # Friends (and the successfully fast-talked) get waved through.
        social = get_world().services.get("social")
        if social is not None and social.get_disposition(obj, mover) >= int(
                self.get_param('allow_disposition', 2)):
            return

        guard_tags = self.get_param('guard_tags', ['player'])
        if not any(mover.has_tag(tag) for tag in guard_tags):
            return

        challenge = self.get_param('challenge_message', "Halt! You shall not pass!")
        action.block(challenge)


class WanderingBehavior(Behavior):
    """
    Roams through random open exits.

    Parameters:
        wander_chance: probability of moving on each check (default 0.25)
        pause: ticks between wander checks (default 7 ≈ 30s at 4s ticks)
        avoid_tags: destination-room tags never entered (default
            ['no_wander']); wanderers also never leave their zone if
            stay_in_zone is set.
        stay_in_zone: keep to rooms sharing the owner's zone: tag
            (default True).
    """

    behavior_id = "wandering"
    param_spec = {
        'pause': (7, 'world beats between wander attempts'),
        'wander_chance': (0.25, 'probability per attempt that it moves'),
        'avoid_tags': (['no_wander'], 'exit tags never taken'),
        'stay_in_zone': (True, 'keep to rooms sharing a zone tag'),
    }

    @property
    def should_tick(self) -> bool:
        return True

    async def tick(self, obj: GameObject, delta: float) -> None:
        if obj.has_tag('in_combat') or obj.location is None:
            return

        if not self.countdown(obj, 'wander_wait', int(self.get_param('pause', 7)) + 1):
            return

        if random.random() > float(self.get_param('wander_chance', 0.25)):
            return


        avoid = set(self.get_param('avoid_tags', ['no_wander']))
        my_zones = {t for t in obj.location.tags.to_list() if t.startswith('zone:')}
        stay_in_zone = bool(self.get_param('stay_in_zone', True))

        candidates = []
        for exit_obj in obj.location.contents:
            if not exit_obj.is_exit or exit_obj.has_tag('closed'):
                continue
            destination = resolve_exit_destination(exit_obj)
            if destination is None:
                continue
            if any(destination.has_tag(tag) for tag in avoid):
                continue
            if stay_in_zone and my_zones:
                dest_zones = {t for t in destination.tags.to_list()
                              if t.startswith('zone:')}
                if not (my_zones & dest_zones):
                    continue
            candidates.append((exit_obj, destination))

        if not candidates:
            return
        exit_obj, destination = random.choice(candidates)
        await move_through_exit(obj, destination, exit_obj=exit_obj)
