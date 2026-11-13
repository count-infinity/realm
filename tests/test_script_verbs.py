"""
Script verbs: one softcode command-line dialect (KERNEL_PLAN 6.1).
"""

from __future__ import annotations

import textwrap
import uuid

import pytest

from realm.features import Feature, FeatureError, FeatureSet, install_default
from realm.scripting.triggers import validate_script
from realm.testing import Simulator


@pytest.fixture(autouse=True)
def restore_default():
    yield
    install_default()


@pytest.fixture
def world():
    sim = Simulator()
    room = sim.room("Hall")
    yard = sim.room("Yard")
    door = sim.obj("north", location=room, tags=["exit"])
    door.db.set("destination", yard.id)
    alice = sim.player("Alice", location=room)
    golem = sim.obj("golem", location=room, tags=["npc"])
    try:
        yield sim, room, yard, alice, golem
    finally:
        sim.close()


def heard(sim, who) -> str:
    return "\n".join(sim.seen(who))


async def _by_attribute(sim, alice, golem, line):
    golem.db.set("cmd_go", f"$poke:{line}")
    await sim.do(alice, "poke")


async def _by_cmd(sim, alice, golem, line):
    await sim.eval(golem, f"cmd({line!r})", enactor=alice)


@pytest.mark.parametrize("run", [_by_attribute, _by_cmd], ids=["attribute", "cmd"])
class TestEachVerb:

    async def test_speech_verbs(self, world, run):
        sim, _room, _yard, alice, golem = world
        for line, expect in (("say Hello there", "golem says, \"Hello there\""),
                             ("pose waves.", "golem waves."),
                             (":bows.", "golem bows."),
                             (";'s gears whir.", "golem's gears whir."),
                             ("emit The air hums.", "The air hums."),
                             ("\\A bell rings.", "A bell rings."),
                             ("whisper Alice = psst", "psst")):
            sim.seen(alice)
            await run(sim, alice, golem, line)
            assert expect in heard(sim, alice), line

    async def test_item_verbs(self, world, run):
        sim, room, _yard, alice, golem = world
        coin = sim.obj("coin", location=room)
        await run(sim, alice, golem, "get coin")
        assert coin.location is golem
        await run(sim, alice, golem, "give coin = Alice")
        assert coin.location is alice
        crate = sim.obj("crate", location=room, tags=["container", "closed"])
        crate.db.set("openable", True)
        await run(sim, alice, golem, "open crate")
        await run(sim, alice, golem, "close crate")
        stone = sim.obj("stone", location=golem)
        await run(sim, alice, golem, "drop stone")
        assert stone.location is room

    async def test_move_trigger_wait(self, world, run):
        sim, _room, yard, alice, golem = world
        golem.db.set("chime", "say ding")
        await run(sim, alice, golem, "trigger chime")
        assert "ding" in heard(sim, alice)
        await run(sim, alice, golem, "wait 0 say later")
        await sim.engine.tick_waits()
        assert "later" in heard(sim, alice)
        await run(sim, alice, golem, "move north")
        assert golem.location is yard


VERB_MODULE = '''
from realm.features import Feature

feature = Feature("{name}")


@feature.script_verb("ping", doc="ping <text>")
async def _ping(engine, executor, rest):
    executor.db.set("pinged", rest)
'''


class TestGameVerbs:

    async def test_a_feature_verb_runs_and_validates(self, tmp_path, monkeypatch):
        name = f"kp_verbs_{uuid.uuid4().hex[:8]}"
        (tmp_path / f"{name}.py").write_text(textwrap.dedent(VERB_MODULE.format(name=name)))
        monkeypatch.syspath_prepend(str(tmp_path))
        sim = Simulator(features=["basics", "talk", name])
        try:
            room = sim.room("Hall")
            alice = sim.player("Alice", location=room)
            bell = sim.obj("bell", location=room)
            bell.db.set("cmd_ring", "$ring:ping hello")
            await sim.do(alice, "ring")
            assert bell.db.get("pinged") == "hello"
            assert validate_script("ping hello") == []
        finally:
            sim.close()

    async def test_a_missing_verb_is_named_and_logged(self, caplog):
        sim = Simulator(features=["basics", "talk", "movement", "look", "building"])
        try:
            room = sim.room("Hall")
            alice = sim.player("Alice", location=room)
            golem = sim.obj("golem", location=room)
            [warning] = validate_script("get key")
            assert "'get'" in warning
            golem.db.set("cmd_grab", "$grab:get key")
            with caplog.at_level("WARNING", logger="realm.scripting.engine"):
                await sim.do(alice, "grab")
            assert len([r for r in caplog.records
                        if "'get' is not a script verb" in r.getMessage()]) == 1
        finally:
            sim.close()

    async def test_cmd_refuses_an_unknown_verb(self, world):
        sim, _room, _yard, alice, golem = world
        _result, err = await sim.eval(golem, "cmd('jump around')", enactor=alice)
        assert err is not None and "not a script verb" in err


class TestCollisions:

    def _verb(self, feature, word, token=None):
        feature.script_verb(word, token=token)(lambda engine, executor, rest: None)

    def test_same_verb_in_two_features_raises(self):
        a, b = Feature("alpha"), Feature("beta")
        self._verb(a, "chant")
        self._verb(b, "chant")
        with pytest.raises(FeatureError, match="'chant'.*'alpha'.*'beta'"):
            FeatureSet([a, b])

    def test_same_token_in_two_features_raises(self):
        a, b = Feature("alpha"), Feature("beta")
        self._verb(a, "shout_a", token="!")
        self._verb(b, "shout_b", token="!")
        with pytest.raises(FeatureError, match="token '!'"):
            FeatureSet([a, b])
