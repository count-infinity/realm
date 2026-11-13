"""
Open vocabularies: lock types (KERNEL_PLAN 6.3) and audiences (6.5).
Entitlements (6.4) are covered in test_permissions.py.
"""

from __future__ import annotations

import textwrap
import uuid

import pytest

from realm.core.propagation import Action, propagate
from realm.features import install_default
from realm.testing import Simulator


@pytest.fixture(autouse=True)
def restore_default():
    yield
    install_default()


@pytest.fixture
def game_feature(tmp_path, monkeypatch):
    def write(body: str) -> str:
        name = f"kp_vocab_{uuid.uuid4().hex[:8]}"
        (tmp_path / f"{name}.py").write_text(textwrap.dedent(body.format(name=name)))
        monkeypatch.syspath_prepend(str(tmp_path))
        return name
    return write


class TestLockTypes:

    async def test_a_games_own_lock_type_without_a_default_passes(self):
        sim = Simulator()
        try:
            room = sim.room("Vault")
            safe = sim.obj("safe", location=room)
            thief = sim.obj("thief", location=room)
            result, err = await sim.eval(thief, f"result = test_lock('#{safe.id}', 'crack')")
            assert err is None and result is True          # nobody set it: open
            safe.locks["crack"] = "False"
            result, _err = await sim.eval(thief, f"result = test_lock('#{safe.id}', 'crack')")
            assert result is False
        finally:
            sim.close()

    async def test_a_declared_lock_type_uses_its_default(self, game_feature):
        name = game_feature('''
from realm.features import Feature
feature = Feature("{name}")
feature.lock_type("crack", default="False", doc="crack this safe")
''')
        sim = Simulator(features=["basics", name])
        try:
            room = sim.room("Vault")
            safe = sim.obj("safe", location=room)
            thief = sim.obj("thief", location=room)
            result, err = await sim.eval(thief, f"result = test_lock('#{safe.id}', 'crack')")
            assert err is None and result is False         # the declared default
        finally:
            sim.close()


ZONE_AUDIENCE = '''
from realm.features import Feature

feature = Feature("{name}")


@feature.audience("zone")
def zone_players(action):
    """Every player in rooms sharing the actor's zone tag."""
    from realm.core.query import find_objects
    room = action.actor.location
    zones = [t for t in room.tags.to_list() if t.startswith("zone:")]
    out = []
    for zone in zones:
        for other in find_objects(tag=zone):
            out.extend(o for o in other.contents if o.is_player)
    return out
'''


class TestAudiences:

    async def test_a_feature_audience_reaches_the_zone(self, game_feature):
        name = game_feature(ZONE_AUDIENCE)
        sim = Simulator(features=["basics", name])
        try:
            hall, mid, far = (sim.room(n) for n in ("Hall", "Mid", "Far"))
            for room in (hall, mid, far):
                room.add_tag("zone:keep")
            guard = sim.player("Guard", location=hall)
            scout = sim.player("Scout", location=far)
            sim.seen(scout)
            action = Action(actor=guard, target=hall, action_type="event:alarm")
            action.add_message("zone", "{actor} sounds the alarm!")
            await propagate(action)
            assert "Guard sounds the alarm!" in sim.seen(scout)
        finally:
            sim.close()

    async def test_an_unregistered_audience_warns_once(self, caplog):
        sim = Simulator()
        try:
            hall = sim.room("Hall")
            guard = sim.player("Guard", location=hall)
            with caplog.at_level("WARNING", logger="realm.core.propagation"):
                for _ in range(2):
                    action = Action(actor=guard, target=hall, action_type="event:mutter")
                    action.add_message("guild", "{actor} mutters.")
                    await propagate(action)
            warnings = [r for r in caplog.records if "'guild'" in r.getMessage()]
            assert len(warnings) == 1
        finally:
            sim.close()
