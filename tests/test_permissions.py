"""Tests for the permission system."""

from realm.core.objects import GameObject
from realm.permissions.locks import (
    Lock,
    LockEvaluator,
    LockType,
    check_lock,
    clear_lock,
    get_lock,
    parse_lock,
    set_lock,
)
from realm.permissions.roles import (
    Role,
    get_role,
    has_permission,
    may_change_role_tag,
    role_conferred_by_tag,
)
from realm.scripting.functions import ScriptFunctions


class TestRoles:
    """Test suite for role system."""

    def test_god_role_from_tag(self):
        """Object with 'god' tag has God role."""
        obj = GameObject("God", tags=['god', 'player'])
        assert get_role(obj) == Role.GOD

    def test_admin_role_from_tag(self):
        """Object with 'admin' tag has Admin role."""
        obj = GameObject("Admin", tags=['admin', 'player'])
        assert get_role(obj) == Role.ADMIN

    def test_wizard_alias(self):
        """'wizard' tag is alias for Admin."""
        obj = GameObject("Wizard", tags=['wizard', 'player'])
        assert get_role(obj) == Role.ADMIN

    def test_builder_role_from_tag(self):
        """Object with 'builder' tag has Builder role."""
        obj = GameObject("Builder", tags=['builder', 'player'])
        assert get_role(obj) == Role.BUILDER

    def test_staff_alias(self):
        """'staff' tag is alias for Builder."""
        obj = GameObject("Staff", tags=['staff', 'player'])
        assert get_role(obj) == Role.BUILDER

    def test_player_role_default(self):
        """Object with only 'player' tag has Player role."""
        obj = GameObject("Player", tags=['player'])
        assert get_role(obj) == Role.PLAYER

    def test_guest_role_from_tag(self):
        """Object with 'guest' tag has Guest role."""
        obj = GameObject("Guest", tags=['guest'])
        assert get_role(obj) == Role.GUEST

    def test_none_object_is_guest(self):
        """None object returns Guest role."""
        assert get_role(None) == Role.GUEST

    def test_non_player_is_guest(self):
        """Object without player tag is Guest level."""
        obj = GameObject("Rock")
        assert get_role(obj) == Role.GUEST

    def test_highest_role_wins(self):
        """Highest privilege tag takes precedence."""
        obj = GameObject("SuperUser", tags=['god', 'admin', 'builder', 'player'])
        assert get_role(obj) == Role.GOD

    def test_has_permission_exact_match(self):
        """has_permission with exact level match."""
        player = GameObject("Player", tags=['player'])
        assert has_permission(player, "player") is True

    def test_has_permission_higher_level(self):
        """Higher role has lower permissions."""
        admin = GameObject("Admin", tags=['admin', 'player'])
        assert has_permission(admin, "player") is True
        assert has_permission(admin, "builder") is True

    def test_has_permission_insufficient(self):
        """Lower role lacks higher permissions."""
        player = GameObject("Player", tags=['player'])
        assert has_permission(player, "builder") is False
        assert has_permission(player, "admin") is False

class TestLocks:
    """Test suite for lock system."""

    def test_lock_validation_valid(self):
        """Valid lock expressions pass validation."""
        lock = Lock(LockType.BASIC, "caller.has_tag('admin')")
        valid, error = lock.validate()

        assert valid is True
        assert error is None

    def test_lock_validation_syntax_error(self):
        """Syntax errors are caught."""
        lock = Lock(LockType.BASIC, "caller.has_tag(")
        valid, error = lock.validate()

        assert valid is False
        assert error is not None
        assert "Syntax" in error

    def test_lock_validation_import_blocked(self):
        """Import statements are blocked (as syntax error in eval mode)."""
        lock = Lock(LockType.BASIC, "import os")
        valid, error = lock.validate()

        # 'import' is a syntax error in eval mode, which is fine
        assert valid is False
        assert error is not None

    def test_lock_validation_private_blocked(self):
        """Private attribute access is blocked."""
        lock = Lock(LockType.BASIC, "caller.__class__")
        valid, error = lock.validate()

        assert valid is False
        assert "Private" in error

    def test_lock_evaluation_true(self):
        """Lock evaluates to True when condition met."""
        evaluator = LockEvaluator()
        admin = GameObject("Admin", tags=['admin'])
        door = GameObject("Door")

        lock = Lock(LockType.BASIC, "caller.has_tag('admin')")
        result = evaluator.evaluate(lock, admin, door)

        assert result is True

    def test_lock_evaluation_false(self):
        """Lock evaluates to False when condition not met."""
        evaluator = LockEvaluator()
        player = GameObject("Player", tags=['player'])
        door = GameObject("Door")

        lock = Lock(LockType.BASIC, "caller.has_tag('admin')")
        result = evaluator.evaluate(lock, player, door)

        assert result is False

    def test_lock_with_attribute_check(self):
        """Lock can check attributes."""
        evaluator = LockEvaluator()
        player = GameObject("Player", tags=['player'])
        player.db.level = 15
        door = GameObject("Door")

        lock = Lock(LockType.ENTER, "caller.db.level >= 10")
        result = evaluator.evaluate(lock, player, door)

        assert result is True

    def test_lock_owner_variable(self):
        """Lock can access owner variable."""
        evaluator = LockEvaluator()
        player1 = GameObject("Player1", tags=['player'])
        player2 = GameObject("Player2", tags=['player'])
        item = GameObject("Item", owner=player1)

        lock = Lock(LockType.CONTROL, "caller.id == owner.id")
        assert evaluator.evaluate(lock, player1, item) is True
        assert evaluator.evaluate(lock, player2, item) is False

    def test_check_lock_god_bypass(self):
        """God bypasses all locks."""
        god = GameObject("God", tags=['god'])
        locked_door = GameObject("Door")
        locked_door.locks['basic'] = "False"  # Always fail

        result = check_lock(locked_door, LockType.BASIC, god)
        assert result is True

    def test_check_lock_admin_bypass(self):
        """Admin bypasses most locks."""
        admin = GameObject("Admin", tags=['admin'])
        locked_door = GameObject("Door")
        locked_door.locks['basic'] = "False"

        result = check_lock(locked_door, LockType.BASIC, admin)
        assert result is True

    def test_check_lock_admin_no_bypass_god_control(self):
        """Admin cannot bypass control lock on God's objects."""
        god = GameObject("God", tags=['god'])
        admin = GameObject("Admin", tags=['admin'])
        god_item = GameObject("God's Item", owner=god)
        god_item.locks['control'] = "False"

        result = check_lock(god_item, LockType.CONTROL, admin)
        assert result is False

    def test_check_lock_uses_default(self):
        """check_lock uses default lock when none set."""
        player = GameObject("Player", tags=['player'])
        door = GameObject("Door")

        # BASIC default is True
        result = check_lock(door, LockType.BASIC, player)
        assert result is True

    def test_set_and_get_lock(self):
        """Can set and get locks."""
        door = GameObject("Door")

        success = set_lock(door, LockType.ENTER, "caller.db.has_key")
        assert success is True

        expr = get_lock(door, LockType.ENTER)
        assert expr == "caller.db.has_key"

    def test_set_lock_invalid_rejected(self):
        """Invalid lock expressions are rejected."""
        door = GameObject("Door")

        success = set_lock(door, LockType.ENTER, "import os")
        assert success is False

    def test_clear_lock(self):
        """Can clear locks."""
        door = GameObject("Door")
        door.locks['enter'] = "False"

        result = clear_lock(door, LockType.ENTER)
        assert result is True
        assert 'enter' not in door.locks

    def test_parse_lock(self):
        """parse_lock creates Lock object."""
        lock = parse_lock("caller.db.level > 5", LockType.ENTER)

        assert lock.lock_type == LockType.ENTER
        assert lock.expression == "caller.db.level > 5"


class TestLockTypes:
    """Test that all lock types are properly defined."""

    def test_basic_lock_type(self):
        """BASIC lock type exists."""
        assert LockType.BASIC.value == "basic"

    def test_enter_lock_type(self):
        """ENTER lock type exists."""
        assert LockType.ENTER.value == "enter"

    def test_control_lock_type(self):
        """CONTROL lock type exists."""
        assert LockType.CONTROL.value == "control"


class TestRoleTagAuthority:
    """Privilege tags may only be changed by someone who outranks them.

    Regression for the escalation the old `set_flag`/`flags.py` namespace bug
    became once flags were folded into role tags: because everyone controls
    themselves and their own objects, `controls()` alone would let `@tag me =
    admin` — or a self-owned script's `add_tag(me, 'admin')` — self-promote.
    """

    def test_role_conferred_by_tag(self):
        assert role_conferred_by_tag('admin') == Role.ADMIN
        assert role_conferred_by_tag('WIZARD') == Role.ADMIN   # alias, case
        assert role_conferred_by_tag('builder') == Role.BUILDER
        assert role_conferred_by_tag('god') == Role.GOD
        assert role_conferred_by_tag('container') is None      # ordinary tag

    def test_ordinary_tags_always_pass(self):
        """The guard is surgical: non-role tags are governed only by control."""
        guest = GameObject("Nobody")                 # role GUEST
        assert may_change_role_tag(guest, 'glowing')
        assert may_change_role_tag(None, 'container')

    def test_builder_cannot_grant_admin_or_god(self):
        builder = GameObject("Bob", tags=['player', 'builder'])
        assert not may_change_role_tag(builder, 'admin')
        assert not may_change_role_tag(builder, 'wizard')
        assert not may_change_role_tag(builder, 'god')
        # ...and cannot even mint a peer builder — that needs admin+.
        assert not may_change_role_tag(builder, 'builder')

    def test_admin_grants_builder_but_not_admin(self):
        admin = GameObject("Ada", tags=['player', 'admin'])
        assert may_change_role_tag(admin, 'builder')
        assert may_change_role_tag(admin, 'staff')
        assert not may_change_role_tag(admin, 'admin')   # can't reach own rank
        assert not may_change_role_tag(admin, 'god')

    def test_god_grants_anything_including_god(self):
        god = GameObject("Ao", tags=['player', 'god'])
        assert may_change_role_tag(god, 'admin')
        assert may_change_role_tag(god, 'builder')
        assert may_change_role_tag(god, 'god')           # superuser mints gods

    def test_quelled_admin_cannot_grant(self):
        """Quell means quelled: an admin acting as a mortal has no rank power."""
        admin = GameObject("Ada", tags=['player', 'admin', 'quelled'])
        assert get_role(admin) == Role.PLAYER
        assert not may_change_role_tag(admin, 'builder')

    def test_softcode_add_tag_cannot_self_promote(self):
        """A non-privileged script executor can't grant itself a role tag,
        even though it plainly controls itself (rule 1)."""
        obj = GameObject("gadget", tags=['thing'])       # role GUEST
        funcs = ScriptFunctions(executor=obj, enactor=obj)

        assert funcs.add_tag(obj, 'admin') is False
        assert not obj.has_tag('admin')
        assert get_role(obj) == Role.GUEST
        # ...but an ordinary tag on the same self-controlled object still works.
        assert funcs.add_tag(obj, 'glowing') is True
        assert obj.has_tag('glowing')

    def test_softcode_add_tag_honors_a_blessed_executor(self):
        """A god-blessed admin object CAN confer a lower rank via softcode."""
        booth = GameObject("promotion booth", tags=['thing', 'admin'])
        funcs = ScriptFunctions(executor=booth, enactor=booth)

        assert funcs.add_tag(booth, 'builder') is True   # admin > builder
        assert funcs.add_tag(booth, 'admin') is False    # admin !> admin

