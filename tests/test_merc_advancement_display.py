"""Merc XP economy + system-aware score + equipped-state display.

The bugs these pin (found playing Midgaard, 2026-08-01):

- ``death_award`` was inherited from the ABC as ``points // 10`` — CP
  scaling on an XP system. A level-1 fido (points 100) paid 10 XP against
  a 1000-XP level curve: a hundred dogs per level. Merc now overrides it:
  the victim's ``points`` are the base, bent by level difference.
- ``score`` always showed the GURPS point-buy sheet regardless of the
  active system. It now delegates to ``GameSystem.score_lines``.
- ``inventory`` gave no hint what was wielded or worn.
"""

from __future__ import annotations

import pytest

from realm.commands import CommandDispatcher
from realm.commands.builtin import register_all_commands
from realm.core.objects import GameObject
from realm.gateway.session import Session
from realm.systems import GurpsSystem, MercSystem, set_game_system


def _drain(session) -> str:
    out = []
    while not session._output_queue.empty():
        out.append(session._output_queue.get_nowait())
    return "\n".join(out)


class TestMercDeathAward:

    def setup_method(self):
        self.system = MercSystem()

    def _mob(self, level, points=None):
        mob = GameObject("prey", tags=['npc'])
        mob.db.level = level
        mob.db.points = points if points is not None else level * 100
        return mob

    def _killer(self, level):
        killer = GameObject("Hunter", tags=['player'])
        killer.db.level = level
        return killer

    def test_equal_level_pays_full_points(self):
        # A level-1 fido pays 100 XP, not 10 — ten dogs to level 2, not 100.
        assert self.system.death_award(self._mob(1), self._killer(1)) == 100

    def test_tougher_prey_pays_a_premium(self):
        award = self.system.death_award(self._mob(5), self._killer(1))
        assert award > 500                      # above base: +15%/level up

    def test_grey_prey_pays_a_pittance(self):
        award = self.system.death_award(self._mob(1, points=100),
                                        self._killer(30))
        assert award == max(1, round(100 * 0.05))   # clamped floor

    def test_award_actually_levels(self):
        player = GameObject("Grog", tags=['player'])
        player.db.level = 1
        player.db.xp = 0
        player.db.character_class = 'barbarian'
        player.db.max_hp = 12
        player.db.hp = 12
        self.system.grant_award(player, 1000)
        assert player.db.get('level') == 2
        assert player.db.get('max_hp') > 12     # hit die banked


@pytest.mark.asyncio
class TestSystemAwareScore:

    async def _score(self, system):
        set_game_system(system)
        try:
            dispatcher = CommandDispatcher()
            register_all_commands(dispatcher)
            room = GameObject("Square", tags=['room'])
            player = GameObject("Grog", tags=['player'], location=room)
            player.db.level = 3
            player.db.xp = 250
            player.db.character_class = 'barbarian'
            player.db.hp = 30
            player.db.max_hp = 34
            player.db.thac0 = 18
            player.db.armor_class = 6
            player.db.character_points = 7
            player.db.set('skill_melee', 40)
            club = GameObject("a heavy club", tags=['thing'], location=player)
            club.add_tag('wielded')
            session = Session()
            session.link_player(player)
            await dispatcher.dispatch(session, "score")
            return _drain(session)
        finally:
            set_game_system(None)

    async def test_merc_score_speaks_diku(self):
        out = await self._score(MercSystem())
        assert "level 3 barbarian" in out
        assert "Experience: 250 / 3000" in out   # xp_to_next(3)
        assert "THAC0: 18" in out and "AC: 6" in out
        assert "Wielding: a heavy club" in out
        assert "Character points" not in out     # no GURPS leakage

    async def test_gurps_score_still_point_buy(self):
        out = await self._score(GurpsSystem())
        assert "Character points: 7" in out
        assert "improve <skill>" in out
        assert "THAC0" not in out


@pytest.mark.asyncio
class TestInventoryEquipMarks:

    async def test_wielded_and_worn_are_marked(self):
        dispatcher = CommandDispatcher()
        register_all_commands(dispatcher)
        room = GameObject("Square", tags=['room'])
        player = GameObject("Grog", tags=['player'], location=room)
        sword = GameObject("a short sword", tags=['thing'], location=player)
        sword.add_tag('wielded')
        helm = GameObject("an iron helm", tags=['thing'], location=player)
        helm.add_tag('worn')
        helm.db.slot = 'head'
        GameObject("a rock", tags=['thing'], location=player)  # unequipped
        session = Session()
        session.link_player(player)
        await dispatcher.dispatch(session, "inventory")
        out = _drain(session)
        assert "a short sword (wielded)" in out
        assert "an iron helm (worn on head)" in out
        assert "a rock (" not in out                 # unequipped: no mark
