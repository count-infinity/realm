"""
Tests for the softcode-builder loop: unified safe-eval, script
actuators (move/trigger), ScriptTickerBehavior, and the @behavior /
@clone / @tr commands.

The scenario these enable is the MUSH classic — a builder assembles a
wandering NPC entirely in-game:

    @clone guard
    @behavior guard-2 = script_ticker, interval:4
    @set guard-2/on_tick = move(...)
"""

from __future__ import annotations

import pytest

from realm.behaviors.ticker import ScriptTickerBehavior
from realm.commands.olc.softcode import cmd_behavior, cmd_clone, cmd_trigger
from realm.core.objects import GameObject
from realm.core.propagation import reset_engine
from realm.core.safe_eval import eval_bool, eval_expression, validate_code
from realm.gateway.session import Session
from realm.scripting.engine import (
    ScriptEngine,
    get_script_engine,
    set_script_engine,
)
from tests.test_olc import MockPersistence, make_context, use_persistence

# --- Helpers -----------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_world():
    """Fresh propagation singleton and no ambient script engine."""
    reset_engine()
    set_script_engine(None)
    yield
    set_script_engine(None)
    reset_engine()


def make_rooms():
    """Two rooms joined by an 'east' exit; returns (west, east, exit)."""
    west = GameObject("West Hall", tags=["room"])
    east = GameObject("East Hall", tags=["room"])
    exit_obj = GameObject("east", tags=["exit"], location=west)
    exit_obj.db.destination_obj = east
    return west, east, exit_obj


def make_player(name: str, location: GameObject) -> tuple[GameObject, Session]:
    player = GameObject(name=name, location=location)
    player.add_tag("player")
    player.add_tag("builder")
    sess = Session(protocol="test", address="127.0.0.1")
    sess.link_player(player)
    return player, sess


def drain(sess: Session) -> list[str]:
    out: list[str] = []
    while not sess._output_queue.empty():
        out.append(sess._output_queue.get_nowait())
    return out


# --- Unified safe-eval --------------------------------------------------------


class TestSafeEval:

    def test_valid_expression(self):
        assert eval_expression("1 + 2", {}) == 3

    def test_namespace_layering(self):
        assert eval_expression("max(hp, 5)", {"hp": 12}) == 12

    def test_eval_bool_fail_closed_on_bad_syntax(self):
        assert eval_bool("this is not python", {}) is False

    def test_eval_bool_fail_closed_on_runtime_error(self):
        assert eval_bool("missing_name > 3", {}) is False

    def test_forbidden_import(self):
        assert validate_code("import os", mode="exec")

    def test_getattr_forbidden_in_expressions(self):
        # The lock validator historically allowed getattr; the unified
        # engine closes that hole.
        errors = validate_code("getattr(caller, 'id')", mode="eval")
        assert any("getattr" in e for e in errors)

    def test_private_attribute_forbidden(self):
        assert validate_code("caller._secret", mode="eval")

    def test_lock_uses_unified_validator(self):
        from realm.permissions.locks import Lock

        valid, error = Lock("basic", "getattr(caller, 'db')").validate()
        assert valid is False
        assert "getattr" in error

    def test_lock_still_evaluates(self):
        from realm.permissions.locks import check_lock

        room = GameObject("Vault", tags=["room"])
        alice = GameObject("Alice")
        alice.add_tag("keyholder")
        room.locks["enter"] = "caller.has_tag('keyholder')"
        assert check_lock(room, "enter", alice) is True

    def test_strategy_condition_uses_unified_engine(self):
        from realm.combat.strategy import _evaluate_condition

        assert _evaluate_condition("hp < 5", {"hp": 3}) is True
        assert _evaluate_condition("__import__('os')", {"hp": 3}) is False


# --- Script actuators: move + trigger ------------------------------------------


@pytest.mark.asyncio
class TestScriptedMove:

    async def test_move_walks_the_exit(self):
        west, east, _exit = make_rooms()
        critter = GameObject("critter", location=west)

        engine = ScriptEngine()
        await engine._run_script_command(critter, "move east")

        assert critter.location is east

    async def test_move_partial_exit_name(self):
        west, east, exit_obj = make_rooms()
        exit_obj.name = "fire escape"
        critter = GameObject("critter", location=west)

        engine = ScriptEngine()
        await engine._run_script_command(critter, "move fire")

        assert critter.location is east

    async def test_move_respects_locks(self):
        west, east, exit_obj = make_rooms()
        exit_obj.locks["basic"] = "False"
        critter = GameObject("critter", location=west)

        engine = ScriptEngine()
        await engine._run_script_command(critter, "move east")

        assert critter.location is west

    async def test_move_unknown_exit_is_noop(self):
        west, _east, _exit = make_rooms()
        critter = GameObject("critter", location=west)

        engine = ScriptEngine()
        await engine._run_script_command(critter, "move up")

        assert critter.location is west

    async def test_sandbox_move_helper_end_to_end(self):
        """A Python on_tick picking a random exit actually moves the NPC."""
        west, east, _exit = make_rooms()
        critter = GameObject("critter", location=west)
        critter.db.on_tick = (
            "exits = [e for e in contents(here) if has_tag(e, 'exit')]\n"
            "if exits: move(name(exits[rand(0, len(exits) - 1)]))"
        )

        engine = ScriptEngine()
        fired = await engine.run_object_script(critter, "on_tick")

        assert fired is True
        assert critter.location is east


@pytest.mark.asyncio
class TestRunObjectScript:

    async def test_named_script_fires(self):
        room = GameObject("Cantina", tags=["room"])
        npc = GameObject("Zeke", location=room)
        npc.db.battle_cry = "say To arms!"
        _alice, sess = make_player("Alice", room)

        engine = ScriptEngine()
        from realm.core.propagation import get_engine
        get_engine().add_observer(engine.handle_action)

        fired = await engine.run_object_script(npc, "battle_cry")

        assert fired is True
        assert 'Zeke says, "To arms!"' in drain(sess)

    async def test_missing_attr_returns_false(self):
        npc = GameObject("Zeke")
        engine = ScriptEngine()
        assert await engine.run_object_script(npc, "nothing_here") is False

    async def test_halt_tag_blocks(self):
        npc = GameObject("Zeke")
        npc.db.battle_cry = "say To arms!"
        npc.add_tag("halt")
        engine = ScriptEngine()
        assert await engine.run_object_script(npc, "battle_cry") is False

    async def test_attr_lookup_case_insensitive(self):
        npc = GameObject("Zeke")
        npc.db.ON_TICK = "say tick"
        engine = ScriptEngine()
        assert await engine.run_object_script(npc, "on_tick") is True

    async def test_trigger_chains_to_neighbor(self):
        room = GameObject("Cantina", tags=["room"])
        bell = GameObject("bell", location=room)
        crier = GameObject("crier", location=room)
        bell.db.on_ring = "trigger crier/announce"
        crier.db.announce = "say Hear ye!"
        _alice, sess = make_player("Alice", room)

        engine = ScriptEngine()
        from realm.core.propagation import get_engine
        get_engine().add_observer(engine.handle_action)

        await engine.run_object_script(bell, "on_ring")

        assert 'crier says, "Hear ye!"' in drain(sess)

    async def test_self_trigger_loop_is_depth_capped(self):
        room = GameObject("Cantina", tags=["room"])
        loop = GameObject("loop", location=room)
        loop.db.forever = "trigger me/forever"

        engine = ScriptEngine()
        # Must terminate rather than recurse forever.
        assert await engine.run_object_script(loop, "forever") is True


# --- ScriptTickerBehavior -------------------------------------------------------


@pytest.mark.asyncio
class TestScriptTicker:

    async def test_ticker_runs_on_tick_softcode(self):
        west, east, _exit = make_rooms()
        critter = GameObject("critter", location=west)
        critter.db.on_tick = "move east"
        critter.add_behavior(ScriptTickerBehavior(interval=1))

        set_script_engine(ScriptEngine())

        for behavior in critter.get_behaviors():
            await behavior.tick(critter, 4.0)

        assert critter.location is east

    async def test_ticker_honors_interval_countdown(self):
        room = GameObject("Cantina", tags=["room"])
        npc = GameObject("Zeke", location=room)
        npc.db.on_tick = "say tick"
        ticker = ScriptTickerBehavior(interval=3)
        npc.add_behavior(ticker)
        _alice, sess = make_player("Alice", room)

        engine = ScriptEngine()
        from realm.core.propagation import get_engine
        get_engine().add_observer(engine.handle_action)
        set_script_engine(engine)

        heard = 0
        for _ in range(6):
            await ticker.tick(npc, 4.0)
            heard += sum('says, "tick"' in m for m in drain(sess))

        # interval=3 → fires on pulses 1 and 4 of 6.
        assert heard == 2

    async def test_ticker_without_engine_is_noop(self):
        npc = GameObject("Zeke")
        npc.db.on_tick = "say tick"
        ticker = ScriptTickerBehavior(interval=1)
        npc.add_behavior(ticker)

        assert get_script_engine() is None
        await ticker.tick(npc, 4.0)  # must not raise

    async def test_ticker_survives_serialization(self):
        npc = GameObject("Zeke")
        npc.add_behavior(ScriptTickerBehavior(interval=7, attr="brain"))

        from realm.core.behaviors import BehaviorRegistry
        data = npc.get_behaviors()[0].to_dict()
        revived = BehaviorRegistry.from_dict(data)

        assert isinstance(revived, ScriptTickerBehavior)
        assert revived.get_param("interval") == 7
        assert revived.get_param("attr") == "brain"


# --- Builder commands -------------------------------------------------------------


@pytest.mark.asyncio
class TestBehaviorCommand:

    def setup_method(self):
        self.persistence = MockPersistence()
        use_persistence(self.persistence)

    async def test_attach_with_params(self):
        room = GameObject("Workshop", tags=["room"])
        player = GameObject("Bob", location=room)
        player.add_tag("player")
        player.add_tag("builder")
        parrot = GameObject("parrot", location=room)

        ctx = make_context(player, left_args="parrot",
                           right_args="script_ticker, interval:8")
        await cmd_behavior(ctx)

        behaviors = parrot.get_behaviors()
        assert len(behaviors) == 1
        assert behaviors[0].behavior_id == "script_ticker"
        assert behaviors[0].get_param("interval") == 8
        assert parrot in self.persistence.saved

    async def test_unknown_behavior_rejected(self):
        room = GameObject("Workshop", tags=["room"])
        player = GameObject("Bob", location=room)
        player.add_tag("player")
        player.add_tag("builder")
        GameObject("parrot", location=room)

        ctx = make_context(player, left_args="parrot", right_args="frobnicator")
        await cmd_behavior(ctx)

        assert any("Unknown behavior" in m for m in ctx.session.messages)

    async def test_list_and_remove(self):
        room = GameObject("Workshop", tags=["room"])
        player = GameObject("Bob", location=room)
        player.add_tag("player")
        player.add_tag("builder")
        parrot = GameObject("parrot", location=room)
        parrot.add_behavior(ScriptTickerBehavior(interval=2))

        ctx = make_context(player, left_args="parrot")
        await cmd_behavior(ctx)
        assert any("script_ticker" in m for m in ctx.session.messages)

        ctx = make_context(player, left_args="parrot",
                           right_args="script_ticker", switches=["remove"])
        await cmd_behavior(ctx)
        assert parrot.get_behaviors() == []


@pytest.mark.asyncio
class TestCloneCommand:

    def setup_method(self):
        self.persistence = MockPersistence()
        use_persistence(self.persistence)

    async def test_clone_copies_everything(self):
        room = GameObject("Workshop", tags=["room"])
        player = GameObject("Bob", location=room)
        player.add_tag("player")
        player.add_tag("builder")
        guard = GameObject("guard", location=room, tags=["npc", "spawned:door"])
        guard.description = "A stern guard."
        guard.db.hp = 12
        guard.db.on_tick = "say Halt!"
        guard.locks["basic"] = "False"
        guard.add_behavior(ScriptTickerBehavior(interval=4))

        ctx = make_context(player, left_args="guard")
        await cmd_clone(ctx)

        clones = [o for o in room.contents
                  if o.name == "guard" and o is not guard]
        assert len(clones) == 1
        clone = clones[0]
        assert clone.description == "A stern guard."
        assert clone.db.get("hp") == 12
        assert clone.db.get("on_tick") == "say Halt!"
        assert clone.has_tag("npc")
        assert not clone.has_tag("spawned:door")  # bookkeeping stripped
        assert clone.locks.get("basic") == "False"
        assert clone.get_behaviors()[0].behavior_id == "script_ticker"
        assert clone in self.persistence.saved

    async def test_clone_with_rename(self):
        room = GameObject("Workshop", tags=["room"])
        player = GameObject("Bob", location=room)
        player.add_tag("player")
        player.add_tag("builder")
        GameObject("guard", location=room, tags=["npc"])

        ctx = make_context(player, left_args="guard", right_args="guard two")
        await cmd_clone(ctx)

        assert any(o.name == "guard two" for o in room.contents)

    async def test_cannot_clone_players(self):
        room = GameObject("Workshop", tags=["room"])
        player = GameObject("Bob", location=room)
        player.add_tag("player")
        player.add_tag("builder")

        ctx = make_context(player, left_args="me")
        await cmd_clone(ctx)

        assert any("can't clone" in m.lower() for m in ctx.session.messages)


@pytest.mark.asyncio
class TestTriggerCommand:

    def setup_method(self):
        self.persistence = MockPersistence()
        use_persistence(self.persistence)

    async def test_tr_fires_named_script(self):
        room = GameObject("Workshop", tags=["room"])
        player = GameObject("Bob", location=room)
        player.add_tag("player")
        player.add_tag("builder")
        parrot = GameObject("parrot", location=room)
        parrot.db.battle_cry = "say Awk! To arms!"

        set_script_engine(ScriptEngine())
        ctx = make_context(player, args="parrot/battle_cry")
        await cmd_trigger(ctx)

        assert any("Triggered parrot/battle_cry" in m for m in ctx.session.messages)

    async def test_tr_reports_missing_script(self):
        room = GameObject("Workshop", tags=["room"])
        player = GameObject("Bob", location=room)
        player.add_tag("player")
        player.add_tag("builder")
        GameObject("parrot", location=room)

        set_script_engine(ScriptEngine())
        ctx = make_context(player, args="parrot/battle_cry")
        await cmd_trigger(ctx)

        assert any("no script" in m for m in ctx.session.messages)

    async def test_tr_without_engine(self):
        room = GameObject("Workshop", tags=["room"])
        player = GameObject("Bob", location=room)
        player.add_tag("player")
        player.add_tag("builder")

        ctx = make_context(player, args="me/foo")
        await cmd_trigger(ctx)

        assert any("not enabled" in m for m in ctx.session.messages)


# --- Permissions on softcode ---------------------------------------------------


class TestControls:

    def test_self_and_owner(self):
        from realm.permissions.locks import controls

        alice = GameObject("Alice", tags=["player"])
        rock = GameObject("rock", owner=alice)
        assert controls(alice, alice) is True
        assert controls(alice, rock) is True

    def test_plain_player_denied_on_others(self):
        from realm.permissions.locks import controls

        alice = GameObject("Alice", tags=["player"])
        bob = GameObject("Bob", tags=["player"])
        rock = GameObject("rock", owner=bob)
        assert controls(alice, rock) is False
        assert controls(alice, bob) is False

    def test_roles(self):
        from realm.permissions.locks import controls

        bob = GameObject("Bob", tags=["player"])
        rock = GameObject("rock", owner=bob)
        world_prop = GameObject("fountain")

        builder = GameObject("Bea", tags=["player", "builder"])
        assert controls(builder, world_prop) is True  # unowned = staff territory
        assert controls(builder, rock) is False       # owned by someone else

        admin = GameObject("Ada", tags=["player", "admin"])
        assert controls(admin, rock) is True

    def test_world_trusts_world(self):
        from realm.permissions.locks import controls

        bell = GameObject("bell")
        crier = GameObject("crier")
        alice = GameObject("Alice", tags=["player"])
        assert controls(bell, crier) is True    # unowned NPC ↔ unowned prop
        assert controls(bell, alice) is False   # never players

    def test_control_lock_grant(self):
        from realm.permissions.locks import controls

        bob = GameObject("Bob", tags=["player"])
        alice = GameObject("Alice", tags=["player"])
        alice.add_tag("trusted")
        rock = GameObject("rock", owner=bob)
        rock.locks["control"] = "caller.has_tag('trusted')"
        assert controls(alice, rock) is True


@pytest.mark.asyncio
class TestCommandAuthority:

    def setup_method(self):
        self.persistence = MockPersistence()
        use_persistence(self.persistence)

    async def test_plain_player_cannot_set_others(self):
        from realm.commands.olc.modify import cmd_set

        room = GameObject("Plaza", tags=["room"])
        bob = GameObject("Bob", tags=["player"], location=room)
        rock = GameObject("rock", location=room, owner=GameObject("Owner"))

        ctx = make_context(bob, left_args="rock/hp", right_args="999")
        await cmd_set(ctx)

        assert rock.db.get("hp") is None
        assert any("don't control" in m for m in ctx.session.messages)

    async def test_owner_can_set_their_own(self):
        from realm.commands.olc.modify import cmd_set

        room = GameObject("Plaza", tags=["room"])
        bob = GameObject("Bob", tags=["player"], location=room)
        rock = GameObject("rock", location=room, owner=bob)

        ctx = make_context(bob, left_args="rock/hp", right_args="5")
        await cmd_set(ctx)

        assert rock.db.get("hp") == 5

    async def test_tr_denied_without_control(self):
        room = GameObject("Plaza", tags=["room"])
        bob = GameObject("Bob", tags=["player"], location=room)
        parrot = GameObject("parrot", location=room, owner=GameObject("Owner"))
        parrot.db.cry = "say Awk!"

        set_script_engine(ScriptEngine())
        ctx = make_context(bob, args="parrot/cry")
        await cmd_trigger(ctx)

        assert any("don't control" in m for m in ctx.session.messages)

    async def test_tr_allowed_by_command_lock(self):
        room = GameObject("Plaza", tags=["room"])
        bob = GameObject("Bob", tags=["player"], location=room)
        bell = GameObject("bell", location=room, owner=GameObject("Owner"))
        bell.db.ring = "say Bong!"
        bell.locks["command"] = "True"  # trigger_ok

        set_script_engine(ScriptEngine())
        ctx = make_context(bob, args="bell/ring")
        await cmd_trigger(ctx)

        assert any("Triggered bell/ring" in m for m in ctx.session.messages)


@pytest.mark.asyncio
class TestTriggerLocks:

    async def test_use_lock_gates_dollar_commands(self):
        from realm.core.propagation import get_engine
        from realm.server.dispatcher import CommandContext

        room = GameObject("Cantina", tags=["room"])
        npc = GameObject("Zeke", location=room)
        npc.db.cmd_greet = "$greet*:say Welcome!"
        npc.locks["use"] = "caller.has_tag('regular')"
        alice, sess = make_player("Alice", room)
        alice.remove_tag("builder")

        engine = ScriptEngine()
        get_engine().add_observer(engine.handle_action)
        ctx = CommandContext(session=sess, player=alice, raw_input="greet",
                             command_name="greet", args="")

        assert await engine.handle_unknown_command(ctx) is False

        alice.add_tag("regular")
        assert await engine.handle_unknown_command(ctx) is True

    async def test_listen_lock_gates_overhearing(self):
        room = GameObject("Cantina", tags=["room"])
        spy = GameObject("spy", location=room)
        spy.db.listen_all = "^*treasure*:say I heard that!"
        spy.locks["listen"] = "False"
        alice, sess = make_player("Alice", room)

        engine = ScriptEngine()
        from realm.core.propagation import get_engine
        get_engine().add_observer(engine.handle_action)

        await engine.handle_speech(alice, "the treasure is buried", room)
        assert not any("I heard that" in m for m in drain(sess))

    async def test_script_cross_trigger_needs_authority(self):
        room = GameObject("Cantina", tags=["room"])
        owner = GameObject("Owner", tags=["player"])
        bell = GameObject("bell", location=room)
        crier = GameObject("crier", location=room, owner=owner)
        bell.db.on_ring = "trigger crier/announce"
        crier.db.announce = "say Hear ye!"
        _alice, sess = make_player("Alice", room)

        engine = ScriptEngine()
        from realm.core.propagation import get_engine
        get_engine().add_observer(engine.handle_action)

        await engine.run_object_script(bell, "on_ring")
        assert not any("Hear ye" in m for m in drain(sess))

        crier.locks["command"] = "True"
        await engine.run_object_script(bell, "on_ring")
        assert any("Hear ye" in m for m in drain(sess))


# --- The engine API for softcode -------------------------------------------------


@pytest.mark.asyncio
class TestEngineApi:

    def setup_method(self):
        self.persistence = MockPersistence()
        use_persistence(self.persistence)

    async def test_script_creates_object(self):
        room = GameObject("Workshop", tags=["room"])
        smith = GameObject("smith", location=room)
        smith.db.on_forge = "sword = create_obj('iron sword')\nsay('The sword is done!')"

        engine = ScriptEngine(persistence=self.persistence)
        await engine.run_object_script(smith, "on_forge")

        swords = [o for o in room.contents if o.name == "iron sword"]
        assert len(swords) == 1
        assert swords[0].owner is smith
        assert swords[0] in self.persistence.saved  # queued save landed

    async def test_script_cannot_mutate_players(self):
        room = GameObject("Workshop", tags=["room"])
        npc = GameObject("imp", location=room)
        alice, _sess = make_player("Alice", room)
        alice.db.hp = 10
        npc.db.on_curse = "set_attr('Alice', 'hp', 0)\nadd_tag('Alice', 'cursed')"

        engine = ScriptEngine(persistence=self.persistence)
        self.persistence.add(alice)
        await engine.run_object_script(npc, "on_curse")

        assert alice.db.get("hp") == 10
        assert not alice.has_tag("cursed")

    async def test_script_destroys_own_creation(self):
        room = GameObject("Workshop", tags=["room"])
        smith = GameObject("smith", location=room)
        smith.db.on_cleanup = "junk = create_obj('slag')\ndestroy_obj(junk)"

        engine = ScriptEngine(persistence=self.persistence)
        await engine.run_object_script(smith, "on_cleanup")

        assert not any(o.name == "slag" for o in room.contents)
        assert any(o.name == "slag" for o in self.persistence.deleted)

    async def test_script_teleports_prop_not_through_lock(self):
        room = GameObject("Workshop", tags=["room"])
        vault = GameObject("Vault", tags=["room"])
        smith = GameObject("smith", location=room)
        prop = GameObject("anvil", location=room)
        self.persistence.add(vault)
        self.persistence.add(prop)

        smith.db.on_move = "teleport_obj('anvil', 'Vault')"
        engine = ScriptEngine(persistence=self.persistence)

        vault.locks["teleport"] = "False"
        await engine.run_object_script(smith, "on_move")
        assert prop.location is room  # teleport lock held

        del vault.locks["teleport"]
        await engine.run_object_script(smith, "on_move")
        assert prop.location is vault

    async def test_script_attaches_behavior(self):
        room = GameObject("Workshop", tags=["room"])
        smith = GameObject("smith", location=room)
        golem = GameObject("golem", location=room)
        self.persistence.add(golem)
        smith.db.on_awaken = (
            "attach_behavior('golem', 'script_ticker', interval=5)\n"
            "set_attr('golem', 'on_tick', 'say ...crunch...')"
        )

        engine = ScriptEngine(persistence=self.persistence)
        await engine.run_object_script(smith, "on_awaken")

        assert [b.behavior_id for b in golem.get_behaviors()] == ["script_ticker"]
        assert golem.db.get("on_tick") == "say ...crunch..."

    async def test_exits_function(self):
        west, _east, exit_obj = make_rooms()
        scout = GameObject("scout", location=west)
        scout.db.on_scan = "n = len(exits(here))\nsay(str(n) + ' exit(s)')"
        _alice, sess = make_player("Alice", west)

        engine = ScriptEngine()
        from realm.core.propagation import get_engine
        get_engine().add_observer(engine.handle_action)
        await engine.run_object_script(scout, "on_scan")

        assert any("1 exit(s)" in m for m in drain(sess))


# --- Combat channels, locks, verbs, waits (tranche 3) ---------------------------


class FakeCombatManager:
    def __init__(self):
        self.deaths = []
        self.fights = []

    async def handle_death(self, obj, killer=None):
        self.deaths.append((obj, killer))

    async def initiate(self, attacker, target):
        self.fights.append((attacker, target))


@pytest.fixture
def fake_combat():
    from realm.combat.manager import set_combat_manager
    manager = FakeCombatManager()
    set_combat_manager(manager)
    yield manager
    set_combat_manager(None)


@pytest.mark.asyncio
class TestCombatChannels:

    async def test_trap_damages_and_death_routes_to_manager(self, fake_combat):
        room = GameObject("Pit", tags=["room"])
        trap = GameObject("dart trap", location=room)
        rat = GameObject("rat", location=room)
        rat.db.hp = 2
        rat.db.max_hp = 5
        trap.db.on_spring = "damage('rat', 3)"

        engine = ScriptEngine()
        await engine.run_object_script(trap, "on_spring")

        assert rat.db.get("hp") == -1
        assert fake_combat.deaths == [(rat, trap)]

    async def test_damage_out_of_reach_fails(self, fake_combat):
        room = GameObject("Pit", tags=["room"])
        elsewhere = GameObject("Away", tags=["room"])
        trap = GameObject("dart trap", location=room)
        rat = GameObject("rat", location=elsewhere)
        rat.db.hp = 5

        from realm.scripting.functions import ScriptFunctions
        funcs = ScriptFunctions(executor=trap)
        assert funcs.damage(rat, 3) is False
        assert rat.db.get("hp") == 5

    async def test_heal_caps_at_max(self):
        room = GameObject("Chapel", tags=["room"])
        cleric = GameObject("cleric", location=room)
        rat = GameObject("rat", location=room)
        rat.db.hp = 4
        rat.db.max_hp = 5

        from realm.scripting.functions import ScriptFunctions
        funcs = ScriptFunctions(executor=cleric)
        assert funcs.heal(rat, 10) is True
        assert rat.db.get("hp") == 5

    async def test_start_combat_queues_initiate(self, fake_combat):
        room = GameObject("Arena", tags=["room"])
        handler = GameObject("beast handler", location=room)
        beast = GameObject("beast", location=room, owner=handler)
        alice, _sess = make_player("Alice", room)
        handler.db.on_release = "start_combat('beast', 'Alice')"

        engine = ScriptEngine()
        await engine.run_object_script(handler, "on_release")

        assert fake_combat.fights == [(beast, alice)]

    async def test_start_combat_needs_control(self, fake_combat):
        room = GameObject("Arena", tags=["room"])
        imp = GameObject("imp", location=room)
        alice, _sess = make_player("Alice", room)
        bob = GameObject("Bob", tags=["player"], location=room)
        imp.db.on_meddle = "start_combat('Alice', 'Bob')"

        engine = ScriptEngine()
        await engine.run_object_script(imp, "on_meddle")

        assert fake_combat.fights == []  # can't puppet players into fights


@pytest.mark.asyncio
class TestScriptLocks:

    async def test_script_sets_working_lock(self):
        room = GameObject("Hall", tags=["room"])
        warden = GameObject("warden", location=room)
        door = GameObject("door", location=room, tags=["exit"])

        from realm.scripting.functions import ScriptFunctions
        funcs = ScriptFunctions(executor=warden)
        assert funcs.set_lock(door, "basic", "caller.has_tag('warden_pass')") is True
        assert funcs.test_lock(door, "basic") is False  # warden has no pass

        warden.add_tag("warden_pass")
        assert funcs.test_lock(door, "basic") is True
        assert funcs.clear_lock(door, "basic") is True

    async def test_bad_expression_rejected(self):
        room = GameObject("Hall", tags=["room"])
        warden = GameObject("warden", location=room)
        door = GameObject("door", location=room)

        from realm.scripting.functions import ScriptFunctions
        funcs = ScriptFunctions(executor=warden)
        assert funcs.set_lock(door, "basic", "getattr(caller, 'id')") is False
        assert "basic" not in door.locks

    async def test_set_lock_needs_control(self):
        room = GameObject("Hall", tags=["room"])
        imp = GameObject("imp", location=room)
        alice, _sess = make_player("Alice", room)

        from realm.scripting.functions import ScriptFunctions
        funcs = ScriptFunctions(executor=imp)
        assert funcs.set_lock(alice, "basic", "False") is False


@pytest.mark.asyncio
class TestScriptedVerbs:

    async def test_get_and_drop(self):
        room = GameObject("Vault", tags=["room"])
        imp = GameObject("imp", location=room)
        coin = GameObject("coin", location=room, tags=["thing"])

        engine = ScriptEngine()
        await engine._run_script_command(imp, "get coin")
        assert coin.location is imp

        await engine._run_script_command(imp, "drop coin")
        assert coin.location is room

    async def test_get_respects_basic_lock(self):
        room = GameObject("Vault", tags=["room"])
        imp = GameObject("imp", location=room)
        gem = GameObject("gem", location=room, tags=["thing"])
        gem.locks["basic"] = "False"

        engine = ScriptEngine()
        await engine._run_script_command(imp, "get gem")
        assert gem.location is room

    async def test_give_hands_item_over(self):
        room = GameObject("Vault", tags=["room"])
        imp = GameObject("imp", location=room)
        coin = GameObject("coin", location=imp, tags=["thing"])
        alice, sess = make_player("Alice", room)

        engine = ScriptEngine()
        await engine._run_script_command(imp, "give coin = Alice")
        assert coin.location is alice
        assert any("imp gives you" in m for m in drain(sess))

    async def test_open_and_close(self):
        room = GameObject("Vault", tags=["room"])
        imp = GameObject("imp", location=room)
        chest = GameObject("chest", location=room, tags=["thing", "closed"])
        chest.db.container = True

        engine = ScriptEngine()
        await engine._run_script_command(imp, "open chest")
        assert not chest.has_tag("closed")

        await engine._run_script_command(imp, "close chest")
        assert chest.has_tag("closed")

    async def test_open_locked_stays_shut(self):
        room = GameObject("Vault", tags=["room"])
        imp = GameObject("imp", location=room)
        chest = GameObject("chest", location=room, tags=["thing", "closed"])
        chest.db.container = True
        chest.db.locked = True

        engine = ScriptEngine()
        await engine._run_script_command(imp, "open chest")
        assert chest.has_tag("closed")


@pytest.mark.asyncio
class TestWaits:

    async def test_python_wait_fires_on_heartbeat(self):
        room = GameObject("Stage", tags=["room"])
        crier = GameObject("crier", location=room)
        crier.db.on_cue = "wait(0, 'say Hear ye, later!')"
        _alice, sess = make_player("Alice", room)

        engine = ScriptEngine()
        from realm.core.propagation import get_engine
        get_engine().add_observer(engine.handle_action)

        await engine.run_object_script(crier, "on_cue")
        assert not any("Hear ye, later" in m for m in drain(sess))  # not yet

        await engine.tick_waits()
        assert any("Hear ye, later" in m for m in drain(sess))

    async def test_simple_wait_command_form(self):
        room = GameObject("Stage", tags=["room"])
        crier = GameObject("crier", location=room)
        crier.db.on_cue = "wait 0 say Boom!"
        _alice, sess = make_player("Alice", room)

        engine = ScriptEngine()
        from realm.core.propagation import get_engine
        get_engine().add_observer(engine.handle_action)

        await engine.run_object_script(crier, "on_cue")
        await engine.tick_waits()
        assert any('crier says, "Boom!"' in m for m in drain(sess))

    async def test_halted_wait_does_not_fire(self):
        room = GameObject("Stage", tags=["room"])
        crier = GameObject("crier", location=room)
        _alice, sess = make_player("Alice", room)

        engine = ScriptEngine()
        from realm.core.propagation import get_engine
        get_engine().add_observer(engine.handle_action)

        engine.schedule_wait(crier, 0, "say Too late!")
        crier.add_tag("halt")
        await engine.tick_waits()
        assert not any("Too late" in m for m in drain(sess))

    async def test_future_wait_not_due_yet(self):
        crier = GameObject("crier")
        engine = ScriptEngine()
        engine.schedule_wait(crier, 300, "say Way later")
        await engine.tick_waits()
        assert len(engine._waits) == 1


# --- The banshee-wail pipeline: condition modifiers ------------------------------


@pytest.mark.asyncio
class TestConditionModifiers:

    async def test_attr_provider_sums_shapes(self):
        from realm.core.checks import condition_modifier

        bob = GameObject("Bob")
        bob.db.check_mods = {
            "fear": {"all": -2},
            "blinded": {"observation": -6},
            "blessed": 1,
        }
        assert condition_modifier(bob, "stealth") == -1     # -2 +1
        assert condition_modifier(bob, "observation") == -7  # -2 -6 +1

    async def test_check_folds_modifiers_before_resolver(self):
        from realm.core.checks import check, set_check_resolver

        seen = {}

        def recorder(obj, skill, modifier):
            seen["modifier"] = modifier
            from realm.core.checks import CheckResult
            return CheckResult(True, 0, 10, 10, skill)

        bob = GameObject("Bob")
        bob.db.check_mods = {"fear": {"all": -2}}
        set_check_resolver(recorder)
        try:
            check(bob, "stealth", modifier=1)
        finally:
            set_check_resolver(None)
        assert seen["modifier"] == -1  # explicit +1, fear -2

    async def test_modifier_effect_lifecycle(self):
        from realm.behaviors.effects import ModifierEffectBehavior
        from realm.core.checks import condition_modifier

        bob = GameObject("Bob", tags=["player"])
        effect = ModifierEffectBehavior(kind="fear", duration=2,
                                        check_mods={"all": -2})
        bob.add_behavior(effect)

        assert bob.has_tag("fear")
        assert condition_modifier(bob, "melee") == -2

        await effect.tick(bob, 4.0)   # duration 2 -> 1
        await effect.tick(bob, 4.0)   # expires
        assert not bob.has_tag("fear")
        assert condition_modifier(bob, "melee") == 0
        assert bob.get_behaviors() == []

    async def test_blinding_poison_composes(self):
        from realm.behaviors.effects import DamageOverTimeBehavior
        from realm.core.checks import condition_modifier

        bob = GameObject("Bob")
        bob.db.hp = 10
        bob.add_behavior(DamageOverTimeBehavior(
            kind="blinding_venom", damage=1, duration=5,
            check_mods={"observation": -6}))
        assert condition_modifier(bob, "observation") == -6
        assert condition_modifier(bob, "melee") == 0

    async def test_banshee_wail_end_to_end(self):
        from realm.core.checks import condition_modifier

        crypt = GameObject("Crypt", tags=["room"])
        banshee = GameObject("banshee", location=crypt)
        alice, sess = make_player("Alice", crypt)
        banshee.db.on_wail = (
            "apply_effect('Alice', 'modifier_effect', kind='fear', duration=8, "
            "check_mods={'all': -2}, apply_msg='Terror grips you!')"
        )

        engine = ScriptEngine()
        await engine.run_object_script(banshee, "on_wail")

        assert alice.has_tag("fear")
        assert condition_modifier(alice, "stealth") == -2
        assert any("Terror grips you" in m for m in drain(sess))

    async def test_apply_effect_out_of_reach_fails(self):
        crypt = GameObject("Crypt", tags=["room"])
        away = GameObject("Away", tags=["room"])
        banshee = GameObject("banshee", location=crypt)
        alice, _sess = make_player("Alice", away)

        from realm.scripting.functions import ScriptFunctions
        funcs = ScriptFunctions(executor=banshee)
        assert funcs.apply_effect(alice, "modifier_effect", kind="fear") is False
        assert not alice.has_tag("fear")

    async def test_remove_effect_cures(self):
        from realm.behaviors.effects import ModifierEffectBehavior
        from realm.core.checks import condition_modifier

        chapel = GameObject("Chapel", tags=["room"])
        cleric = GameObject("cleric", location=chapel)
        bob = GameObject("Bob", tags=["player"], location=chapel)
        bob.add_behavior(ModifierEffectBehavior(kind="fear", duration=0,
                                                check_mods={"all": -2}))

        from realm.scripting.functions import ScriptFunctions
        funcs = ScriptFunctions(executor=cleric)
        assert funcs.remove_effect(bob, "fear") is True
        assert not bob.has_tag("fear")
        assert condition_modifier(bob, "anything") == 0

    async def test_effect_survives_reboot_via_serialization(self):
        from realm.behaviors.effects import ModifierEffectBehavior
        from realm.core.behaviors import BehaviorRegistry
        from realm.core.checks import condition_modifier

        bob = GameObject("Bob")
        bob.add_behavior(ModifierEffectBehavior(kind="fear", duration=8,
                                                check_mods={"all": -2}))
        data = bob.get_behaviors()[0].to_dict()

        # A "rebooted" copy: attrs persisted, behavior rehydrated.
        clone = GameObject("Bob2")
        clone.db.check_mods = dict(bob.db.get("check_mods"))
        revived = BehaviorRegistry.from_dict(data)
        assert isinstance(revived, ModifierEffectBehavior)
        assert condition_modifier(clone, "melee") == -2


@pytest.mark.asyncio
class TestTier1AuthorityFixes:
    """Simplicity-review fixes: builder commands as strict as scripts."""

    def setup_method(self):
        self.persistence = MockPersistence()
        use_persistence(self.persistence)

    async def test_teleport_other_needs_control(self):
        from realm.commands.olc.admin import cmd_teleport

        room = GameObject("Plaza", tags=["room"])
        vault = GameObject("Vault", tags=["room"])
        self.persistence.add(vault)
        bob = GameObject("Bob", tags=["player", "builder"], location=room)
        prize = GameObject("prize", location=room, owner=GameObject("Owner"))
        self.persistence.add(prize)

        ctx = make_context(bob, args="prize = Vault", left_args="prize",
                           right_args="Vault")
        await cmd_teleport(ctx)
        assert prize.location is room
        assert any("don't control" in m for m in ctx.session.messages)

    async def test_destroy_needs_control(self):
        from realm.commands.olc.admin import cmd_destroy

        room = GameObject("Plaza", tags=["room"])
        bob = GameObject("Bob", tags=["player", "builder"], location=room)
        relic = GameObject("relic", location=room, owner=GameObject("Owner"))
        self.persistence.add(relic)

        ctx = make_context(bob, args="relic")
        await cmd_destroy(ctx)
        assert relic.location is room
        assert any("don't control" in m for m in ctx.session.messages)

    async def test_create_obj_cannot_seed_strangers_rooms(self):
        from realm.scripting.functions import ScriptFunctions

        here = GameObject("Here", tags=["room"])
        theirs = GameObject("Theirs", tags=["room"],
                            owner=GameObject("Owner", tags=["player"]))
        imp = GameObject("imp", location=here)

        funcs = ScriptFunctions(executor=imp, persistence=self.persistence)
        self.persistence.add(theirs)
        assert funcs.create_obj("bomb", location=theirs) is None
        assert funcs.create_obj("rock") is not None  # own room fine

    async def test_engine_floor_survives_system_swap(self):
        from realm.core.checks import (
            SKILL_DEFAULTS,
            set_skill_defaults,
        )
        saved = dict(SKILL_DEFAULTS)
        try:
            set_skill_defaults({"stealth": ("dexterity", -4)})
            assert SKILL_DEFAULTS["flee"] == ("dexterity", -2)  # floor kept
        finally:
            set_skill_defaults(saved)
