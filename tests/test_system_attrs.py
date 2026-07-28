"""System-owned attributes: the `system` flag and CONTROL_ALL write gate.

A character's stats are stamped `system` at creation, so neither the
player nor a plain builder can rewrite them through `@set`, softcode
`set_attr`/`del_attr`, or `@wipe`. Only ADMIN+ (CONTROL_ALL, walked up a
script's owner chain) may, and the native GameSystem — writing raw
`db.set` in Python — bypasses the gate entirely, since it is the system
that owns them.
"""

from __future__ import annotations

import pytest

from realm.core.attrflags import has_attr_flag, mark_system, writable_attr
from realm.scripting.functions import ScriptFunctions
from realm.testing import Simulator


@pytest.fixture
def world():
    sim = Simulator()
    bay = sim.room("Bay")
    admin = sim.player("God", location=bay)
    admin.add_tag("admin")
    builder = sim.player("Bilda", location=bay)
    builder.add_tag("builder")
    zed = sim.player("Zed", location=bay)
    zed.db.set("strength", 12)
    yield sim, bay, admin, builder, zed
    sim.close()


def funcs(executor, sim, bay):
    return ScriptFunctions(enactor=executor, executor=executor,
                           location=bay, persistence=sim.store)


class TestWritableGate:

    def test_system_attr_refuses_below_admin(self, world):
        _sim, _bay, admin, builder, zed = world
        mark_system(zed, "strength")
        assert writable_attr(zed, "strength", zed)[0] is False
        assert writable_attr(zed, "strength", builder)[0] is False
        assert writable_attr(zed, "strength", admin)[0] is True

    def test_normal_attr_stays_open(self, world):
        _sim, _bay, _admin, builder, zed = world
        mark_system(zed, "strength")
        assert writable_attr(zed, "mood", builder)[0] is True

    def test_no_writer_is_refused(self, world):
        _sim, _bay, _admin, _builder, zed = world
        mark_system(zed, "strength")
        assert writable_attr(zed, "strength", None)[0] is False

    def test_delegated_admin_authority_passes(self, world):
        sim, bay, admin, _builder, zed = world
        mark_system(zed, "strength")
        pod = sim.obj("pod", location=bay)
        pod.owner = admin      # a script running as an admin-owned object
        assert writable_attr(zed, "strength", pod)[0] is True

    def test_builder_owned_script_does_not_pass(self, world):
        sim, bay, _admin, builder, zed = world
        mark_system(zed, "strength")
        gadget = sim.obj("gadget", location=bay)
        gadget.owner = builder
        assert writable_attr(zed, "strength", gadget)[0] is False


class TestSoftcodePaths:

    def test_set_attr_blocked_for_the_player(self, world):
        sim, bay, _admin, _builder, zed = world
        mark_system(zed, "strength")
        assert funcs(zed, sim, bay).set_attr(zed, "strength", 99) is False
        assert zed.db.get("strength") == 12

    def test_del_attr_blocked_for_the_player(self, world):
        sim, bay, _admin, _builder, zed = world
        mark_system(zed, "strength")
        assert funcs(zed, sim, bay).del_attr(zed, "strength") is False
        assert zed.db.get("strength") == 12

    def test_admin_owned_script_may_write(self, world):
        sim, bay, admin, _builder, zed = world
        mark_system(zed, "strength")
        pod = sim.obj("pod", location=bay)
        pod.owner = admin
        assert funcs(pod, sim, bay).set_attr(zed, "strength", 14) is True
        assert zed.db.get("strength") == 14

    def test_normal_attr_still_writable_by_own_gadget(self, world):
        sim, bay, _admin, _builder, zed = world
        mark_system(zed, "strength")
        assert funcs(zed, sim, bay).set_attr(zed, "notes", "hi") is True
        assert zed.db.get("notes") == "hi"


@pytest.mark.asyncio
class TestCommandPaths:

    async def test_at_set_tiers(self, world):
        sim, bay, admin, _builder, zed = world
        mark_system(zed, "strength")

        sim.seen(zed)
        await sim.submit_line(zed, "@set Zed/strength = 30")
        assert zed.db.get("strength") == 12   # player refused

        sim.seen(admin)
        await sim.submit_line(admin, "@set Zed/strength = 30")
        assert zed.db.get("strength") == 30   # admin allowed

    async def test_at_wipe_spares_system_attrs_below_admin(self, world):
        sim, bay, admin, builder, _zed = world
        # a builder's own scratch object with a mix of attrs (@wipe is
        # builder-gated, so a plain player never reaches this path)
        pad = sim.obj("pad", location=bay)
        pad.owner = builder
        pad.db.set("scratch", 1)
        pad.db.set("serial", "SN-1")
        mark_system(pad, "serial")

        sim.seen(builder)
        await sim.submit_line(builder, "@wipe pad")
        assert pad.db.get("scratch") is None      # ordinary attr wiped
        assert pad.db.get("serial") == "SN-1"     # system attr survives

        sim.seen(admin)
        await sim.submit_line(admin, "@wipe pad")
        assert pad.db.get("serial") is None       # admin wipe reaches it


class TestChargenStamping:

    def test_finish_chargen_locks_the_characteristics(self):
        from realm.systems.gurps import GurpsSystem
        sim = Simulator()
        zed = sim.player("Zed", location=sim.room("Bay"))
        for stat in ("strength", "dexterity", "intelligence", "health"):
            zed.db.set(stat, 11)
        GurpsSystem().finish_chargen(zed)
        for stat in ("strength", "dexterity", "intelligence", "health",
                     "hp", "max_hp", "dodge"):
            assert has_attr_flag(zed, stat, "system"), stat
        sim.close()

    def test_apply_class_locks_stats_but_not_skills(self):
        from realm.systems.definitions import apply_class
        sim = Simulator()
        zed = sim.player("Zed", location=sim.room("Bay"))
        apply_class(zed, ("a pilot", {"dexterity": 13}, {"piloting": 14}),
                    "pilot")
        assert has_attr_flag(zed, "dexterity", "system")
        assert not has_attr_flag(zed, "skill_piloting", "system")
        sim.close()

    def test_add_attr_flag_is_additive(self):
        sim = Simulator()
        obj = sim.obj("thing", location=sim.room("Bay"))
        from realm.core.attrflags import add_attr_flag, attr_flags
        add_attr_flag(obj, "x", "secret")
        add_attr_flag(obj, "x", "system")
        assert attr_flags(obj, "x") == {"secret", "system"}
        sim.close()
