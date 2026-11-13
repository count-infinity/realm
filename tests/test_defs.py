"""
One definition loader (KERNEL_PLAN 6.6).
"""

from __future__ import annotations

import textwrap
import uuid

import pytest

from realm.core import defs
from realm.features import install_default
from realm.testing import Simulator


@pytest.fixture(autouse=True)
def restore_default():
    yield
    install_default()


@pytest.fixture
def sim():
    s = Simulator()
    try:
        yield s
    finally:
        s.close()


def skill(sim, name, stat="dexterity", penalty=-5):
    return sim.obj(name, tags=["skill_def"], stat=stat, penalty=penalty)


class TestCaching:

    def test_cached_until_a_def_object_changes(self, sim):
        stealth = skill(sim, "stealth")
        first = defs.all_defs("skill")
        assert first["stealth"] == ("dexterity", -5)
        assert defs.all_defs("skill") is first                 # cached
        stealth.db.set("penalty", -3)                           # any write drops it
        assert defs.all_defs("skill")["stealth"] == ("dexterity", -3)

    async def test_at_set_and_at_tag_are_live(self, sim):
        room = sim.room("Hall")
        bob = sim.player("Bob", location=room)
        bob.add_tag("admin")
        skill(sim, "stealth")
        assert "stealth" in defs.all_defs("skill")
        await sim.do(bob, "@set stealth/penalty = -2")
        assert defs.all_defs("skill")["stealth"] == ("dexterity", -2)
        hacking = sim.obj("hacking", stat="iq", penalty=-6)
        assert "hacking" not in defs.all_defs("skill")
        await sim.do(bob, f"@tag #{hacking.id} = skill_def")
        assert defs.all_defs("skill")["hacking"] == ("iq", -6)
        await sim.do(bob, f"@untag #{hacking.id} = skill_def")
        assert "hacking" not in defs.all_defs("skill")

    def test_prefix_matching(self, sim):
        skill(sim, "stealth")
        skill(sim, "streetwise")
        assert defs.find_def("skill", "STEALTH") == ("dexterity", -5)
        assert defs.find_def("skill", "stea") == ("dexterity", -5)
        assert defs.find_def("skill", "st") is None              # ambiguous


RECIPES = '''
from realm.features import Feature

feature = Feature("{name}")


def parse_recipe(obj):
    needs = obj.db.get("needs")
    if not isinstance(needs, dict):
        raise ValueError("needs must be a dict")
    return needs


feature.def_kind("recipe", "recipe_def", parse=parse_recipe)
'''


class TestGameKinds:

    def test_a_game_kind_with_a_failing_parser(self, tmp_path, monkeypatch, caplog):
        name = f"kp_recipes_{uuid.uuid4().hex[:8]}"
        (tmp_path / f"{name}.py").write_text(textwrap.dedent(RECIPES.format(name=name)))
        monkeypatch.syspath_prepend(str(tmp_path))
        sim = Simulator(features=["basics", name])
        try:
            sim.obj("stew", tags=["recipe_def"], needs={"carrot": 2})
            sim.obj("broken", tags=["recipe_def"], needs="carrots")
            with caplog.at_level("WARNING", logger="realm.core.defs"):
                recipes = defs.all_defs("recipe")
            assert recipes == {"stew": {"carrot": 2}}
            assert any("'broken'" in r.getMessage() for r in caplog.records)
        finally:
            sim.close()

    def test_unknown_kind_raises(self):
        with pytest.raises(KeyError, match="no definition kind"):
            defs.all_defs("nonesuch")
