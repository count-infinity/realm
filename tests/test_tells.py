"""
MUD_PLAN step 7.1: tells, ignore and afk (the ``channels`` feature).

A tell reaches an online player anywhere, as one propagated
``comm:on_tell`` action with the recipient as target and no room audience,
so softcode reacts and wards veto.
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


def _two_rooms(sim):
    inn, dock = sim.room("Inn"), sim.room("Dock")
    ann = sim.player("Ann", location=inn)
    bob = sim.player("Bob", location=dock)
    eve = sim.player("Eve", location=inn)
    return inn, dock, ann, bob, eve


def _text(sim, who):
    return "\n".join(sim.seen(who))


async def test_a_tell_crosses_rooms_and_reply_answers(sim):
    inn, dock, ann, bob, eve = _two_rooms(sim)
    await sim.do(ann, "tell bob meet me at the inn")
    assert "Ann tells you, 'meet me at the inn'" in _text(sim, bob)
    assert "You tell Bob, 'meet me at the inn'" in _text(sim, ann)
    assert "meet me" not in _text(sim, eve)              # no room audience
    await sim.do(bob, "r on my way")
    assert "Bob tells you, 'on my way'" in _text(sim, ann)
    await sim.do(bob, "t ann quick")
    assert "Bob tells you, 'quick'" in _text(sim, ann)


async def test_reply_with_nobody_to_reply_to(sim):
    _inn, _dock, ann, _bob, _eve = _two_rooms(sim)
    await sim.do(ann, "reply hello?")
    assert "Nobody has told you anything" in _text(sim, ann)


async def test_an_offline_player_is_pointed_at_mail(sim):
    inn, _dock, ann, _bob, _eve = _two_rooms(sim)
    sim.obj("Gus", tags=["player"])                     # a character with no connection
    await sim.do(ann, "tell gus hello")
    out = _text(sim, ann)
    assert "Gus is not online" in out and "mail" in out
    await sim.do(ann, "tell nobody hello")
    assert "No one called 'nobody'" in _text(sim, ann)


async def test_ignore_unignore_and_the_list(sim):
    _inn, _dock, ann, bob, _eve = _two_rooms(sim)
    await sim.do(bob, "ignore ann")
    sim.seen(bob)
    await sim.do(ann, "tell bob hi")
    assert "Bob is not listening to you." in _text(sim, ann)
    assert "hi" not in _text(sim, bob)
    await sim.do(bob, "ignore")
    assert "Ann" in _text(sim, bob)
    await sim.do(bob, "unignore ann")
    await sim.do(ann, "tell bob hi")
    assert "Ann tells you, 'hi'" in _text(sim, bob)


async def test_afk_tellers_are_shown_the_message(sim):
    _inn, _dock, ann, bob, _eve = _two_rooms(sim)
    await sim.do(bob, "afk making tea")
    assert bob.has_tag("afk")
    sim.seen(bob)
    await sim.do(ann, "tell bob there?")
    out = _text(sim, ann)
    assert "Bob is away: making tea" in out
    assert "Ann tells you, 'there?'" in _text(sim, bob)   # still delivered
    await sim.do(bob, "afk")
    assert not bob.has_tag("afk")


async def test_a_ward_silences_tells_from_a_room(sim):
    inn, _dock, ann, bob, _eve = _two_rooms(sim)
    inn.db.on_check = "if atype == 'comm:on_tell': block('The walls swallow your words.')"
    await sim.do(ann, "tell bob anyone?")
    assert "The walls swallow your words." in _text(sim, ann)
    assert "anyone" not in _text(sim, bob)


async def test_softcode_hears_a_tell(sim):
    _inn, dock, ann, bob, _eve = _two_rooms(sim)
    bob.db.on_tell = "set_attr(me, 'last_heard', adata('message'))"
    await sim.do(ann, "tell bob psst")
    assert bob.db.last_heard == "psst"


async def test_a_sleeper_still_gets_a_tell(sim):
    _inn, _dock, ann, bob, _eve = _two_rooms(sim)
    bob.add_tag("sleeping")
    await sim.do(ann, "tell bob wake up")
    assert "Ann tells you, 'wake up'" in _text(sim, bob)
