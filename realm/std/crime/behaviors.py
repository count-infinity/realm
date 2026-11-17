"""
The ``crime`` feature's behaviors: the wanted flag's timer, peacekeepers who
arrest the wanted, and thieves.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from realm.core.behaviors import Behavior
from realm.core.markup import capitalize
from realm.core.movement import move_through_exit, resolve_exit_destination
from realm.core.world import get_world
from realm.permissions.roles import Role, get_role
from realm.std.combat.manager import is_combat_capable
from realm.std.crime.crime import WANTED_PREFIX, is_wanted, wanted_heat
from realm.std.economy.credits import get_credits, transfer_credits
from realm.std.effects.behaviors import TimedEffectBehavior
from realm.std.rules.checks import contest

if TYPE_CHECKING:
    from realm.core.objects import GameObject


async def _say(npc: GameObject, text: str) -> None:
    """The NPC speaks, when the world has ``talk`` (``services["talk"]``)."""
    talk = get_world().services.get("talk")
    if talk is not None:
        await talk.npc_say(npc, text)


class PeacekeeperBehavior(Behavior):
    """
    Attacks WANTED criminals in its room (ROM spec_guard, done right).

    Unlike the `guard` behavior — which blocks *movement* — a peacekeeper
    enforces the law: each tick it scans its room for players carrying a
    ``wanted:*`` tag (see systems/crime.py) and engages the highest-heat one.

    With no criminal in sight, ``protect`` says whom else it takes on:

    - ``"evil"`` (ROM ``spec_guard``): the most evil character (the lowest
      ``alignment``, below 300) in a fight with someone other than itself.
    - ``"fights"`` (ROM ``spec_patrolman``): it breaks up any fight, going
      for the stronger (higher-level) side.

    The importer maps ``spec_guard`` (``protect="evil"``), ``spec_patrolman``
    (``"fights"``) and ``spec_executioner`` (criminals only) to this.

    Params:
        yell (str): line shouted when it moves to arrest (optional).
        protect (str): '' (criminals only), 'evil' or 'fights'.
    """

    behavior_id = "peacekeeper"
    param_spec = {
        'yell': ("HALT! You are under arrest!",
                 'line shouted when it engages a criminal'),
        'protect': ('', "whom else it attacks: '' none, 'evil' the most evil "
                        "fighter (spec_guard), 'fights' any fight (spec_patrolman)"),
    }

    #: ROM spec_guard's ``max_evil``: only a fighter below it is a target.
    EVIL_BELOW = 300

    @property
    def should_tick(self) -> bool:
        return True

    async def tick(self, obj: GameObject, delta: float) -> None:
        if obj.location is None or obj.has_tag('in_combat'):
            return
        manager = get_world().services.get("combat")
        if manager is None:
            return
        criminals = [c for c in obj.location.contents
                     if c.is_player and is_wanted(c)
                     and is_combat_capable(c)]
        if criminals:
            target = max(criminals, key=wanted_heat)
            yell = self.get_param('yell')
            if yell:
                await _say(obj, str(yell))
            await manager.initiate(obj, target)
            return
        protect = str(self.get_param('protect') or '')
        if protect:
            await self._intervene(obj, manager, protect)

    async def _intervene(self, obj: GameObject, manager, protect: str) -> None:
        """Take a side in a fight in the room (``protect``)."""
        fighters = [c for c in obj.location.contents
                    if c is not obj and c.has_tag('in_combat') and is_combat_capable(c)
                    and not any(b.behavior_id == self.behavior_id
                                for b in c.get_behaviors())]
        target = None
        if protect == 'evil':
            evil = [c for c in fighters if _alignment(c) < self.EVIL_BELOW
                    and manager.target_of(c) is not obj]
            if evil:
                target = min(evil, key=_alignment)
                line = "PROTECT THE INNOCENT!!  BANZAI!!"
        elif protect == 'fights' and fighters:
            first = random.choice(fighters)
            other = manager.target_of(first)
            target = first if other is None or _level(first) >= _level(other) else other
            line = "All roit! All roit! Break it up!"
        if target is None:
            return
        await _say(obj, line)
        await manager.initiate(obj, target)


def _alignment(obj: GameObject) -> int:
    return int(obj.db.get('alignment') or 0)


def _level(obj: GameObject) -> int:
    return int(obj.db.get('level') or 1)


class WantedBehavior(TimedEffectBehavior):
    """
    A criminal's ticking wanted status (see systems/crime.py). No pulse — it
    just counts down; on expiry the sentence is served, so it strips the
    ``wanted:*`` tags and heat. Guards read the tags while it lasts.
    """

    behavior_id = "wanted"
    param_spec = {
        'duration': (100, 'world beats the wanted status lasts'),
    }

    @property
    def kind(self) -> str:
        return "wanted"

    async def _expire(self, obj: GameObject) -> None:

        for tag in list(obj.tags.to_list()):
            if tag.startswith(WANTED_PREFIX):
                obj.remove_tag(tag)
        obj.db.delete("wanted_heat")
        obj.msg("Your name is clean once more.")
        await super()._expire(obj)


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
            mark.msg(capitalize(f"{obj.name} tries to pick your pocket!"))
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
