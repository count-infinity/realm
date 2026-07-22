"""Tests for the permission system."""

import pytest

from realm.core.objects import GameObject
from realm.permissions import entitlements as E
from realm.permissions.entitlements import (
    define_role,
    reload_role_defs,
)
from realm.permissions.locks import (
    Lock,
    LockEvaluator,
    LockType,
    check_lock,
    clear_lock,
    controls,
    get_lock,
    parse_lock,
    set_lock,
)
from realm.permissions.roles import (
    Role,
    entitlements_of,
    get_role,
    has_entitlement,
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
        assert role_conferred_by_tag('glowing') is None        # ordinary tag

    def test_ordinary_tags_always_pass(self):
        """The guard is surgical: non-role tags are governed only by control."""
        guest = GameObject("Nobody")                 # role GUEST
        assert may_change_role_tag(guest, 'glowing')
        assert may_change_role_tag(None, 'shiny')

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



# --- Entitlement refactor (2026-07-18) ---------------------------------------

def _player(name, *roles):
    return GameObject(name, tags=['player', *roles])


# Entitlements are authority capabilities only — command tiers are NOT
# entitlements (command access stays a coarse role rung; see has_permission).
_LADDER = {
    'guest':   set(),
    'player':  set(),
    'builder': {E.CONTROL_UNOWNED},
    'admin':   {E.CONTROL_UNOWNED, E.LOCK_BYPASS, E.CONTROL_ALL,
                E.TELEPORT_ANY, E.SEE_ALL},
    'god':     {E.CONTROL_UNOWNED, E.LOCK_BYPASS, E.CONTROL_ALL,
                E.TELEPORT_ANY, E.SEE_ALL, E.LOCK_BYPASS_ALL},
}


class TestEntitlementLadderEquivalence:
    """The built-in roles reproduce the old rung ladder exactly, so the
    cut-over from ``get_role(x) >= Role.Y`` to ``has_entitlement`` is
    behaviour-preserving."""

    def test_builtin_role_entitlement_sets(self):
        # guest tag alone (a guest is not tagged 'player')
        assert set(entitlements_of(GameObject('Gu', tags=['guest']))) == _LADDER['guest']
        for role in ('player', 'builder', 'admin', 'god'):
            got = set(entitlements_of(_player(role.title(), role)))
            assert got == _LADDER[role], f"{role}: {got}"

    def test_authority_entitlements_track_the_old_rungs(self):
        god, admin, builder, player = (
            _player('G', 'god'), _player('A', 'admin'),
            _player('B', 'builder'), _player('P'))
        # LOCK_BYPASS_ALL: god only
        assert has_entitlement(god, E.LOCK_BYPASS_ALL)
        assert not has_entitlement(admin, E.LOCK_BYPASS_ALL)
        # LOCK_BYPASS / CONTROL_ALL / TELEPORT_ANY / SEE_ALL: admin+ (was >=ADMIN)
        for ent in (E.LOCK_BYPASS, E.CONTROL_ALL, E.TELEPORT_ANY, E.SEE_ALL):
            assert has_entitlement(admin, ent) and has_entitlement(god, ent)
            assert not has_entitlement(builder, ent)
        # CONTROL_UNOWNED: builder+ (was >=BUILDER)
        assert has_entitlement(builder, E.CONTROL_UNOWNED)
        assert not has_entitlement(player, E.CONTROL_UNOWNED)

    def test_controls_still_matches_the_ladder(self):
        admin, builder, player = (
            _player('A', 'admin'), _player('B', 'builder'), _player('P'))
        world_prop = GameObject('statue', tags=['thing'])       # unowned, non-player
        # admin controls everything; builder controls unowned world objects;
        # a plain player controls neither.
        assert controls(admin, world_prop)
        assert controls(builder, world_prop)
        assert not controls(player, world_prop)

    def test_has_permission_matches_the_ladder(self):
        rungs = ['guest', 'player', 'builder', 'admin', 'god']
        for i, role in enumerate(rungs):
            who = GameObject(role, tags=[role]) if role == 'guest' else _player(role, role)
            for j, tier in enumerate(rungs):
                assert has_permission(who, tier) == (i >= j), f"{role} vs {tier}"

    def test_quelled_admin_has_only_player_entitlements(self):
        quelled = _player('A', 'admin')
        quelled.add_tag('quelled')
        assert set(entitlements_of(quelled)) == _LADDER['player']
        assert not has_entitlement(quelled, E.CONTROL_ALL)


class _FakeManager:
    """Minimal active-manager so find_objects can see role_def objects."""
    def __init__(self, objs):
        self._objs = list(objs)
    def all_cached(self):
        return list(self._objs)


@pytest.fixture
def role_world():
    """Register a set of world objects as the active manager, and reset the
    role_def cache after — so custom roles don't leak between tests."""
    from realm.persistence.manager import set_active_manager

    created = []

    def install(*objs):
        created.extend(objs)
        set_active_manager(_FakeManager(created))
        reload_role_defs()

    try:
        yield install
    finally:
        set_active_manager(None)
        reload_role_defs()


class TestEntitlementDecoupling:
    """The payoff: a custom role grants exactly what its data lists — a
    capability the rung ladder could never express."""

    def test_custom_role_grants_only_its_entitlements(self, role_world):
        role_world(define_role('warden', [E.TELEPORT_ANY, E.SEE_ALL]))
        warden = _player('W', 'warden')
        # Gains exactly the two listed authority entitlements...
        assert has_entitlement(warden, E.TELEPORT_ANY)
        assert has_entitlement(warden, E.SEE_ALL)
        # ...and NONE of the rest of the admin bundle.
        assert not has_entitlement(warden, E.CONTROL_ALL)
        assert not has_entitlement(warden, E.LOCK_BYPASS)
        assert not has_entitlement(warden, E.LOCK_BYPASS_ALL)
        # ...and it grants no command access: the warden is still role PLAYER,
        # so command tiers (a separate rung check) refuse admin commands.
        assert not has_permission(warden, 'admin')

    def test_custom_role_composes_with_a_builtin_role(self, role_world):
        role_world(define_role('warden', [E.TELEPORT_ANY]))
        both = _player('W', 'builder', 'warden')
        assert has_entitlement(both, E.CONTROL_UNOWNED)   # from builder
        assert has_entitlement(both, E.TELEPORT_ANY)      # from warden
        assert not has_entitlement(both, E.CONTROL_ALL)   # neither grants it

    def test_unknown_entitlement_in_role_def_is_dropped(self, role_world):
        role_world(define_role('bogus', ['NOT_A_REAL_ENTITLEMENT', E.SEE_ALL]))
        who = _player('X', 'bogus')
        assert has_entitlement(who, E.SEE_ALL)                    # valid one kept
        assert 'NOT_A_REAL_ENTITLEMENT' not in entitlements_of(who)  # typo dropped

    def test_quell_suppresses_custom_roles_too(self, role_world):
        role_world(define_role('warden', [E.TELEPORT_ANY]))
        warden = _player('W', 'warden')
        warden.add_tag('quelled')
        assert not has_entitlement(warden, E.TELEPORT_ANY)


class TestEntitlementSoftcodeSurface:
    """The two softcode-facing entry points: the read-only `has_entitlement`
    function and the `caller.has_entitlement(...)` lock-DSL method."""

    def test_softcode_has_entitlement(self):
        admin = GameObject('A', tags=['player', 'admin'])
        gadget = GameObject('g', tags=['thing'])
        funcs = ScriptFunctions(executor=gadget, enactor=admin)
        assert funcs.has_entitlement(admin, 'SEE_ALL') is True
        assert funcs.has_entitlement(admin, 'LOCK_BYPASS_ALL') is False
        assert 'has_entitlement' in ScriptFunctions._READONLY  # check-pass safe

    def test_lock_dsl_caller_has_entitlement(self):
        ev = LockEvaluator()
        admin = GameObject('A', tags=['player', 'admin'])
        player = GameObject('P', tags=['player'])
        door = GameObject('door', tags=['thing'])
        expr = "caller.has_entitlement('SEE_ALL')"
        assert ev.evaluate(expr, admin, door) is True
        assert ev.evaluate(expr, player, door) is False
