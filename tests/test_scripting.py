"""Tests for the scripting system."""

import pytest
from realm.core.objects import GameObject
from realm.scripting.sandbox import (
    ScriptSandbox,
    ScriptContext,
    ScriptError,
    ScriptSecurityError,
    ScriptLimits,
    SimpleScriptRunner,
)
from realm.scripting.triggers import (
    TriggerManager,
    CommandTrigger,
    ListenTrigger,
    EventTrigger,
    get_search_objects,
)
from realm.scripting.functions import ScriptFunctions


class TestScriptSandbox:
    """Test suite for ScriptSandbox."""

    def test_simple_execution(self):
        """Basic script execution works."""
        sandbox = ScriptSandbox()
        ctx = ScriptContext()

        result, output = sandbox.execute("result = 2 + 2", ctx)
        assert result == 4

    def test_output_function(self):
        """Scripts can produce output."""
        sandbox = ScriptSandbox()
        ctx = ScriptContext()

        result, output = sandbox.execute("output('hello')", ctx)
        assert 'hello\n' in output

    def test_substitution_enactor_name(self):
        """Substitution %n expands to enactor's name."""
        sandbox = ScriptSandbox()
        player = GameObject("Alice")
        ctx = ScriptContext(enactor=player)

        result, output = sandbox.execute("output('%n')", ctx)
        assert 'Alice\n' in output

    def test_substitution_captures(self):
        """Substitutions %0-%9 expand to captures."""
        sandbox = ScriptSandbox()
        ctx = ScriptContext(captures=['first', 'second', 'third'])

        result, output = sandbox.execute("output('%0 %1 %2')", ctx)
        assert 'first second third\n' in output

    def test_validation_blocks_import(self):
        """Validation rejects import statements."""
        sandbox = ScriptSandbox()

        errors = sandbox.validate("import os")
        assert len(errors) > 0
        assert any('Import' in e for e in errors)

    def test_validation_blocks_eval(self):
        """Validation rejects eval/exec."""
        sandbox = ScriptSandbox()

        errors = sandbox.validate("eval('1+1')")
        assert len(errors) > 0
        assert any('eval' in e for e in errors)

    def test_validation_blocks_private_attrs(self):
        """Validation rejects private attribute access."""
        sandbox = ScriptSandbox()

        errors = sandbox.validate("x.__class__")
        assert len(errors) > 0
        assert any('Private' in e or '__' in e for e in errors)

    def test_security_error_on_bad_code(self):
        """Executing invalid code raises ScriptSecurityError."""
        sandbox = ScriptSandbox()
        ctx = ScriptContext()

        with pytest.raises(ScriptSecurityError):
            sandbox.execute("import os", ctx)

    def test_safe_builtins_available(self):
        """Safe builtins are available."""
        sandbox = ScriptSandbox()
        ctx = ScriptContext()

        result, _ = sandbox.execute("result = len([1, 2, 3])", ctx)
        assert result == 3

    def test_safe_builtins_math(self):
        """Math functions work."""
        sandbox = ScriptSandbox()
        ctx = ScriptContext()

        result, _ = sandbox.execute("result = sum([1, 2, 3, 4])", ctx)
        assert result == 10

    def test_context_variables_available(self):
        """Context variables are accessible."""
        sandbox = ScriptSandbox()
        player = GameObject("TestPlayer")
        room = GameObject("TestRoom", tags=['room'])
        ctx = ScriptContext(enactor=player, executor=player, location=room)

        result, _ = sandbox.execute("result = enactor.name", ctx)
        assert result == "TestPlayer"

    def test_recursion_limit(self):
        """Recursion limit is enforced."""
        sandbox = ScriptSandbox(limits=ScriptLimits(max_recursion=10))
        ctx = ScriptContext()

        with pytest.raises(ScriptError):
            sandbox.execute("""
def recurse(n):
    return recurse(n + 1)
recurse(0)
""", ctx)


class TestSimpleScriptRunner:
    """Test the simple script runner."""

    def test_is_simple_say(self):
        """'say hello' is simple."""
        assert SimpleScriptRunner.is_simple_script("say hello")

    def test_is_simple_pose(self):
        """'pose waves' is simple."""
        assert SimpleScriptRunner.is_simple_script("pose waves")

    def test_not_simple_with_def(self):
        """Script with 'def' is not simple."""
        assert not SimpleScriptRunner.is_simple_script("def foo(): pass")

    def test_not_simple_multiline(self):
        """Multiline script is not simple."""
        assert not SimpleScriptRunner.is_simple_script("line1\nline2")

    def test_expand_simple(self):
        """Simple expansion works."""
        player = GameObject("Bob")
        ctx = ScriptContext(enactor=player, captures=['world'])

        result = SimpleScriptRunner.expand_simple("say Hello, %0! I'm %n.", ctx)
        assert result == "say Hello, world! I'm Bob."


class TestCommandTrigger:
    """Test suite for CommandTrigger."""

    def test_simple_match(self):
        """Simple pattern matches."""
        trigger = CommandTrigger(_pattern="greet", action="say Hello!")

        captures = trigger.matches("greet")
        assert captures == []

    def test_no_match(self):
        """Non-matching input returns None."""
        trigger = CommandTrigger(_pattern="greet", action="say Hello!")

        captures = trigger.matches("wave")
        assert captures is None

    def test_wildcard_match(self):
        """Wildcard * captures text."""
        trigger = CommandTrigger(_pattern="greet *", action="say Hello, %0!")

        captures = trigger.matches("greet Alice")
        assert captures == ["Alice"]

    def test_multiple_wildcards(self):
        """Multiple wildcards capture in order."""
        trigger = CommandTrigger(_pattern="give * to *", action="@force %1=accept")

        captures = trigger.matches("give sword to Bob")
        assert captures == ["sword", "Bob"]

    def test_case_insensitive(self):
        """Matching is case-insensitive."""
        trigger = CommandTrigger(_pattern="GREET *", action="say Hi!")

        captures = trigger.matches("greet Alice")
        assert captures == ["Alice"]

    def test_question_mark_single_char(self):
        """? matches single character."""
        trigger = CommandTrigger(_pattern="go ?", action="move %0")

        captures = trigger.matches("go n")
        assert captures == ["n"]

        captures = trigger.matches("go north")
        assert captures is None  # More than one char


class TestListenTrigger:
    """Test suite for ListenTrigger."""

    def test_simple_match(self):
        """Simple pattern matches."""
        trigger = ListenTrigger(_pattern="hello", action="say Hi!")

        captures = trigger.matches("hello")
        assert captures == []

    def test_wildcard_contains(self):
        """Wildcard can match substring."""
        trigger = ListenTrigger(_pattern="*treasure*", action="say I heard treasure!")

        captures = trigger.matches("I found some treasure here")
        assert captures == ["I found some ", " here"]

    def test_no_match(self):
        """Non-matching speech returns None."""
        trigger = ListenTrigger(_pattern="*password*", action="say Shh!")

        captures = trigger.matches("The weather is nice")
        assert captures is None


class TestEventTrigger:
    """Test suite for EventTrigger."""

    def test_matches_event_type(self):
        """EventTrigger matches correct action_type suffix."""
        from realm.core.propagation import Action

        trigger = EventTrigger(event_type="ENTER", action="say Welcome!")
        action = Action(actor=None, target=None, action_type="event:on_enter")

        assert trigger.matches_event(action)

    def test_matches_event_type_without_on_prefix(self):
        """EventTrigger matches even when action_type lacks the on_ prefix."""
        from realm.core.propagation import Action

        trigger = EventTrigger(event_type="ENTER", action="say Welcome!")
        action = Action(actor=None, target=None, action_type="event:enter")

        assert trigger.matches_event(action)

    def test_no_match_wrong_type(self):
        """EventTrigger doesn't match wrong action_type."""
        from realm.core.propagation import Action

        trigger = EventTrigger(event_type="ENTER", action="say Welcome!")
        action = Action(actor=None, target=None, action_type="event:on_leave")

        assert not trigger.matches_event(action)


class TestTriggerManager:
    """Test suite for TriggerManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = TriggerManager()

    def test_parse_command_trigger(self):
        """Parses command trigger from attribute."""
        obj = GameObject("greeter")
        obj.db.CMD_GREET = "$greet *: say Hello, %0!"

        triggers = self.manager.get_command_triggers(obj)
        assert len(triggers) == 1
        assert triggers[0].pattern == "greet *"
        assert triggers[0].action == "say Hello, %0!"

    def test_parse_listen_trigger(self):
        """Parses listen trigger from attribute."""
        obj = GameObject("eavesdropper")
        obj.db.LISTEN_MAGIC = "^*magic*: say I sense magic!"

        triggers = self.manager.get_listen_triggers(obj)
        assert len(triggers) == 1
        assert triggers[0].pattern == "*magic*"

    def test_parse_event_trigger(self):
        """Parses event trigger from attribute."""
        obj = GameObject("welcoming_room")
        obj.db.ON_ENTER = "say Welcome!"

        triggers = self.manager.get_event_triggers(obj, "ENTER")
        assert len(triggers) == 1
        assert triggers[0].action == "say Welcome!"

    def test_find_command_match(self):
        """Finds matching command trigger."""
        obj = GameObject("robot")
        obj.db.CMD_DANCE = "$dance: pose does a robot dance!"

        match = self.manager.find_command_match("dance", [obj])
        assert match is not None
        assert match.obj == obj
        assert match.action == "pose does a robot dance!"

    def test_find_command_no_match(self):
        """Returns None when no trigger matches."""
        obj = GameObject("robot")
        obj.db.CMD_DANCE = "$dance: pose dances!"

        match = self.manager.find_command_match("sing", [obj])
        assert match is None

    def test_halt_tag_skips_object(self):
        """Objects with HALT tag are skipped."""
        obj = GameObject("broken_robot", tags=['halt'])
        obj.db.CMD_DANCE = "$dance: pose dances!"

        match = self.manager.find_command_match("dance", [obj])
        assert match is None

    def test_find_listen_matches_multiple(self):
        """Can find multiple listen matches."""
        obj1 = GameObject("spy1")
        obj1.db.LISTEN_SECRET = "^*secret*: say Interesting..."

        obj2 = GameObject("spy2")
        obj2.db.LISTEN_SECRET = "^*secret*: say Tell me more..."

        matches = self.manager.find_listen_matches(
            "I have a secret to share",
            [obj1, obj2]
        )
        assert len(matches) == 2


class TestGetSearchObjects:
    """Test the search order for triggers."""

    def test_includes_room_contents(self):
        """Search includes room contents."""
        room = GameObject("room", tags=['room'])
        npc = GameObject("npc", location=room)
        player = GameObject("player", location=room, tags=['player'])

        search = get_search_objects(player)
        assert npc in search

    def test_includes_room(self):
        """Search includes the room itself."""
        room = GameObject("room", tags=['room'])
        player = GameObject("player", location=room, tags=['player'])

        search = get_search_objects(player)
        assert room in search

    def test_includes_inventory(self):
        """Search includes player inventory."""
        room = GameObject("room", tags=['room'])
        player = GameObject("player", location=room, tags=['player'])
        item = GameObject("magic_wand", location=player)

        search = get_search_objects(player)
        assert item in search

    def test_excludes_player(self):
        """Search doesn't include the player themselves."""
        room = GameObject("room", tags=['room'])
        player = GameObject("player", location=room, tags=['player'])

        search = get_search_objects(player)
        assert player not in search

    def test_no_duplicates(self):
        """Search list has no duplicates."""
        room = GameObject("room", tags=['room'])
        player = GameObject("player", location=room, tags=['player'])

        search = get_search_objects(player)
        assert len(search) == len(set(obj.id for obj in search))


class TestScriptFunctions:
    """Test suite for ScriptFunctions."""

    def test_string_ucfirst(self):
        """ucfirst capitalizes first char."""
        assert ScriptFunctions.ucfirst("hello") == "Hello"
        assert ScriptFunctions.ucfirst("") == ""

    def test_string_capstr(self):
        """capstr title-cases."""
        assert ScriptFunctions.capstr("hello world") == "Hello World"

    def test_math_rand(self):
        """rand returns value in range."""
        for _ in range(10):
            val = ScriptFunctions.rand(1, 10)
            assert 1 <= val <= 10

    def test_math_dice(self):
        """dice rolls correctly."""
        # Roll 2d6 should be 2-12
        for _ in range(10):
            val = ScriptFunctions.dice(2, 6)
            assert 2 <= val <= 12

    def test_math_clamp(self):
        """clamp limits value."""
        assert ScriptFunctions.clamp(5, 0, 10) == 5
        assert ScriptFunctions.clamp(-5, 0, 10) == 0
        assert ScriptFunctions.clamp(15, 0, 10) == 10

    def test_list_first(self):
        """first gets first element."""
        assert ScriptFunctions.first("a b c") == "a"
        assert ScriptFunctions.first([1, 2, 3]) == "1"

    def test_list_rest(self):
        """rest gets remaining elements."""
        assert ScriptFunctions.rest("a b c") == "b c"
        assert ScriptFunctions.rest([1, 2, 3]) == [2, 3]

    def test_list_member(self):
        """member finds position (1-indexed)."""
        assert ScriptFunctions.member("b", "a b c") == 2
        assert ScriptFunctions.member("x", "a b c") == 0

    def test_list_extract(self):
        """extract gets element at position."""
        assert ScriptFunctions.extract("a b c", 2) == "b"
        assert ScriptFunctions.extract("a b c", 5) == ""

    def test_conditional_if_else(self):
        """if_else returns correct value."""
        assert ScriptFunctions.if_else(True, "yes", "no") == "yes"
        assert ScriptFunctions.if_else(False, "yes", "no") == "no"

    def test_conditional_switch(self):
        """switch finds matching case."""
        result = ScriptFunctions.switch("b", "a", 1, "b", 2, "c", 3, 0)
        assert result == 2

        # Default case
        result = ScriptFunctions.switch("x", "a", 1, "b", 2, 0)
        assert result == 0

    def test_object_access(self):
        """Object functions work with real objects."""
        player = GameObject("Alice")
        room = GameObject("Kitchen", tags=['room'])
        player.location = room

        funcs = ScriptFunctions(enactor=player, location=room)

        assert funcs.name(player) == "Alice"
        assert funcs.loc(player) == room
        assert funcs.has_tag(room, "room") is True
        assert funcs.has_tag(room, "player") is False

    def test_attribute_access(self):
        """Attribute functions work."""
        obj = GameObject("chest")
        obj.db.gold = 100

        funcs = ScriptFunctions()

        assert funcs.get_attr(obj, "gold") == 100
        assert funcs.get_attr(obj, "silver", 0) == 0
        assert funcs.has_attr(obj, "gold") is True

        funcs.set_attr(obj, "silver", 50)
        assert obj.db.silver == 50

    def test_to_dict_exports_all(self):
        """to_dict exports all functions."""
        funcs = ScriptFunctions()
        exported = funcs.to_dict()

        # Check some expected functions are present
        assert 'rand' in exported
        assert 'ucfirst' in exported
        assert 'get_attr' in exported
        assert 'if_else' in exported
