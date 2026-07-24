"""
@parent attribute inheritance — templates as the builder-authored
capability bundle (the third category beside tags and behaviors).

A child reads through its parent chain for db attributes it lacks:
values, ON_* hooks, $-commands. Writes always land on the child
(copy-on-write); tags/behaviors/fields never inherit; secret and
protected template attrs never leak; the chain is cycle-refused and
depth-capped. Gate: control the child AND the parent.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.testing import Simulator


@pytest.fixture
def sim():
    s = Simulator()
    s.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: list(s._sessions.values()))
    try:
        yield s
    finally:
        s.close()


def builder(sim, room, name="Bilda"):
    p = sim.player(name, location=room)
    p.add_tag("builder")
    return p


class TestValueInheritance:

    def test_child_reads_through_and_own_wins(self, sim):
        t = sim.obj("template")
        t.db.set("price", 25)
        t.db.set("greeting", "hello")
        c = sim.obj("child")
        c.parent = t
        c.db.set("price", 99)
        assert c.db.get("price") == 99          # own shadows parent
        assert c.db.get("greeting") == "hello"  # inherited
        assert c.db.get("absent", "dflt") == "dflt"

    def test_delete_re_exposes_the_template_value(self, sim):
        t = sim.obj("template"); t.db.set("msg", "from template")
        c = sim.obj("child"); c.parent = t
        c.db.set("msg", "mine")
        assert c.db.get("msg") == "mine"
        c.db.delete("msg")
        assert c.db.get("msg") == "from template"  # reset-to-template

    def test_copy_on_write_incr(self, sim):
        # A numeric template default: read falls through, write lands on
        # the child — the template is never mutated.
        t = sim.obj("template"); t.db.set("stock", 5)
        c = sim.obj("child"); c.parent = t
        c.db.set("stock", c.db.get("stock") + 1)
        assert c.db.get("stock") == 6
        assert t.db.get("stock") == 5

    def test_grandparent_chain_and_contains(self, sim):
        a = sim.obj("a"); a.db.set("deep", 1)
        b = sim.obj("b"); b.parent = a
        c = sim.obj("c"); c.parent = b
        assert c.db.get("deep") == 1
        assert "deep" in c.db
        assert "nope" not in c.db

    def test_own_all_never_shows_inherited(self, sim):
        t = sim.obj("template"); t.db.set("x", 1)
        c = sim.obj("child"); c.parent = t
        c.db.set("y", 2)
        assert c.db.all() == {"y": 2}            # persistence purity
        assert c.db.merged() == {"x": 1, "y": 2}


class TestNeverInherits:

    def test_tags_do_not_inherit(self, sim):
        t = sim.obj("template", tags=["thing", "container"])
        c = sim.obj("child"); c.parent = t
        assert not c.has_tag("container")

    def test_protected_and_flagged_attrs_do_not_inherit(self, sim):
        from realm.core.attrflags import set_attr_flags
        t = sim.obj("template")
        t.db.set("password", "hunter2")
        t.db.set("gm_notes", "the twist ending")
        set_attr_flags(t, "gm_notes", ["secret"])
        t.db.set("keyid", "the_one")  # direct write for the test
        c = sim.obj("child"); c.parent = t
        assert c.db.get("password") is None
        assert c.db.get("gm_notes") is None      # secret stays on template
        assert c.db.get("keyid") is None
        assert "gm_notes" not in c.db.merged()

    def test_flag_table_does_not_inherit(self, sim):
        from realm.core.attrflags import set_attr_flags, writable_attr
        t = sim.obj("template")
        t.db.set("on_open", "pass")
        set_attr_flags(t, "on_open", ["safe"])
        c = sim.obj("child"); c.parent = t
        # The child's own flag lookups are its own — template's 'safe'
        # doesn't lock the child's attrs.
        ok, _ = writable_attr(c, "on_open")
        assert ok

    def test_depth_cap_backstop(self, sim):
        objs = [sim.obj(f"o{i}") for i in range(12)]
        for i in range(1, 12):
            objs[i].parent = objs[i - 1]
        objs[0].db.set("root", "yes")
        assert objs[8].db.get("root") == "yes"    # within cap
        assert objs[11].db.get("root") is None    # beyond 8 ancestors


class TestCommandsAndHooks:

    async def test_template_dollar_command_fires_on_child(self, sim):
        room = sim.room("Shop")
        bilda = builder(sim, room)
        t = sim.obj("kiosk template")
        t.db.set("cmd_ping", "$ping: pemit(enactor, 'Kiosk online.')")
        kiosk = sim.obj("kiosk", location=room)
        kiosk.parent = t
        await sim.do(bilda, "ping")
        assert "Kiosk online." in sim.seen(bilda)

    async def test_child_override_wins_over_template_command(self, sim):
        room = sim.room("Shop")
        bilda = builder(sim, room)
        t = sim.obj("kiosk template")
        t.db.set("cmd_ping", "$ping: pemit(enactor, 'template')")
        kiosk = sim.obj("kiosk", location=room)
        kiosk.parent = t
        kiosk.db.set("cmd_ping", "$ping: pemit(enactor, 'override')")
        await sim.do(bilda, "ping")
        out = sim.seen(bilda)
        assert "override" in out and "template" not in out

    async def test_lockable_door_template_end_to_end(self, sim):
        """The motivating build: four guarded mirror hooks written ONCE
        on a template; two dug (auto-paired) exits adopt it; state
        mirrors. Fix the template and every door on the map is fixed."""
        room = sim.room("Workshop")
        bilda = builder(sim, room)
        t = sim.obj("LockableDoor Template")
        t.db.set("on_open", "if target is me: remove_tag(V('partner'), 'closed')")
        t.db.set("on_close", "if target is me: add_tag(V('partner'), 'closed')")
        t.db.set("on_lock", "if target is me: add_tag(V('partner'), 'locked')")
        t.db.set("on_unlock", "if target is me: remove_tag(V('partner'), 'locked')")

        await sim.do(bilda, "@dig The Vault = vault door, vault door")
        vault = sim.store.find_cached(name="The Vault")[0]
        side_a = next(o for o in room.contents if o.has_tag("exit"))
        side_b = next(o for o in vault.contents if o.has_tag("exit"))
        for side in (side_a, side_b):
            side.parent = t
            side.db.set("key_id", "vault_brass")
        key = sim.obj("brass key", location=bilda)
        key.db.set("unlocks", "vault_brass")

        await sim.do(bilda, "close vault door")
        assert side_a.has_tag("closed") and side_b.has_tag("closed")
        await sim.do(bilda, "lock vault door")
        assert side_a.has_tag("locked") and side_b.has_tag("locked")
        await sim.do(bilda, "unlock vault door")
        assert not side_a.has_tag("locked") and not side_b.has_tag("locked")
        await sim.do(bilda, "open vault door")
        assert not side_a.has_tag("closed") and not side_b.has_tag("closed")


class TestGateAndTools:

    async def test_parent_requires_control_of_the_template(self, sim):
        room = sim.room("Shop")
        ada = sim.player("Ada", location=room); ada.add_tag("admin")
        bob = builder(sim, room, "Bob")
        t = sim.obj("their template", location=room)
        t.owner = ada
        mine = sim.obj("my gadget", location=room)
        mine.owner = bob
        await sim.do(bob, "@parent my gadget = their template")
        assert mine.parent is None
        assert any("don't control" in line.lower() or "control" in line
                   for line in sim.seen(bob))

    async def test_examine_shows_inherited_section(self, sim):
        room = sim.room("Shop")
        bilda = builder(sim, room)
        t = sim.obj("template", location=room)
        t.db.set("greeting", "hello")
        c = sim.obj("gadget", location=room)
        c.parent = t
        c.db.set("own_attr", 1)
        await sim.do(bilda, "@examine gadget")
        joined = "\n".join(sim.seen(bilda))
        assert "Inherited (from template):" in joined
        assert "greeting" in joined

    async def test_clone_keeps_the_parent_link(self, sim):
        room = sim.room("Shop")
        bilda = builder(sim, room)
        t = sim.obj("template")
        t.db.set("cmd_ping", "$ping: pemit(enactor, 'pong')")
        exemplar = sim.obj("kiosk", location=room, tags=["thing"])
        exemplar.parent = t
        exemplar.owner = bilda
        await sim.do(bilda, "@clone kiosk = kiosk two")
        copy = sim.store.find_cached(name="kiosk two")[0]
        assert copy.parent is t

    async def test_foreign_import_without_template_warns(self, sim, caplog):
        # The reference always exports; the OBJECT only if in the set.
        # Importing into a world lacking the template drops the link —
        # loudly, never silently.
        import logging
        from realm.persistence.worldio import export_objects, import_objects
        t = sim.obj("template"); t.db.set("cmd_ping", "$ping: pemit(enactor, 'pong')")
        gadget = sim.obj("gadget"); gadget.parent = t

        foreign = Simulator()
        try:
            with caplog.at_level(logging.WARNING):
                made = await import_objects(export_objects([gadget]), foreign.store)
            assert made[0].parent is None
            assert any("lost its @parent" in r.message for r in caplog.records)
        finally:
            foreign.close()

    async def test_softcode_V_reads_inherited(self, sim):
        room = sim.room("Shop")
        t = sim.obj("template"); t.db.set("motto", "measure twice")
        c = sim.obj("gadget", location=room); c.parent = t
        result, error = await sim.eval(c, "result = V('motto')")
        assert error is None and result == "measure twice"
