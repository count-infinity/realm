"""
MUD_PLAN step 6.5: achievements.

An ``achievement_def`` names an achievement, its scope (``account`` or
``character``), and its grants: tags and check modifiers. Earned once with
softcode ``grant_achievement``; an account achievement reaches every
character of the account, including one logged in later.
"""

from __future__ import annotations

import pytest

from realm.core.action_types import ActionType
from realm.core.propagation import Action, propagate
from realm.std.rules.checks import condition_modifier
from realm.testing import Simulator


@pytest.fixture
def sim():
    s = Simulator()
    try:
        yield s
    finally:
        s.close()


def _achievement(sim, name, **attrs):
    return sim.obj(name, tags=["achievement_def"], **attrs)


def _world(sim):
    room = sim.room("Crypt")
    bree = sim.player("Bree", location=room)
    cole = sim.player("Cole")                          # not logged in yet
    dov = sim.player("Dov", location=room)
    ann = sim.account("Ann", bree, cole)
    zed = sim.account("Zed", dov)
    altar = sim.obj("altar", location=room)
    _achievement(sim, "Banshee Slayer", description="Slay the banshee.",
                 grants={"tags": ["banshee_slayer"], "check_mods": {"will": 1}})
    return room, ann, zed, bree, cole, dov, altar


async def _login(sim, player, room):
    player.location = room
    await propagate(Action(actor=player, target=room, action_type=ActionType.CONNECT))


async def test_earned_on_one_character_it_reaches_the_others(sim):
    room, ann, zed, bree, cole, dov, altar = _world(sim)
    altar.db.on_ach = "result = 1"
    witness = sim.obj("witness", location=room)
    witness.db.on_achievement = "set_attr(me, 'heard', adata('achievement'))"
    _r, err = await sim.eval(altar, "grant_achievement(get('Bree'), 'Banshee Slayer')")
    assert err is None
    assert "Banshee Slayer" in ann.db.achievements
    assert any("Banshee Slayer" in line for line in sim.seen(bree))
    assert bree.has_tag("banshee_slayer")
    assert condition_modifier(bree, "will") == 1
    assert witness.db.heard == "Banshee Slayer"

    await _login(sim, cole, room)
    assert cole.has_tag("banshee_slayer")
    assert condition_modifier(cole, "will") == 1
    assert condition_modifier(cole, "stealth") == 0
    assert not dov.has_tag("banshee_slayer") and condition_modifier(dov, "will") == 0


async def test_granting_twice_does_nothing(sim):
    room, ann, zed, bree, cole, dov, altar = _world(sim)
    await sim.eval(altar, "grant_achievement(get('Bree'), 'Banshee Slayer')")
    first = dict(ann.db.achievements)
    sim.seen(bree)
    result, _e = await sim.eval(altar, "result = grant_achievement(get('Cole'), 'Banshee Slayer')")
    assert result is False
    assert ann.db.achievements == first
    assert not sim.seen(bree)


async def test_a_character_scope_stays_put(sim):
    room, ann, zed, bree, cole, dov, altar = _world(sim)
    _achievement(sim, "First Steps", scope="character", grants={"tags": ["walker"]})
    await sim.eval(altar, "grant_achievement(get('Bree'), 'First Steps')")
    assert "First Steps" in bree.db.achievements
    assert "First Steps" not in (ann.db.get("achievements") or {})
    await _login(sim, cole, room)
    assert bree.has_tag("walker") and not cole.has_tag("walker")
    result, _e = await sim.eval(altar, "result = has_achievement(get('Cole'), 'First Steps')")
    assert result is False


async def test_has_achievement_and_the_listing(sim):
    room, ann, zed, bree, cole, dov, altar = _world(sim)
    _achievement(sim, "Secret Door", hidden=True, description="Find it.")
    _achievement(sim, "Explorer", description="See everything.")
    await sim.eval(altar, "grant_achievement(get('Bree'), 'Banshee Slayer')")
    result, _e = await sim.eval(altar, "result = has_achievement(get('Cole'), 'Banshee Slayer')")
    assert result is True
    sim.seen(bree)
    await sim.do(bree, "achievements")
    out = "\n".join(sim.seen(bree))
    assert "Banshee Slayer" in out and "Explorer" in out
    assert "Secret Door" not in out and "1 hidden" in out
    await sim.eval(altar, "grant_achievement(get('Bree'), 'Secret Door')")
    sim.seen(bree)
    await sim.do(bree, "achievements")
    assert "Secret Door" in "\n".join(sim.seen(bree))


async def test_a_reload_picks_up_changed_grants(sim):
    room, ann, zed, bree, cole, dov, altar = _world(sim)
    await sim.eval(altar, "grant_achievement(get('Bree'), 'Banshee Slayer')")
    assert condition_modifier(bree, "will") == 1
    slayer = sim.store.find_cached(name="Banshee Slayer")[0]
    slayer.db.grants = {"check_mods": {"all": 2}}
    for hook in sim.world.reload_hooks:
        hook(sim.world)
    assert condition_modifier(bree, "will") == 2


async def test_an_unknown_achievement_is_refused(sim):
    room, ann, zed, bree, cole, dov, altar = _world(sim)
    result, _e = await sim.eval(altar, "result = grant_achievement(get('Bree'), 'Nope')")
    assert result is False and not (ann.db.get("achievements") or {})
