"""
MUD_PLAN step 6.4: account data in softcode.

``account_attr``, ``set_account_attr``, ``incr_account_attr`` and
``account_characters`` reach the account behind a character, so state set
by one character is read by another of the same person, and by nobody
else.
"""

from __future__ import annotations

import pytest

from realm.testing import Simulator


@pytest.fixture
def sim():
    s = Simulator()
    try:
        yield s
    finally:
        s.close()


def _world(sim):
    room = sim.room("Hall")
    bree = sim.player("Bree", location=room)
    cole = sim.player("Cole", location=room)
    dov = sim.player("Dov", location=room)
    ann = sim.account("Ann", bree, cole)
    sim.account("Zed", dov)
    # Players are controlled by themselves, their owner and admins: the
    # ledger is an admin's, as a game's own bank or quest board would be.
    boss = sim.player("Boss")
    boss.add_tag("admin")
    ledger = sim.obj("ledger", location=room)
    ledger.owner = boss
    return room, ann, bree, cole, dov, ledger


async def test_a_value_set_from_one_character_reads_from_another(sim):
    _room, ann, bree, cole, dov, ledger = _world(sim)
    _r, err = await sim.eval(ledger, "set_account_attr(get('Bree'), 'gold_banked', 50)")
    assert err is None
    assert ann.db.gold_banked == 50
    result, _e = await sim.eval(ledger, "result = account_attr(get('Cole'), 'gold_banked')")
    assert result == 50
    result, _e = await sim.eval(ledger, "result = account_attr(get('Dov'), 'gold_banked', 0)")
    assert result == 0


async def test_incr_and_the_character_list(sim):
    _room, ann, bree, cole, dov, ledger = _world(sim)
    await sim.eval(ledger, "incr_account_attr(get('Cole'), 'kills')")
    await sim.eval(ledger, "incr_account_attr(get('Bree'), 'kills', 4)")
    assert ann.db.kills == 5
    result, _e = await sim.eval(ledger, "result = account_characters(get('Bree'))")
    assert result == ["Bree", "Cole"]


async def test_a_character_without_an_account(sim):
    room = sim.room("Hall")
    sim.player("Solo", location=room)
    ledger = sim.obj("ledger", location=room)
    result, _e = await sim.eval(ledger, "result = account_attr(get('Solo'), 'kills', 7)")
    assert result is None
    result, _e = await sim.eval(ledger, "result = set_account_attr(get('Solo'), 'kills', 1)")
    assert result is False


async def test_the_setters_need_control_and_refuse_protected_and_system(sim):
    from realm.core.attrflags import set_attr_flags
    _room, ann, bree, cole, dov, _ledger = _world(sim)
    pin = sim.obj("pin", location=bree.location)  # an object of Dov's
    pin.owner = dov                                    # Dov's object: no control of Bree
    result, _e = await sim.eval(pin, "result = set_account_attr(get('Bree'), 'gold', 1)")
    assert result is False and ann.db.get("gold") is None
    trusted = _ledger
    result, _e = await sim.eval(trusted, "result = set_account_attr(get('Bree'), 'password', 'x')")
    assert result is False and str(ann.db.password).startswith("scrypt$")
    ann.db.vip = 1
    set_attr_flags(ann, "vip", ["system"])
    result, _e = await sim.eval(trusted, "result = set_account_attr(get('Bree'), 'vip', 2)")
    assert result is False and ann.db.vip == 1


async def test_the_character_limit_and_its_bonus_slots(sim):
    """Decision D2: ``MAX_CHARACTERS`` plus the account's own
    ``bonus_characters`` (an administrator's ``@account/slots``), read with
    ``character_limit``; softcode reads the bonus and cannot write it, nor
    the other records the engine keeps on an account."""
    _room, ann, bree, cole, dov, ledger = _world(sim)
    result, _e = await sim.eval(ledger, "result = character_limit(get('Bree'))")
    assert result == 5
    ann.db.bonus_characters = 2
    result, _e = await sim.eval(ledger, "result = character_limit(get('Cole'))")
    assert result == 7
    result, _e = await sim.eval(ledger, "result = account_attr(get('Bree'), 'bonus_characters')")
    assert result == 2
    for name in ("bonus_characters", "characters", "achievements", "banned_until"):
        result, _e = await sim.eval(ledger, f"result = set_account_attr(get('Bree'), '{name}', 9)")
        assert result is False, name
        result, _e = await sim.eval(ledger, f"result = incr_account_attr(get('Bree'), '{name}')")
        assert result is None, name
    assert ann.db.bonus_characters == 2 and ann.db.characters == [bree.id, cole.id]
    sim.player("Solo", location=_room)
    result, _e = await sim.eval(ledger, "result = character_limit(get('Solo'))")
    assert result is None
