"""Tests for the permission system."""

import pytest
from realm.core.objects import GameObject
from realm.permissions.roles import (
    Role,
    get_role,
    has_permission,
    can_control,
    is_god,
    is_admin,
    is_builder,
    set_role,
    get_role_name,
)
from realm.permissions.flags import (
    Flag,
    has_flag,
    set_flag,
    clear_flag,
    get_flags,
    toggle_flag,
    is_halted,
    is_gagged,
    is_dark,
    is_safe,
    can_set_flag,
)
from realm.permissions.locks import (
    Lock,
    LockType,
    LockEvaluator,
    check_lock,
    parse_lock,
    set_lock,
    clear_lock,
    get_lock,
)


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

    def test_is_god(self):
        """is_god helper function."""
        god = GameObject("God", tags=['god'])
        player = GameObject("Player", tags=['player'])

        assert is_god(god) is True
        assert is_god(player) is False

    def test_is_admin(self):
        """is_admin helper function."""
        admin = GameObject("Admin", tags=['admin'])
        builder = GameObject("Builder", tags=['builder'])

        assert is_admin(admin) is True
        assert is_admin(builder) is False

    def test_is_builder(self):
        """is_builder helper function."""
        builder = GameObject("Builder", tags=['builder'])
        player = GameObject("Player", tags=['player'])

        assert is_builder(builder) is True
        assert is_builder(player) is False


class TestCanControl:
    """Test suite for can_control function."""

    def test_god_controls_everything(self):
        """God can control any object."""
        god = GameObject("God", tags=['god'])
        target = GameObject("Target")

        assert can_control(god, target) is True

    def test_admin_controls_most(self):
        """Admin can control most objects."""
        admin = GameObject("Admin", tags=['admin'])
        target = GameObject("Target")

        assert can_control(admin, target) is True

    def test_admin_cannot_control_god_owned(self):
        """Admin cannot control God-owned objects."""
        god = GameObject("God", tags=['god'])
        admin = GameObject("Admin", tags=['admin'])
        god_item = GameObject("God's Item", owner=god)

        assert can_control(admin, god_item) is False

    def test_owner_controls_own_objects(self):
        """Owner can control their own objects."""
        player = GameObject("Player", tags=['player'])
        item = GameObject("My Item", owner=player)

        assert can_control(player, item) is True

    def test_non_owner_cannot_control(self):
        """Non-owner cannot control others' objects."""
        player1 = GameObject("Player1", tags=['player'])
        player2 = GameObject("Player2", tags=['player'])
        item = GameObject("Item", owner=player1)

        assert can_control(player2, item) is False

    def test_none_actor_cannot_control(self):
        """None actor cannot control anything."""
        target = GameObject("Target")
        assert can_control(None, target) is False

    def test_none_target_cannot_be_controlled(self):
        """Cannot control None target."""
        actor = GameObject("Actor")
        assert can_control(actor, None) is False


class TestSetRole:
    """Test suite for set_role function."""

    def test_set_role_adds_tag(self):
        """set_role adds appropriate tag."""
        player = GameObject("Player", tags=['player'])
        set_role(player, Role.BUILDER)

        assert player.has_tag('builder')
        assert get_role(player) == Role.BUILDER

    def test_set_role_removes_old_tags(self):
        """set_role removes previous role tags."""
        admin = GameObject("Admin", tags=['admin', 'player'])
        set_role(admin, Role.BUILDER)

        assert not admin.has_tag('admin')
        assert player.has_tag('builder') if (player := admin) else False

    def test_set_player_role_no_tag(self):
        """Player role doesn't need a tag."""
        builder = GameObject("Builder", tags=['builder', 'player'])
        set_role(builder, Role.PLAYER)

        assert not builder.has_tag('builder')
        assert get_role(builder) == Role.PLAYER


class TestFlags:
    """Test suite for object flags."""

    def test_set_and_has_flag(self):
        """Can set and check flags."""
        obj = GameObject("Object")

        assert has_flag(obj, Flag.HALT) is False
        set_flag(obj, Flag.HALT)
        assert has_flag(obj, Flag.HALT) is True

    def test_clear_flag(self):
        """Can clear flags."""
        obj = GameObject("Object")
        set_flag(obj, Flag.DARK)

        assert has_flag(obj, Flag.DARK) is True
        clear_flag(obj, Flag.DARK)
        assert has_flag(obj, Flag.DARK) is False

    def test_get_flags(self):
        """get_flags returns all set flags."""
        obj = GameObject("Object")
        set_flag(obj, Flag.HALT)
        set_flag(obj, Flag.GAGGED)
        set_flag(obj, Flag.DARK)

        flags = get_flags(obj)
        assert Flag.HALT in flags
        assert Flag.GAGGED in flags
        assert Flag.DARK in flags
        assert Flag.SAFE not in flags

    def test_toggle_flag(self):
        """toggle_flag toggles state."""
        obj = GameObject("Object")

        result = toggle_flag(obj, Flag.QUIET)
        assert result is True
        assert has_flag(obj, Flag.QUIET)

        result = toggle_flag(obj, Flag.QUIET)
        assert result is False
        assert not has_flag(obj, Flag.QUIET)

    def test_flag_convenience_functions(self):
        """Convenience functions work."""
        obj = GameObject("Object")

        assert is_halted(obj) is False
        set_flag(obj, Flag.HALT)
        assert is_halted(obj) is True

        assert is_gagged(obj) is False
        set_flag(obj, Flag.GAGGED)
        assert is_gagged(obj) is True

        assert is_dark(obj) is False
        set_flag(obj, Flag.DARK)
        assert is_dark(obj) is True

        assert is_safe(obj) is False
        set_flag(obj, Flag.SAFE)
        assert is_safe(obj) is True

    def test_flag_with_string(self):
        """Flags work with string names."""
        obj = GameObject("Object")

        set_flag(obj, "halt")
        assert has_flag(obj, "halt") is True
        assert has_flag(obj, Flag.HALT) is True

    def test_none_object_flags(self):
        """None object has no flags."""
        assert has_flag(None, Flag.HALT) is False
        assert get_flags(None) == []

    def test_can_set_flag_requires_control(self):
        """can_set_flag requires control over target."""
        player1 = GameObject("Player1", tags=['player'])
        player2 = GameObject("Player2", tags=['player'])
        item = GameObject("Item", owner=player1)

        assert can_set_flag(player1, item, Flag.HALT) is True
        assert can_set_flag(player2, item, Flag.HALT) is False

    def test_admin_only_flags(self):
        """Admin-only flags require admin role."""
        player = GameObject("Player", tags=['player'])
        admin = GameObject("Admin", tags=['admin'])
        item = GameObject("Item", owner=player)

        assert can_set_flag(player, item, Flag.SAFE) is False
        assert can_set_flag(admin, item, Flag.SAFE) is True


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

    def test_all_lock_types(self):
        """All expected lock types exist."""
        expected = [
            'basic', 'enter', 'use', 'control', 'zone',
            'speech', 'teleport', 'examine', 'give', 'drop',
            'command', 'listen', 'page', 'mail'
        ]

        for name in expected:
            assert LockType(name), f"Missing lock type: {name}"


class TestRoleNames:
    """Test role name helpers."""

    def test_get_role_name(self):
        """get_role_name returns display names."""
        assert get_role_name(Role.GOD) == "God"
        assert get_role_name(Role.ADMIN) == "Admin"
        assert get_role_name(Role.BUILDER) == "Builder"
        assert get_role_name(Role.PLAYER) == "Player"
        assert get_role_name(Role.GUEST) == "Guest"
