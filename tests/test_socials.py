"""
MUD_PLAN step 7.3: socials (the ``talk`` feature).

A ``social_def`` carries up to five lines; its name is a command when
nothing else is. The socials-classic pack ships the common Diku socials.
"""

from __future__ import annotations

import pytest

from realm.testing import Simulator


@pytest.fixture
async def sim():
    from realm.packs import import_pack
    s = Simulator()
    await import_pack("socials-classic", s.store)
    try:
        yield s
    finally:
        s.close()


def _text(sim, who):
    return "\n".join(sim.seen(who))


def _room(sim):
    inn = sim.room("Inn")
    ann = sim.player("Ann", location=inn)
    bob = sim.player("Bob", location=inn)
    eve = sim.player("Eve", location=inn)
    return inn, ann, bob, eve


def test_the_pack_has_the_common_socials(sim):
    names = {o.name for o in sim.store.find_cached(tag="social_def")}
    assert len(names) >= 40
    assert {"smile", "nod", "bow", "laugh", "wave", "shrug"} <= names


async def test_without_a_target(sim):
    _inn, ann, bob, _eve = _room(sim)
    await sim.do(ann, "smile")
    assert "You smile happily." in _text(sim, ann)
    assert "Ann smiles happily." in _text(sim, bob)


async def test_with_a_target(sim):
    _inn, ann, bob, eve = _room(sim)
    await sim.do(ann, "smile bob")
    assert "You smile at Bob." in _text(sim, ann)
    assert "Ann smiles at you." in _text(sim, bob)
    assert "Ann smiles at Bob." in _text(sim, eve)


async def test_a_target_not_here(sim):
    _inn, ann, _bob, _eve = _room(sim)
    await sim.do(ann, "smile zed")
    assert "They aren't here." in _text(sim, ann)


async def test_an_unseen_actor_reads_as_someone(sim):
    _inn, ann, bob, _eve = _room(sim)
    ann.add_tag("invisible")
    await sim.do(ann, "wave")
    assert "Someone waves happily." in _text(sim, bob)


async def test_a_social_named_like_a_command_never_shadows_it(sim):
    _inn, ann, bob, _eve = _room(sim)
    sim.obj("look", tags=["social_def"], actor="You gawk.", room="{actor} gawks.")
    sim.seen(bob)
    await sim.do(ann, "look")
    assert "You gawk." not in _text(sim, ann)
    assert "gawks" not in _text(sim, bob)


async def test_a_world_verb_comes_first(sim):
    inn, ann, _bob, _eve = _room(sim)
    dice = sim.obj("dice cup", location=inn)
    dice.db.cmd_shake = "$shake: pemit(enactor, 'The dice rattle.')"
    await sim.do(ann, "shake")
    assert "The dice rattle." in _text(sim, ann)


async def test_the_socials_listing(sim):
    _inn, ann, _bob, _eve = _room(sim)
    await sim.do(ann, "socials")
    out = _text(sim, ann)
    assert "smile" in out and "bow" in out


async def test_a_social_without_target_lines_refuses_a_target(sim):
    _inn, ann, _bob, _eve = _room(sim)
    sim.obj("yodel", tags=["social_def"], actor="You yodel.", room="{actor} yodels.")
    await sim.do(ann, "yodel bob")
    assert "You can't yodel at someone." in _text(sim, ann)
