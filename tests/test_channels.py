"""
MUD_PLAN step 7.2: channels.

A channel is a ``channel_def``; its name and alias are commands. Locks on
the definition decide who speaks and who hears, each player turns channels
on and off (on the account when there is one), and recent lines are kept.
"""

from __future__ import annotations

import pytest

from realm.testing import Simulator


@pytest.fixture
async def sim():
    from realm.packs import import_pack
    s = Simulator()
    await import_pack("channels", s.store)
    try:
        yield s
    finally:
        s.close()


def _text(sim, who):
    return "\n".join(sim.seen(who))


def _people(sim):
    inn, dock = sim.room("Inn"), sim.room("Dock")
    ann = sim.player("Ann", location=inn)
    bob = sim.player("Bob", location=dock)
    imm = sim.player("Imm", location=dock)
    imm.add_tag("builder")
    return ann, bob, imm


async def test_the_default_channels_exist(sim):
    names = {o.name for o in sim.store.find_cached(tag="channel_def")}
    assert names == {"gossip", "newbie", "immtalk"}


async def test_speaking_and_hearing_anywhere(sim):
    ann, bob, imm = _people(sim)
    await sim.do(ann, "gossip anyone for cards?")
    for who in (ann, bob, imm):
        assert "[gossip] Ann: anyone for cards?" in _text(sim, who)


async def test_an_alias_speaks_too(sim):
    ann, bob, _imm = _people(sim)
    alias = sim.store.find_cached(name="gossip")[0].db.alias
    await sim.do(ann, f"{alias} hello")
    assert "[gossip] Ann: hello" in _text(sim, bob)


async def test_locks_decide_who_speaks_and_hears(sim):
    ann, bob, imm = _people(sim)
    await sim.do(ann, "immtalk let me in")
    assert "let me in" not in _text(sim, imm)
    await sim.do(imm, "immtalk staff only")
    assert "staff only" in _text(sim, imm)
    assert "staff only" not in _text(sim, ann)


async def test_toggling_off_and_on(sim):
    ann, bob, _imm = _people(sim)
    await sim.do(bob, "channel gossip off")
    await sim.do(ann, "gossip hello")
    assert "hello" not in _text(sim, bob)
    await sim.do(bob, "gossip can I talk?")
    assert "You have gossip turned off" in _text(sim, bob)
    await sim.do(bob, "channel gossip on")
    await sim.do(ann, "gossip again")
    assert "again" in _text(sim, bob)


async def test_preferences_live_on_the_account(sim):
    ann, bob, _imm = _people(sim)
    alt = sim.player("Bobalt", location=bob.location)
    account = sim.account("bob", bob, alt)
    await sim.do(bob, "channel gossip off")
    assert "gossip" in account.db.channels_off
    await sim.do(ann, "gossip hi")
    assert "hi" not in _text(sim, alt)


async def test_the_channels_listing(sim):
    ann, bob, imm = _people(sim)
    await sim.do(bob, "channel newbie off")
    sim.seen(bob)
    await sim.do(bob, "channels")
    out = _text(sim, bob)
    assert "gossip" in out and "newbie" in out and "off" in out
    assert "immtalk" not in out                     # not a channel Bob may hear
    await sim.do(imm, "channels")
    assert "immtalk" in _text(sim, imm)


async def test_history(sim):
    ann, bob, _imm = _people(sim)
    for n in range(3):
        await sim.do(ann, f"gossip line {n}")
    sim.seen(bob)
    await sim.do(bob, "channel gossip history")
    out = _text(sim, bob)
    assert all(f"line {n}" in out for n in range(3))
    gossip = sim.store.find_cached(name="gossip")[0]
    gossip.db.history_size = 2
    await sim.do(ann, "gossip line 3")
    assert len(gossip.db.history) == 2


async def test_softcode_cemit_and_members(sim):
    ann, bob, imm = _people(sim)
    await sim.do(bob, "channel gossip off")
    herald = sim.obj("herald", location=ann.location)
    await sim.eval(herald, "cemit('gossip', 'The fair opens at dawn.')")
    assert "The fair opens at dawn." in _text(sim, ann)
    assert "fair" not in _text(sim, bob)
    result, _e = await sim.eval(herald, "result = channel_members('gossip')")
    assert sorted(result) == ["Ann", "Imm"]


async def test_softcode_hears_a_channel(sim):
    ann, _bob, _imm = _people(sim)
    gossip = sim.store.find_cached(name="gossip")[0]
    gossip.db.on_channel = "set_attr(me, 'heard', adata('message'))"
    await sim.do(ann, "gossip spill it")
    assert gossip.db.heard == "spill it"


async def test_a_world_verb_of_the_same_name_comes_first(sim):
    ann, bob, _imm = _people(sim)
    horn = sim.obj("horn", location=ann.location)
    horn.db.cmd_newbie = "$newbie *: pemit(enactor, 'The horn honks.')"
    await sim.do(ann, "newbie help")
    assert "The horn honks." in _text(sim, ann)
