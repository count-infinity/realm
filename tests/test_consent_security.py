"""
Enactor-consent security model — who may relocate whom from softcode.

``move_to``/``enter_instance`` may move the ENACTOR only when they
*deliberately invoked the executing object*: typed its ``$``-command, or
walked the exit whose ``ON_FAIL`` is running. Passive triggers — being
overheard (``^listen``) or witnessed (a bystander's ``ON_ENTER``) — grant NO
such authority (the confused-deputy hole the vision audit caught): a statue
must not teleport whoever says "hello" near it.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.testing import Simulator


@pytest.fixture
def world():
    sim = Simulator()
    hall = sim.room("Hall")
    oubliette = sim.room("Oubliette")
    alice = sim.player("Alice", location=hall)
    try:
        yield SimpleNamespace(sim=sim, hall=hall, oubliette=oubliette,
                              alice=alice)
    finally:
        sim.close()


@pytest.mark.asyncio
class TestPassiveTriggersGrantNoAuthority:

    async def test_listen_trigger_cannot_teleport_the_speaker(self, world):
        w = world
        statue = w.sim.obj("statue", location=w.hall)
        statue.db.set(
            "listen_grab", f"^*hello*:move_to(enactor, '#{w.oubliette.id}')")

        await w.sim.do(w.alice, "say hello there")

        assert w.alice.location is w.hall     # speaking is not consent

    async def test_listen_trigger_cannot_pull_speaker_into_instance(self, world):
        w = world
        entry = w.sim.room("Crypt Entrance")
        entry.add_tag("zone:crypt")
        entry.add_tag("instance_template")
        entry.add_tag("instance_entry")
        statue = w.sim.obj("statue", location=w.hall)
        statue.db.set("listen_grab", "^*hi*:enter_instance(enactor, 'crypt')")

        await w.sim.do(w.alice, "say hi everyone")

        assert w.alice.location is w.hall

    async def test_bystander_on_enter_cannot_relocate_the_walker(self, world):
        w = world
        lobby = w.sim.room("Lobby")
        exit_in = w.sim.obj("in", location=w.hall, tags=["exit"])
        exit_in.db.set("destination", lobby.id)
        trap = w.sim.obj("trap", location=lobby)
        trap.db.set("ON_ENTER", f"move_to(enactor, '#{w.oubliette.id}')")

        await w.sim.do(w.alice, "in")

        # Alice consented to entering the Lobby — not to being sent onward.
        assert w.alice.location is lobby


@pytest.mark.asyncio
class TestDeliberateInvocationGrantsConsent:

    async def test_dollar_command_may_move_the_typer(self, world):
        w = world
        portal = w.sim.obj("portal", location=w.hall)
        portal.db.set(
            "cmd_touch", f"$touch portal:move_to(enactor, '#{w.oubliette.id}')")

        await w.sim.do(w.alice, "touch portal")

        # Typing the object's own command IS deliberate interaction.
        assert w.alice.location is w.oubliette

    async def test_exit_on_fail_may_move_its_walker(self, world):
        w = world
        # (The portal pattern — also covered in test_fail_event; kept here so
        # the consent matrix reads complete in one file.)
        dead_end = w.sim.obj("north", location=w.hall, tags=["exit"])
        dead_end.db.set("on_fail", f"move_to(enactor, '#{w.oubliette.id}')")

        await w.sim.do(w.alice, "north")

        assert w.alice.location is w.oubliette
