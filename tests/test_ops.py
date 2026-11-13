"""
One service function per world operation (KERNEL_PLAN step 5).

For each op, every actor (a mortal player, a builder, an admin) against
every target (the actor's own, someone else's, unowned, protected) must get
the same outcome three ways: the op called directly, the softcode function,
and the command. Commands keep their permission tiers in this step, so a
mortal player's command is refused before any op runs and is not compared.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pytest

from realm.core import ops
from realm.testing import Simulator

ACTORS = ["player", "builder", "admin"]
TARGETS = ["own", "others", "unowned", "protected"]


@dataclass
class Case:
    command: str                      # with {t} = target #id, {d} = destination #id
    softcode: str
    op: Callable                      # (actor, target, world) -> awaitable or value
    effect: Callable[[Any, Any], Any]  # (target, world) -> observable state
    setup: Callable = lambda t, w, protected: None
    protect_by_god: bool = True       # protected = owned by a god (else setup protects)


@dataclass
class World:
    sim: Simulator
    actor: Any
    target: Any
    vault: Any


def _flag_safe(t, name):
    t.db.set('attr_flags', {name: ['safe']})


def _attr_setup(t, w, protected):
    t.db.set('color', 'blue')
    if protected:
        _flag_safe(t, 'color')


CASES: dict[str, Case] = {
    "set_attr": Case(
        "@set {t}/color = red", "set_attr('{t}', 'color', 'red')",
        lambda a, t, w: ops.set_attr(a, t, 'color', 'red'),
        lambda t, w: t.db.get('color'), setup=_attr_setup, protect_by_god=False),
    "del_attr": Case(
        "@set {t}/color", "del_attr('{t}', 'color')",
        lambda a, t, w: ops.del_attr(a, t, 'color'),
        lambda t, w: t.db.get('color'), setup=_attr_setup, protect_by_god=False),
    "tag": Case(
        "@tag {t} = Shiny", "add_tag('{t}', 'Shiny')",
        lambda a, t, w: ops.tag(a, t, 'Shiny'),
        lambda t, w: sorted(t.tags.to_list())),
    "untag": Case(
        "@untag {t} = shiny", "remove_tag('{t}', 'shiny')",
        lambda a, t, w: ops.untag(a, t, 'shiny'),
        lambda t, w: sorted(t.tags.to_list()),
        setup=lambda t, w, p: t.add_tag('shiny')),
    "set_lock": Case(
        "@lock/use {t} = caller.has_tag('vip')",
        "set_lock('{t}', 'use', \"caller.has_tag('vip')\")",
        lambda a, t, w: ops.set_lock(a, t, 'use', "caller.has_tag('vip')"),
        lambda t, w: dict(t.locks)),
    "clear_lock": Case(
        "@unlock {t}", "clear_lock('{t}', 'use')",
        lambda a, t, w: ops.clear_lock(a, t, None),
        lambda t, w: dict(t.locks),
        setup=lambda t, w, p: t.locks.__setitem__('use', 'True')),
    "rename": Case(
        "@name {t} = gizmo", "set_name('{t}', 'gizmo')",
        lambda a, t, w: ops.rename(a, t, 'gizmo'),
        lambda t, w: t.name),
    "describe": Case(
        "@desc {t} = It hums.", "set_desc('{t}', 'It hums.')",
        lambda a, t, w: ops.describe(a, t, 'It hums.'),
        lambda t, w: t.description),
    "attach_behavior": Case(
        "@behavior {t} = decay", "attach_behavior('{t}', 'decay')",
        lambda a, t, w: ops.attach_behavior(a, t, 'decay'),
        lambda t, w: [b.behavior_id for b in t.get_behaviors()]),
    "destroy": Case(
        "@destroy {t}", "destroy_obj('{t}')",
        lambda a, t, w: ops.destroy(a, t, w.sim.store),
        lambda t, w: w.sim.store.get_cached(t.id) is not None,
        setup=lambda t, w, p: t.add_tag('safe') if p else None, protect_by_god=False),
    "relocate": Case(
        "@teleport {t} = {d}", "teleport_obj('{t}', '{d}')",
        lambda a, t, w: ops.relocate(a, t, w.vault, force=True),
        lambda t, w: t.location.name if t.location else None),
}


def _world(role: str, target_kind: str, case: Case) -> World:
    sim = Simulator()
    room = sim.room("Hall")
    vault = sim.room("Vault")
    actor = sim.player("Actor", location=room)
    if role != "player":
        actor.add_tag(role)
    other = sim.player("Other", location=sim.room("Elsewhere"))
    zeus = sim.player("Zeus", location=sim.room("Olympus"))
    zeus.add_tag("god")
    target = sim.obj("widget", location=room)
    protected = target_kind == "protected"
    if target_kind == "own" or (protected and not case.protect_by_god):
        target.owner = actor
    elif target_kind == "others":
        target.owner = other
    elif protected:
        target.owner = zeus
    case.setup(target, World(sim, actor, target, vault), protected)
    return World(sim, actor, target, vault)


def _fill(text: str, w: World) -> str:
    return text.format(t="#" + w.target.id, d="#" + w.vault.id)


async def _run_op(case: Case, w: World) -> Any:
    try:
        result = case.op(w.actor, w.target, w)
        if hasattr(result, "__await__"):
            await result
    except ops.OpError:
        pass
    return case.effect(w.target, w)


async def _run_softcode(case: Case, w: World) -> Any:
    _result, err = await w.sim.eval(w.actor, _fill(case.softcode, w))
    assert err is None or "is not defined" in err, err
    return case.effect(w.target, w)


async def _run_command(case: Case, w: World) -> Any:
    await w.sim.do(w.actor, _fill(case.command, w))
    return case.effect(w.target, w)


@pytest.mark.parametrize("target_kind", TARGETS)
@pytest.mark.parametrize("role", ACTORS)
@pytest.mark.parametrize("name", list(CASES))
async def test_command_softcode_and_op_agree(name, role, target_kind):
    case = CASES[name]
    outcomes = {}
    for surface, run in (("op", _run_op), ("softcode", _run_softcode),
                         ("command", _run_command)):
        if surface == "command" and role == "player":
            continue                      # builder-tier command: refused by the dispatcher
        w = _world(role, target_kind, case)
        try:
            outcomes[surface] = await run(case, w)
        finally:
            w.sim.close()
    assert len(set(map(repr, outcomes.values()))) == 1, outcomes


class TestOpRules:
    """Unified rules the old surfaces disagreed on."""

    def test_tags_are_lowercased(self):
        sim = Simulator()
        try:
            thing = sim.obj("widget", location=sim.room("Hall"))
            ops.tag(None, thing, "Shiny")
            assert thing.tags.to_list() == ["shiny"]
        finally:
            sim.close()

    def test_both_protected_names_are_refused(self):
        sim = Simulator()
        try:
            thing = sim.obj("widget", location=sim.room("Hall"))
            for name in ("keyid", "password"):
                with pytest.raises(ops.Refused):
                    ops.set_attr(None, thing, name, "x")
        finally:
            sim.close()

    def test_create_location_rule(self):
        sim = Simulator()
        try:
            hall, other = sim.room("Hall"), sim.room("Elsewhere")
            other.owner = sim.player("Owner", location=other)
            actor = sim.player("Actor", location=hall)
            assert ops.create(actor, "pebble", location=actor).value.location is actor
            assert ops.create(actor, "pebble", location=hall).value.location is hall
            with pytest.raises(ops.NotAllowed):
                ops.create(actor, "pebble", location=other)
        finally:
            sim.close()

    def test_create_owner_is_actors_owner_or_actor(self):
        sim = Simulator()
        try:
            hall = sim.room("Hall")
            alice = sim.player("Alice", location=hall)
            gadget = sim.obj("gadget", location=hall)
            gadget.owner = alice
            assert ops.create(alice, "pebble", location=hall).value.owner is alice
            assert ops.create(gadget, "pebble", location=hall).value.owner is alice
        finally:
            sim.close()

    def test_script_warning_is_returned_not_refused(self):
        sim = Simulator()
        try:
            thing = sim.obj("widget", location=sim.room("Hall"))
            result = ops.set_attr(None, thing, "on_tick", "if (")
            assert result.warnings and "will not run" in result.warnings[0]
            assert thing.db.get("on_tick") == "if ("
        finally:
            sim.close()

    def test_chown_needs_control_all_and_halts_scripts(self):
        sim = Simulator()
        try:
            hall = sim.room("Hall")
            builder = sim.player("Bob", location=hall)
            builder.add_tag("builder")
            admin = sim.player("Ada", location=hall)
            admin.add_tag("admin")
            box = sim.obj("box", location=hall)
            box.db.set("cmd_open", "$open box:say hi")
            with pytest.raises(ops.NotAllowed):
                ops.chown(builder, box, builder)
            result = ops.chown(admin, box, builder)
            assert box.owner is builder and box.has_tag("halt") and result.warnings
        finally:
            sim.close()

    async def test_boot_needs_moderate(self):
        sim = Simulator()
        try:
            hall = sim.room("Hall")
            builder = sim.player("Bob", location=hall)
            builder.add_tag("builder")
            victim = sim.player("Vic", location=hall)
            with pytest.raises(ops.NotAllowed):
                ops.check_boot(builder, victim, None)
        finally:
            sim.close()

    async def test_destroying_a_room_unpairs_the_exits_inside(self):
        """The 1.1 gap: an exit deleted with its room left its far side
        pointing at a deleted exit."""
        sim = Simulator()
        try:
            hall = sim.room("Hall")
            result = ops.dig(None, "Annex", from_room=hall, out_name="east")
            annex, east, west = result.value
            for obj in (annex, east, west):
                sim.store.add(obj)
            assert east.db.get("partner") == "#" + west.id
            await ops.destroy(None, annex, sim.store)
            assert east.db.get("partner") is None
        finally:
            sim.close()

    def test_dig_refuses_a_taken_exit_name_before_creating(self):
        sim = Simulator()
        try:
            hall = sim.room("Hall")
            ops.open_exit(None, "east", location=hall, destination=sim.room("X"))
            with pytest.raises(ops.Invalid):
                ops.dig(None, "Annex", from_room=hall, out_name="east")
        finally:
            sim.close()
