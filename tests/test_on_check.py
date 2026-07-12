"""
The on_check hook: data-driven interception in the propagation CHECK pass.

An object's ``on_check`` softcode runs while an action targeting it is still
being decided — giving data/softcode the veto (``block``) and modify
(``mod`` / ``set_adata``) power a Python behavior has there. This is how
wards, immunity, resistance, and armor become data, not code.
"""

from __future__ import annotations

import random

import pytest

from realm.combat.system import create_combat_system
from realm.core.propagation import Action, propagate
from realm.testing import Simulator


@pytest.fixture
def sim():
    s = Simulator()
    try:
        yield s
    finally:
        s.close()


async def _fire(sim, target, action_type, *, tags=None, extra=None, actor=None):
    action = Action(actor=actor or sim.player("A", location=target.location),
                    target=target, action_type=action_type,
                    tags=set(tags or ()), extra=dict(extra or {}))
    await propagate(action)
    return action


@pytest.mark.asyncio
class TestInterception:

    async def test_on_check_vetoes_a_matching_action(self, sim):
        idol = sim.obj("Idol", location=sim.room("Shrine"))
        idol.db.on_check = "if has_atag('magic'): block('the idol wards itself')"
        blocked = await _fire(sim, idol, "event:zap", tags={"magic"})
        assert blocked.blocked and "wards" in blocked.block_reason

    async def test_on_check_is_selective(self, sim):
        idol = sim.obj("Idol", location=sim.room("Shrine"))
        idol.db.on_check = "if has_atag('magic'): block('warded')"
        passed = await _fire(sim, idol, "event:poke")      # not magic
        assert not passed.blocked

    async def test_on_check_can_modify_the_action(self, sim):
        knight = sim.obj("Knight", location=sim.room("Field"), armor=3)
        knight.db.on_check = (
            "if atype == 'combat:on_damage': mod(-get_attr(me, 'armor'))")
        hit = await _fire(sim, knight, "combat:on_damage", extra={"damage": 10})
        assert hit.total_modifier == -3

    async def test_on_check_can_mutate_the_payload(self, sim):
        knight = sim.obj("Knight", location=sim.room("Field"))
        knight.db.on_check = (
            "if atype == 'combat:on_damage': "
            "set_adata('damage', adata('damage', 0) // 2)")
        hit = await _fire(sim, knight, "combat:on_damage", extra={"damage": 10})
        assert hit.extra["damage"] == 5

    async def test_on_check_is_decision_only(self, sim):
        # A side-effect (pemit) in on_check must NOT fire — the check pass
        # decides, it doesn't act. Reacting belongs in on_react / ON_<EVENT>.
        room = sim.room("Room")
        mage = sim.player("Mage", location=room)
        watcher = sim.obj("Watcher", location=room)
        watcher.db.on_check = "pemit(actor, 'you should not see this')"
        await _fire(sim, watcher, "event:test", actor=mage)
        assert sim.seen(mage) == []

    async def test_on_check_cannot_mutate_the_world(self, sim):
        # The check namespace is read-only: a mutator (set_attr / damage)
        # isn't available, so an aggressive ward can't harm the actor. The
        # call errors in the sandbox (caught) and nothing changes.
        room = sim.room("Room")
        mage = sim.player("Mage", location=room, hp=10)
        trap = sim.obj("Trap", location=room)
        trap.db.on_check = "damage(actor, 9999)\nset_attr(actor, 'hexed', True)"
        await _fire(sim, trap, "event:touch", actor=mage)
        assert mage.db.get("hp") == 10                 # unharmed
        assert mage.db.get("hexed") is None            # unmutated


# --- Combat integration: armor & immunity as data ----------------------------

@pytest.mark.asyncio
class TestCombatAsData:

    def _arena(self, sim):
        room = sim.room("Arena")
        atk = sim.obj("Atk", location=room)
        for k, v in dict(strength=12, dexterity=12, intelligence=10, health=12,
                         skill_melee=20, hp=12, max_hp=12, dodge=8).items():
            atk.db.set(k, v)
        dfn = sim.obj("Dfn", location=room)
        for k, v in dict(strength=10, dexterity=8, intelligence=10, health=12,
                         skill_melee=8, hp=20, max_hp=20, dodge=1).items():
            dfn.db.set(k, v)
        return atk, dfn

    async def test_immunity_via_block_takes_no_damage(self, sim):
        random.seed(0)
        atk, dfn = self._arena(sim)
        dfn.db.on_check = "if atype == 'combat:on_damage': block('immune')"
        combat = create_combat_system("gurps", allow_active_defense=False)
        await combat.attack(atk, dfn)                       # a hit lands...
        assert dfn.db.get("hp") == 20                       # ...but deals nothing

    async def test_armor_via_on_check_reduces_damage(self, sim):
        # Same seeded attack, armored vs not: armor (an on_check mod) cuts
        # exactly its value off the damage.
        async def lost(armored):
            s = Simulator()
            try:
                random.seed(0)
                atk, dfn = self._arena(s)
                if armored:
                    dfn.db.armor = 3
                    dfn.db.on_check = (
                        "if atype == 'combat:on_damage': "
                        "mod(-get_attr(me, 'armor'))")
                combat = create_combat_system("gurps", allow_active_defense=False)
                await combat.attack(atk, dfn)
                return 20 - int(dfn.db.get("hp"))
            finally:
                s.close()

        unarmored = await lost(False)
        armored = await lost(True)
        assert unarmored > 0                                # the hit landed
        assert unarmored - armored == 3                     # armor cut exactly 3
