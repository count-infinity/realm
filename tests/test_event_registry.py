"""
Events: one declaration per action type (KERNEL_PLAN 6.2).
"""

from __future__ import annotations

import textwrap
import uuid

import pytest

from realm.core.eventdefs import installed
from realm.features import install_default
from realm.permissions.locks import check_lock, set_lock
from realm.testing import Simulator

# Frozen from scripting/triggers.py::STANDARD_EVENTS before it was deleted.
STANDARD_HOOKS = {
    'ENTER', 'LEAVE', 'ARRIVE', 'FAIL', 'LOOK', 'USE', 'PUSH', 'GET', 'DROP',
    'GIVE', 'RECEIVE', 'PUT', 'WEAR', 'REMOVE', 'WIELD', 'UNWIELD', 'OPEN',
    'CLOSE', 'LOCK', 'UNLOCK', 'ATTACK', 'DAMAGE', 'HITPRCNT', 'DEATH', 'CAST',
    'LOAD', 'EXPIRE', 'RESET', 'TICK', 'CONNECT', 'DISCONNECT', 'PAYMENT',
}

# Frozen from permissions/locks.py::TARGET_ACTION_LOCKS / TOOL_ACTION_LOCKS.
TARGET_LOCKS = {
    "item:on_get": ("basic", "You can't pick up {name}."),
    "item:on_drop": ("drop", "You can't drop {name}."),
    "item:on_put": ("enter", "You can't put things in {name}."),
    "event:speech": ("speech", "You can't speak here."),
    "event:shout": ("speech", "You can't speak here."),
    "event:ooc": ("speech", "You can't speak here."),
    "event:emote": ("speech", "You can't emote here."),
    "event:semipose": ("speech", "You can't emote here."),
    "event:emit": ("speech", "You can't emit here."),
}
TOOL_LOCKS = {"item:on_give": ("give", "You can't give {name} away.")}


@pytest.fixture(autouse=True)
def restore_default():
    yield
    install_default()


def test_classic_hooks_equal_the_old_table():
    # Step 8 added the kernel's pool hooks after the freeze.
    assert set(installed().hooks()) == STANDARD_HOOKS | {'POOL', 'SPENT'}


def test_lock_rows_equal_the_old_tables():
    events = installed().events()
    assert {e.action_type: e.target_lock for e in events if e.target_lock} == TARGET_LOCKS
    assert {e.action_type: e.tool_lock for e in events if e.tool_lock} == TOOL_LOCKS


def test_undeclared_types_still_fire_their_derived_hook():
    assert installed().hook_for("event:on_rumble") == "RUMBLE"
    assert installed().hook_for("item:on_get") == "GET"


HEIST = '''
from realm.features import Feature

feature = Feature("{name}")
feature.event("heist:on_crack", hook="CRACK", doc="a safe is cracked",
              payload={{"tool": "the drill"}},
              target_lock=("crack", "{{name}} holds."))
'''


async def test_a_feature_event_fires_its_hook_locks_and_lists(tmp_path, monkeypatch):
    name = f"kp_heist_{uuid.uuid4().hex[:8]}"
    (tmp_path / f"{name}.py").write_text(textwrap.dedent(HEIST.format(name=name)))
    monkeypatch.syspath_prepend(str(tmp_path))
    sim = Simulator(features=["basics", "talk", "look", "building", name])
    try:
        room = sim.room("Vault")
        thief = sim.player("Thief", location=room)
        thief.add_tag("builder")
        safe = sim.obj("safe", location=room)
        safe.db.set("ON_CRACK", "set_attr(me, 'cracked', adata('tool'))")

        from realm.core.propagation import Action, propagate
        await propagate(Action(actor=thief, target=safe, action_type="heist:on_crack",
                               extra={"tool": "drill"}))
        assert safe.db.get("cracked") == "drill"

        set_lock(safe, "crack", "False")
        assert check_lock(safe, "crack", thief) is False
        blocked = Action(actor=thief, target=safe, action_type="heist:on_crack")
        await propagate(blocked)
        assert blocked.blocked and blocked.block_reason == "safe holds."

        await sim.do(thief, "@events")
        listing = "\n".join(sim.seen(thief))
        assert "ON_CRACK" in listing and name in listing
    finally:
        sim.close()
