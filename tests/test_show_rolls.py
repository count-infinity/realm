"""Roll visibility: dice detail on combat messages, per-viewer.

Every ruleset narrates its rolls (RollResult.description); SHOW_ROLLS /
`rolls on` surfaces them on the attacker's and defender's own combat
lines. Bystanders never see roll detail.
"""

from __future__ import annotations

import pytest

from realm.combat.combatant import Combatant
from realm.combat.system import (
    CombatSystem,
    append_roll_notes,
    set_show_rolls_default,
    shows_rolls,
)
from realm.combat.rulesets.merc import MercRuleset
from realm.core.objects import GameObject


@pytest.fixture(autouse=True)
def _reset_default():
    set_show_rolls_default(False)
    yield
    set_show_rolls_default(False)


def _fighter(name, **stats):
    obj = GameObject(name, tags=['player'])
    defaults = {'hp': 50, 'max_hp': 50, 'thac0': 20, 'armor_class': 6,
                'strength': 14}
    for key, value in {**defaults, **stats}.items():
        obj.db.set(key, value)
    return obj


class TestPreference:

    def test_player_flag_wins_over_default(self):
        obj = _fighter("A")
        assert not shows_rolls(obj)              # global default off
        obj.db.show_rolls = True
        assert shows_rolls(obj)
        set_show_rolls_default(True)
        obj.db.show_rolls = False                # personal off beats global on
        assert not shows_rolls(obj)

    def test_global_default_applies_when_unset(self):
        obj = _fighter("A")
        set_show_rolls_default(True)
        assert shows_rolls(obj)

    def test_none_is_safe(self):
        assert not shows_rolls(None)


class TestNotes:

    def test_notes_go_only_to_those_who_opted_in(self):
        atk = _fighter("Attacker")
        dfn = _fighter("Defender")
        atk.db.show_rolls = True
        messages = {'attacker_msg': "You hit!", 'defender_msg': "You are hit!",
                    'others_msg': "A hits D!"}

        class _Roll:
            description = "d20(13) vs need 16"
        append_roll_notes(messages, atk, dfn, _Roll())
        assert "d20(13)" in messages['attacker_msg']
        assert "d20(13)" not in messages['defender_msg']    # dfn opted out
        assert "d20(13)" not in messages['others_msg']      # bystanders never


@pytest.mark.asyncio
class TestEndToEnd:

    async def test_attack_messages_carry_the_dice(self):
        system = CombatSystem(ruleset=MercRuleset())
        atk_obj = _fighter("Grog", thac0=-40)     # always hits
        dfn_obj = _fighter("Dummy")
        atk_obj.db.show_rolls = True
        result = await system.attack(Combatant(atk_obj), Combatant(dfn_obj))
        msg = result.messages.get('attacker_msg', '')
        assert "d20(" in msg                     # attack roll narrated
        assert "THAC0" in msg
        assert "d20(" not in result.messages.get('defender_msg', '')

    async def test_quiet_by_default(self):
        system = CombatSystem(ruleset=MercRuleset())
        atk_obj = _fighter("Grog", thac0=-40)
        dfn_obj = _fighter("Dummy")
        result = await system.attack(Combatant(atk_obj), Combatant(dfn_obj))
        assert "d20(" not in result.messages.get('attacker_msg', '')
