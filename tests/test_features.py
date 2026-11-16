"""
Features: built-ins use the front door (KERNEL_PLAN step 4).

A game is a list of features. What it leaves out is not registered, not
listed in help, not callable from softcode and not observing actions.
Collisions and unmet requirements raise.
"""

from __future__ import annotations

import textwrap
import uuid

import pytest

from realm.core.action_tags import HOSTILE
from realm.core.behaviors import Behavior, BehaviorRegistry
from realm.core.objects import GameObject
from realm.core.propagation import Action, propagate
from realm.core.world import get_world
from realm.features import Feature, FeatureError, FeatureSet, install_default, load
from realm.scripting.functions import ScriptFrame
from realm.testing import Simulator

# Frozen from the state after KERNEL_PLAN step 3 (2026-11-13).
COMMANDS = [
    '@areas', '@attr', '@behavior', '@boot', '@chown', '@clone', '@create', '@desc',
    '@destroy', '@detail', '@dig', '@eval', '@examine', '@export', '@find', '@force',
    '@foreach', '@import', '@keyid', '@link', '@lock', '@name', '@nuke', '@open', '@pack',
    '@pair', '@parent', '@reload', '@rolls', '@set', '@stats', '@tag', '@teleport', '@tr',
    '@unlink', '@unlock', '@untag', '@wipe', '@zone', 'attack', 'buy', 'cast', 'close',
    'color', 'combat', 'combatdefault', 'commands', 'consider', 'credits', 'defend', 'down',
    'drop', 'east', 'emit', 'examine', 'fasttalk', 'firstaid', 'flee', 'follow', 'get',
    'give', 'go', 'help', 'hide', 'improve', 'in', 'inventory', 'list', 'lock', 'logout',
    'look', 'north', 'northeast', 'northwest', 'ooc', 'open', 'out', 'pace', 'party', 'pay',
    'persuade', 'pick', 'points', 'pose', 'put', 'quell', 'queue', 'quit', 'recall',
    'remove', 'say', 'search', 'sell', 'semipose', 'shout', 'showrolls', 'south',
    'southeast', 'southwest', 'spells', 'think', 'time', 'unfollow', 'unlock', 'unquell',
    'unwield', 'up', 'uptime', 'use', 'wear', 'west', 'whisper', 'who', 'wield', 'wimpy',
]
SOFTCODE_NAMES = [
    'V', 'act', 'add_tag', 'adjust_credits', 'adjust_disposition', 'ansi', 'apply_effect',
    'attach_behavior', 'band', 'behaviors', 'call', 'cancel_wait', 'capstr', 'cast', 'ceil',
    'check', 'check_roll', 'clamp', 'clear_lock', 'contents', 'contest', 'controls',
    'create_obj', 'credits', 'damage', 'decr', 'del_attr', 'destroy_obj', 'detach_behavior',
    'dice', 'disposition', 'enactor', 'enter_instance', 'enter_wilderness', 'escape',
    'eval_attr', 'exits', 'expire', 'extract', 'first', 'floor', 'force', 'get', 'get_attr',
    'has_attr', 'has_entitlement', 'has_tag', 'heal', 'here', 'highest', 'if_else', 'incr',
    'last', 'lcfirst', 'left', 'loc', 'margin_over', 'margin_under', 'me', 'member', 'mid',
    'move_to', 'name', 'net_successes', 'now', 'oemit', 'oob', 'owner', 'pemit', 'prompt',
    'rand', 'reaction_roll', 'remit', 'remove_effect', 'remove_tag', 'repeat', 'replace',
    'rest', 'right', 'roll', 'search_world', 'set_attr', 'set_lock', 'setdiff', 'setinter',
    'setunion', 'skill', 'skill_check', 'start_combat', 'strlen', 'switch', 'tag_value',
    'tag_values', 'tags', 'teleport_obj', 'test_lock', 'transfer_credits', 'trim',
    'ucfirst', 'use_ability', 'wait', 'words', 'zone_rooms', 'zones_of',
]
OBSERVERS = [
    'realm.scripting.engine.ScriptEngine.handle_action',
    'realm.std.combat.manager.CombatManager.hostile_observer',
    'realm.std.crime.crime.crime_observer',
    'realm.std.rules.system.equipment_observer',
    'realm.std.stealth.stealth.stealth_observer',
]
BEHAVIOR_IDS = [
    'aggressive', 'caster', 'combatant', 'damage_over_time', 'decay', 'defensive',
    'disposition_boost', 'fleeing', 'guard', 'healer', 'modifier_effect', 'patrol',
    'peacekeeper', 'population', 'regeneration', 'restock', 'scavenger', 'script_ticker',
    'shopkeeper', 'spawner', 'steal', 'venomous', 'wandering', 'wanted', 'watchful',
    'zone_reset',
]

SOCIAL_GAME = ["basics", "talk", "movement", "look", "items", "building"]


def _qualname(fn) -> str:
    target = getattr(fn, "__func__", fn)
    return f"{target.__module__}.{target.__qualname__}"


@pytest.fixture(autouse=True)
def restore_default():
    yield
    install_default()


class TestDefaultEqualsToday:

    def test_classic_matches_the_frozen_state(self):
        sim = Simulator()
        try:
            # Step 6 added @events after the freeze; MUD_PLAN step 2 the
            # vitals positions, step 3 the sheet and the consumables.
            added_commands = {"@events", "rest", "sleep", "stand",
                              # MUD_PLAN step 3: the character sheet, consumables
                              "equipment", "skills", "prompt", "eat", "drink",
                              "quaff", "recite", "zap"}
            assert sorted(set(sim.dispatcher._commands) - added_commands) == COMMANDS
            names = set(ScriptFrame(persistence=sim.store).to_dict())
            # Step 5 added clone_obj, set_name and set_desc after the freeze;
            # step 8 the pool functions.
            added = {"clone_obj", "set_name", "set_desc", "pool", "pool_max", "has_pool",
                     "spent", "harm_pool", "mend_pool", "spend_pool"}
            assert sorted(names - added) == SOFTCODE_NAMES
            # Step 8 added combat's two vital-pool observers; MUD_PLAN step 2
            # combat's revive observer and the vitals feature's two.
            observers = {_qualname(o) for o in get_world().engine._observers} - {
                "realm.std.combat.vitals.death_observer",
                "realm.std.combat.vitals.threshold_observer",
                "realm.std.combat.vitals.revive_observer",
                "realm.std.vitals.regen.regen_observer",
                "realm.std.vitals.positions.roused_observer"}
            assert sorted(observers) == OBSERVERS
            # MUD_PLAN step 2 added the player corpse's claim.
            assert sorted(set(BehaviorRegistry.list_all()) - {"corpse_claim"}) == BEHAVIOR_IDS
        finally:
            sim.close()


class TestSubtract:

    @pytest.fixture
    def social(self):
        sim = Simulator(features=SOCIAL_GAME)
        try:
            yield sim
        finally:
            sim.close()

    async def test_left_out_commands_are_unknown_and_not_in_help(self, social):
        room = social.room("Plaza")
        alice = social.player("Alice", location=room)
        for command in ("attack", "buy", "cast", "wimpy", "improve"):
            assert social.dispatcher.get_command(command) is None
        await social.do(alice, "help")
        listing = "\n".join(social.seen(alice))
        assert "attack" not in listing and "wimpy" not in listing
        assert "say" in listing

    async def test_left_out_softcode_is_a_name_error(self, social):
        room = social.room("Plaza")
        npc = social.obj("clerk", location=room)
        for fn in ("credits", "damage", "start_combat"):
            _result, err = await social.eval(npc, f"result = {fn}")
            assert err is not None and fn in err

    async def test_no_combat_and_only_the_script_engine_observes(self, social):
        assert [_qualname(o) for o in get_world().engine._observers] == [
            "realm.scripting.engine.ScriptEngine.handle_action"]
        assert "combat" not in social.world.services
        room = social.room("Plaza")
        alice = social.player("Alice", location=room)
        bob = social.player("Bob", location=room)
        await propagate(Action(actor=alice, target=bob, action_type="event:shove",
                               tags={HOSTILE}))
        assert not alice.has_tag("in_combat") and not bob.has_tag("in_combat")

    def test_left_out_behaviors_are_unregistered(self, social):
        assert BehaviorRegistry.get("aggressive") is None
        assert BehaviorRegistry.get("script_ticker") is not None   # kernel

    def test_left_out_items_take_their_hooks_and_verbs(self):
        """KERNEL_PLAN 6: without items, ON_GET is not a known hook and
        `get` is not a script verb."""
        from realm.core.eventdefs import installed as installed_events
        from realm.scripting.verbs import installed as installed_verbs
        sim = Simulator(features=["basics", "talk", "movement", "look", "building"])
        try:
            assert "GET" not in installed_events().hooks()
            assert installed_verbs().match("get key") is None
            assert installed_verbs().match("say hi") is not None
        finally:
            sim.close()

    def test_closing_restores_every_builtin(self, social):
        social.close()
        assert BehaviorRegistry.get("aggressive") is not None


GAME_MODULE = '''
from realm.core.behaviors import Behavior
from realm.features import Feature

feature = Feature("{name}", requires=["basics"])


@feature.behavior
class Chime(Behavior):
    behavior_id = "{name}_chime"

    @property
    def should_tick(self):
        return True

    async def tick(self, obj, delta):
        obj.db.set("chimes", int(obj.db.get("chimes") or 0) + 1)


@feature.command("chime", category="game", help_text="Ring the chime")
async def cmd_chime(ctx):
    await ctx.session.send("Ding.")


@feature.function(readonly=True)
def chime_count(n):
    return n * 2


@feature.name_resolver
def masked(obj, looker, current):
    return obj.db.get("mask") or current


@feature.speech_renderer
def shout(body, action, looker):
    return body.upper()


@feature.group_formatter
def tally(obj, count):
    return f"{{obj.name}} x{{count}}"
'''


@pytest.fixture
def game_module(tmp_path, monkeypatch):
    name = f"kp_game_{uuid.uuid4().hex[:8]}"
    (tmp_path / f"{name}.py").write_text(textwrap.dedent(GAME_MODULE.format(name=name)))
    monkeypatch.syspath_prepend(str(tmp_path))
    return name


class TestGameFeature:

    async def test_command_behavior_and_function_work(self, game_module):
        sim = Simulator(features=["basics", "talk", game_module])
        try:
            room = sim.room("Hall")
            alice = sim.player("Alice", location=room)
            await sim.do(alice, "chime")
            assert "Ding." in sim.seen(alice)
            assert BehaviorRegistry.get(f"{game_module}_chime") is not None
            result, err = await sim.eval(room, "result = chime_count(21)")
            assert err is None and result == 42
        finally:
            sim.close()
        assert BehaviorRegistry.get(f"{game_module}_chime") is None

    async def test_presentation_hooks_reach_the_world(self, game_module):
        """name_resolver, speech_renderer and group_formatter declarations
        are the running world's, and leave with it."""
        sim = Simulator(features=["basics", "talk", "look", game_module])
        try:
            room = sim.room("Hall")
            alice = sim.player("Alice", location=room, mask="a masked figure")
            bob = sim.player("Bob", location=room)
            for _ in range(2):
                sim.obj("apple", location=room, tags=["thing"])
            sim.seen(bob)
            await sim.do(alice, "say hello")
            assert 'a masked figure says, "HELLO"' in sim.seen(bob)
            await sim.do(bob, "look")
            assert any("apple x2" in line for line in sim.seen(bob))
        finally:
            sim.close()

    async def test_saved_behavior_survives_a_reboot_without_imports(self, game_module, tmp_path):
        from realm.server.game import GameServer

        db = tmp_path / "world.db"
        features = ["basics", game_module]
        server = GameServer(db_path=db, enable_telnet=False, tick_interval=0,
                            features=features)
        await server.start()
        try:
            bell = GameObject("bell")
            bell.add_behavior(BehaviorRegistry.create(f"{game_module}_chime"))
            await server.persistence.save(bell)
            bell_id = bell.id
        finally:
            await server.stop()

        server = GameServer(db_path=db, enable_telnet=False, tick_interval=0,
                            features=features)
        await server.start()
        try:
            bell = server.persistence.get_cached(bell_id)
            [behavior] = bell.get_behaviors()
            assert type(behavior).__name__ == "Chime"       # not an inert ScriptedBehavior
            await behavior.tick(bell, 1.0)
            assert bell.db.get("chimes") == 1
        finally:
            await server.stop()


class TestCollisions:

    def _pair(self, declare):
        a, b = Feature("alpha"), Feature("beta")
        declare(a, "a")
        declare(b, "b")
        return a, b

    @pytest.mark.parametrize("kind,declare", [
        ("command", lambda f, tag: f.command("ring", lambda ctx: None)),
        ("behavior", lambda f, tag: f.behavior(type(f"B{tag}", (Behavior,),
                                                    {"behavior_id": "same_id"}))),
        ("softcode function", lambda f, tag: f.function(lambda: tag, name="same_fn")),
        ("ruleset", lambda f, tag: f.ruleset("same_rules", type(f"R{tag}", (), {}))),
        ("group formatter", lambda f, tag: f.group_formatter(lambda obj, n: tag)),
        ("login handler", lambda f, tag: f.login(lambda ctx: None)),
    ])
    def test_two_features_one_name_raise_naming_both(self, kind, declare):
        a, b = self._pair(declare)
        with pytest.raises(FeatureError, match=f"{kind} .*'alpha'.*'beta'"):
            FeatureSet([a, b])

    def test_a_game_function_may_not_shadow_a_builtin(self):
        f = Feature("game")
        f.function(lambda *a: True, name="controls")
        with pytest.raises(FeatureError, match="'controls'.*'kernel'.*'game'"):
            FeatureSet([f])


class TestRequirements:

    def test_combat_without_rules_raises(self):
        with pytest.raises(FeatureError, match="'combat' requires 'rules'"):
            load(["items", "combat"])

    def test_unknown_feature_raises(self):
        with pytest.raises(FeatureError, match="no_such_feature"):
            load(["no_such_feature"])


class TestDispatchOrder:
    """CLASSIC tries a command (exact, alias, unique prefix), then an exit
    of the room, then softcode ``$``-commands. Pinned before the exit
    matcher left the dispatcher (KERNEL_PLAN 7.3)."""

    def _hall(self, sim):
        hall, vault = sim.room("Hall"), sim.room("Vault")
        door = sim.obj("vault", location=hall, tags=["exit"])
        door.db.set("destination", vault.id)
        alice = sim.player("Alice", location=hall)
        sign = sim.obj("sign", location=hall)
        sign.db.set("cmd_vault", "$vault:say The sign answers.")
        sign.db.set("cmd_ponder", "$ponder:say The sign ponders.")
        return hall, vault, alice

    async def test_an_exit_beats_a_softcode_command(self):
        with Simulator() as sim:
            hall, vault, alice = self._hall(sim)
            await sim.do(alice, "vault")
            assert alice.location is vault
            assert not any("answers" in line for line in sim.seen(alice))

    async def test_a_command_beats_an_exit_and_softcode_comes_last(self):
        with Simulator() as sim:
            hall, vault, alice = self._hall(sim)
            look = sim.obj("look", location=hall, tags=["exit"])
            look.db.set("destination", vault.id)
            await sim.do(alice, "look")
            assert alice.location is hall              # the command won
            await sim.do(alice, "ponder")
            assert any("ponders" in line for line in sim.seen(alice))

    async def test_direction_abbreviations_walk(self):
        with Simulator() as sim:
            hall, north = sim.room("Hall"), sim.room("North Room")
            door = sim.obj("north", location=hall, tags=["exit"])
            door.db.set("destination", north.id)
            alice = sim.player("Alice", location=hall)
            await sim.do(alice, "n")
            assert alice.location is north

    async def test_talk_tokens(self):
        with Simulator() as sim:
            hall = sim.room("Hall")
            alice = sim.player("Alice", location=hall)
            await sim.do(alice, '"hello')
            await sim.do(alice, ":waves")
            out = sim.seen(alice)
            assert any('You say, "hello"' in line for line in out)
            assert any("Alice waves" in line for line in out)


class TestMovementSeams:
    """Exits, skill gates and followers are features' declarations
    (KERNEL_PLAN 7.3), not the kernel's."""

    def _two_rooms(self, sim, exit_name="vault"):
        hall, vault = sim.room("Hall"), sim.room("Vault")
        door = sim.obj(exit_name, location=hall, tags=["exit"])
        door.db.set("destination", vault.id)
        return hall, vault, door

    async def test_without_movement_an_exit_name_is_an_unknown_command(self):
        with Simulator(features=["basics", "talk", "look"]) as sim:
            hall, vault, _door = self._two_rooms(sim)
            alice = sim.player("Alice", location=hall)
            await sim.do(alice, "vault")
            assert alice.location is hall

    async def test_a_skill_gate_blocks_with_rules(self):
        with Simulator() as sim:
            hall, vault, door = self._two_rooms(sim)
            door.db.set("check_skill", "climbing")
            alice = sim.player("Alice", location=hall)
            sim.world.services["checks"].resolver = (
                lambda obj, skill, mod: __import__("realm.core.dice", fromlist=["x"])
                .CheckResult(False, -3, 13, 10, skill))
            await sim.do(alice, "vault")
            assert alice.location is hall
            assert any("climbing check" in line for line in sim.seen(alice))

    async def test_without_rules_a_skill_gate_is_passable_and_examine_warns(self):
        with Simulator(features=SOCIAL_GAME) as sim:
            hall, vault, door = self._two_rooms(sim)
            door.db.set("check_skill", "climbing")
            ada = sim.player("Ada", location=hall)
            ada.add_tag("admin")
            await sim.do(ada, "@examine vault")
            out = "\n".join(sim.seen(ada))
            assert "check_skill has no effect" in out and "'rules'" in out
            await sim.do(ada, "vault")
            assert ada.location is vault

    async def test_with_rules_examine_does_not_warn(self):
        with Simulator() as sim:
            hall, vault, door = self._two_rooms(sim)
            door.db.set("check_skill", "climbing")
            ada = sim.player("Ada", location=hall)
            ada.add_tag("admin")
            await sim.do(ada, "@examine vault")
            assert "has no effect" not in "\n".join(sim.seen(ada))

    async def test_without_social_nobody_follows(self):
        from realm.std.social.party import set_following
        with Simulator(features=SOCIAL_GAME) as sim:
            hall, vault, _door = self._two_rooms(sim)
            alice = sim.player("Alice", location=hall)
            bob = sim.player("Bob", location=hall)
            set_following(bob, alice)
            await sim.do(alice, "vault")
            assert alice.location is vault and bob.location is hall

    async def test_with_social_followers_follow(self):
        from realm.std.social.party import set_following
        with Simulator() as sim:
            hall, vault, _door = self._two_rooms(sim)
            alice = sim.player("Alice", location=hall)
            bob = sim.player("Bob", location=hall)
            set_following(bob, alice)
            await sim.do(alice, "vault")
            assert bob.location is vault


SEAM_MODULE = '''
from realm.features import Feature

feature = Feature("{name}")
calls = []


@feature.fallback
async def knock(ctx):
    if ctx.command_name != "knock":
        return False
    await ctx.session.send("Knock knock.")
    return True


@feature.traversal_gate(reason="toll", attrs=["toll"])
async def toll(actor, exit_obj, direction, *, fleeing):
    if exit_obj is not None and exit_obj.db.get("toll") and not actor.db.get("paid"):
        return "Pay the toll first."
    return None


@feature.after_traverse
async def note(actor, origin, destination, exit_obj, *, fleeing):
    calls.append((actor.name, origin.name, destination.name, fleeing))


@feature.command("ping", token="!")
async def ping(ctx):
    await ctx.session.send("pong " + ctx.args)
'''


class TestSeamDeclarations:

    @pytest.fixture
    def seam(self, tmp_path, monkeypatch):
        name = f"kp_seam_{uuid.uuid4().hex[:8]}"
        (tmp_path / f"{name}.py").write_text(textwrap.dedent(SEAM_MODULE.format(name=name)))
        monkeypatch.syspath_prepend(str(tmp_path))
        return name

    async def test_fallback_gate_after_traverse_and_token(self, seam):
        import importlib
        module = importlib.import_module(seam)
        with Simulator(features=["basics", "movement", seam]) as sim:
            hall, vault = sim.room("Hall"), sim.room("Vault")
            door = sim.obj("gate", location=hall, tags=["exit"])
            door.db.set("destination", vault.id)
            door.db.set("toll", 2)
            alice = sim.player("Alice", location=hall)
            await sim.do(alice, "knock")
            await sim.do(alice, "!there")
            out = sim.seen(alice)
            assert "Knock knock." in out and "pong there" in out
            await sim.do(alice, "gate")
            assert alice.location is hall
            assert "Pay the toll first." in sim.seen(alice)
            alice.db.set("paid", True)
            await sim.do(alice, "gate")
            assert alice.location is vault
            assert module.calls == [("Alice", "Hall", "Vault", False)]

    def test_a_duplicate_token_raises(self):
        a, b = Feature("alpha"), Feature("beta")
        a.command("ping", lambda ctx: None, token="!")
        b.command("pong", lambda ctx: None, token="!")
        with pytest.raises(FeatureError, match="command token '!'.*'alpha'.*'beta'"):
            FeatureSet([a, b])
