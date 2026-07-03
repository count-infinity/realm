"""Tests for OLC (Online Creation) commands."""

import pytest

from realm.commands import CommandContext, CommandDispatcher
from realm.commands.base import find_object_global
from realm.commands.olc.admin import (
    cmd_chown,
    cmd_destroy,
    cmd_examine_full,
    cmd_find,
    cmd_teleport,
)
from realm.commands.olc.create import (
    cmd_create,
    cmd_dig,
    cmd_link,
    cmd_open,
    cmd_unlink,
)
from realm.commands.olc.modify import (
    cmd_desc,
    cmd_lock,
    cmd_name,
    cmd_parent,
    cmd_set,
    cmd_tag,
    cmd_unlock,
    cmd_untag,
    cmd_wipe,
)
from realm.core.objects import GameObject


class MockPersistence:
    """Mock persistence manager implementing the public lookup API."""

    def __init__(self):
        self._object_cache = {}
        self.saved = []
        self.deleted = []

    async def save(self, obj):
        self._object_cache[obj.id] = obj
        self.saved.append(obj)

    async def delete(self, obj):
        if obj.id in self._object_cache:
            del self._object_cache[obj.id]
        self.deleted.append(obj)

    def add(self, obj):
        """Add object to cache without async."""
        self._object_cache[obj.id] = obj

    def get_cached(self, obj_id):
        return self._object_cache.get(obj_id)

    def all_cached(self):
        return list(self._object_cache.values())

    def find_cached(self, *, tag=None, name=None):
        name_lower = name.lower() if name is not None else None
        results = []
        for obj in self._object_cache.values():
            if tag is not None and not obj.has_tag(tag):
                continue
            if name_lower is not None and obj.name.lower() != name_lower:
                continue
            results.append(obj)
        return results


class MockSession:
    """Mock session for testing."""

    def __init__(self):
        self.messages = []
        self.player = None

    async def send(self, message):
        self.messages.append(message)

    def link_player(self, player):
        self.player = player


def make_context(player, raw_input="", command_name="", args="",
                 left_args=None, right_args=None, switches=None,
                 persistence=None):
    """Create a command context for testing.

    Commands reach persistence via ctx.dispatcher, mirroring how
    GameServer wires the real dispatcher.
    """
    session = MockSession()
    session.link_player(player)
    dispatcher = CommandDispatcher()
    dispatcher.persistence = persistence if persistence is not None else _current_persistence
    return CommandContext(
        session=session,
        player=player,
        raw_input=raw_input,
        command_name=command_name,
        args=args,
        left_args=left_args,
        right_args=right_args,
        switches=switches or [],
        dispatcher=dispatcher,
    )


# Persistence used by make_context, set per-test-class via use_persistence().
_current_persistence = None


def use_persistence(persistence):
    """Point contexts built by make_context at this persistence manager."""
    global _current_persistence
    _current_persistence = persistence


class TestCreateCommands:
    """Test suite for creation OLC commands."""

    def setup_method(self):
        """Set up test environment."""
        self.persistence = MockPersistence()
        use_persistence(self.persistence)

        self.room = GameObject("Test Room", tags=['room'])
        self.player = GameObject("Builder", tags=['player'], location=self.room)
        self.persistence.add(self.room)
        self.persistence.add(self.player)

    @pytest.mark.asyncio
    async def test_create_basic(self):
        """@create creates a new object."""
        ctx = make_context(self.player, args="sword")
        await cmd_create(ctx)

        assert len(self.persistence.saved) == 1
        obj = self.persistence.saved[0]
        assert obj.name == "sword"
        assert obj.location == self.player  # Created in inventory
        assert obj.owner == self.player
        assert obj.has_tag('thing')
        assert "Created: sword" in ctx.session.messages[0]

    @pytest.mark.asyncio
    async def test_create_with_parent(self):
        """@create with parent sets inheritance."""
        parent = GameObject("Base Sword", tags=['thing'])
        self.persistence.add(parent)

        ctx = make_context(
            self.player,
            args="sword = Base Sword",
            left_args="sword",
            right_args="Base Sword"
        )
        await cmd_create(ctx)

        obj = self.persistence.saved[0]
        assert obj.parent == parent

    @pytest.mark.asyncio
    async def test_create_no_args(self):
        """@create with no args shows usage."""
        ctx = make_context(self.player, args="")
        await cmd_create(ctx)

        assert "Usage:" in ctx.session.messages[0]
        assert len(self.persistence.saved) == 0

    @pytest.mark.asyncio
    async def test_dig_basic(self):
        """@dig creates a new room."""
        ctx = make_context(self.player, args="The Kitchen")
        await cmd_dig(ctx)

        assert len(self.persistence.saved) == 1
        room = self.persistence.saved[0]
        assert room.name == "The Kitchen"
        assert room.has_tag('room')
        assert room.owner == self.player

    @pytest.mark.asyncio
    async def test_dig_with_exits(self):
        """@dig with exits creates exits in both directions."""
        ctx = make_context(
            self.player,
            args="The Kitchen = north, south",
            left_args="The Kitchen",
            right_args="north, south"
        )
        await cmd_dig(ctx)

        # Room + 2 exits (north from here, south in new room)
        assert len(self.persistence.saved) >= 3

        # Check exit names in saved objects
        names = [obj.name for obj in self.persistence.saved]
        assert "The Kitchen" in names
        assert "north" in names
        assert "south" in names

    @pytest.mark.asyncio
    async def test_open_creates_exit(self):
        """@open creates an exit to an existing room."""
        dest_room = GameObject("Kitchen", tags=['room'])
        self.persistence.add(dest_room)

        ctx = make_context(
            self.player,
            args="north = Kitchen",
            left_args="north",
            right_args="Kitchen"
        )
        await cmd_open(ctx)

        exit_obj = self.persistence.saved[0]
        assert exit_obj.name == "north"
        assert exit_obj.has_tag('exit')
        assert exit_obj.db.destination == dest_room.id

    @pytest.mark.asyncio
    async def test_open_not_a_room(self):
        """@open fails if destination is not a room."""
        thing = GameObject("chair", tags=['thing'])
        self.persistence.add(thing)

        ctx = make_context(
            self.player,
            args="sit = chair",
            left_args="sit",
            right_args="chair"
        )
        await cmd_open(ctx)

        assert "not a room" in ctx.session.messages[0]
        assert len(self.persistence.saved) == 0

    @pytest.mark.asyncio
    async def test_link_exit(self):
        """@link sets exit destination."""
        dest_room = GameObject("Kitchen", tags=['room'])
        exit_obj = GameObject("north", tags=['exit'], location=self.room)
        self.persistence.add(dest_room)
        self.persistence.add(exit_obj)

        ctx = make_context(
            self.player,
            args="north = Kitchen",
            left_args="north",
            right_args="Kitchen"
        )
        await cmd_link(ctx)

        assert exit_obj.db.destination == dest_room.id
        assert "now leads to" in ctx.session.messages[0]

    @pytest.mark.asyncio
    async def test_unlink_exit(self):
        """@unlink removes exit destination."""
        exit_obj = GameObject("north", tags=['exit'], location=self.room)
        exit_obj.db.destination = "some-id"
        self.persistence.add(exit_obj)

        ctx = make_context(self.player, args="north")
        await cmd_unlink(ctx)

        assert exit_obj.db.get('destination') is None
        assert "unlinked" in ctx.session.messages[0]


class TestModifyCommands:
    """Test suite for modification OLC commands."""

    def setup_method(self):
        """Set up test environment."""
        self.persistence = MockPersistence()
        use_persistence(self.persistence)

        self.room = GameObject("Test Room", tags=['room'])
        self.player = GameObject("Builder", tags=['player'], location=self.room)
        self.sword = GameObject("sword", tags=['thing'], location=self.room)
        self.persistence.add(self.room)
        self.persistence.add(self.player)
        self.persistence.add(self.sword)

    @pytest.mark.asyncio
    async def test_desc_set(self):
        """@desc sets object description."""
        ctx = make_context(
            self.player,
            args="sword = A shiny blade",
            left_args="sword",
            right_args="A shiny blade"
        )
        await cmd_desc(ctx)

        assert self.sword.description == "A shiny blade"
        assert "Description set" in ctx.session.messages[0]

    @pytest.mark.asyncio
    async def test_desc_clear(self):
        """@desc with no value clears description."""
        self.sword.description = "Old description"

        ctx = make_context(
            self.player,
            args="sword =",
            left_args="sword",
            right_args=""
        )
        await cmd_desc(ctx)

        assert self.sword.description == ""
        assert "cleared" in ctx.session.messages[0]

    @pytest.mark.asyncio
    async def test_name_rename(self):
        """@name renames an object."""
        ctx = make_context(
            self.player,
            args="sword = Excalibur",
            left_args="sword",
            right_args="Excalibur"
        )
        await cmd_name(ctx)

        assert self.sword.name == "Excalibur"
        assert "Renamed" in ctx.session.messages[0]

    @pytest.mark.asyncio
    async def test_set_attribute_int(self):
        """@set parses integer values."""
        ctx = make_context(
            self.player,
            args="sword/damage = 10",
            left_args="sword/damage",
            right_args="10"
        )
        await cmd_set(ctx)

        assert self.sword.db.damage == 10
        assert isinstance(self.sword.db.damage, int)

    @pytest.mark.asyncio
    async def test_set_attribute_bool(self):
        """@set parses boolean values."""
        ctx = make_context(
            self.player,
            args="sword/magical = true",
            left_args="sword/magical",
            right_args="true"
        )
        await cmd_set(ctx)

        assert self.sword.db.magical is True

    @pytest.mark.asyncio
    async def test_set_attribute_string(self):
        """@set stores strings when not parseable."""
        ctx = make_context(
            self.player,
            args="sword/material = steel",
            left_args="sword/material",
            right_args="steel"
        )
        await cmd_set(ctx)

        assert self.sword.db.material == "steel"

    @pytest.mark.asyncio
    async def test_set_clear_attribute(self):
        """@set with no value clears attribute."""
        self.sword.db.damage = 10

        ctx = make_context(
            self.player,
            args="sword/damage =",
            left_args="sword/damage",
            right_args=""
        )
        await cmd_set(ctx)

        assert self.sword.db.get('damage') is None

    @pytest.mark.asyncio
    async def test_wipe_clears_all(self):
        """@wipe clears all attributes."""
        self.sword.db.damage = 10
        self.sword.db.material = "steel"
        self.sword.db.magical = True

        ctx = make_context(self.player, args="sword")
        await cmd_wipe(ctx)

        assert self.sword.db.get('damage') is None
        assert self.sword.db.get('material') is None
        assert self.sword.db.get('magical') is None
        assert "Wiped 3 attribute(s)" in ctx.session.messages[0]

    @pytest.mark.asyncio
    async def test_parent_set(self):
        """@parent sets object parent."""
        base_weapon = GameObject("Base Weapon", tags=['thing'])
        self.persistence.add(base_weapon)

        ctx = make_context(
            self.player,
            args="sword = Base Weapon",
            left_args="sword",
            right_args="Base Weapon"
        )
        await cmd_parent(ctx)

        assert self.sword.parent == base_weapon
        assert "inherits from" in ctx.session.messages[0]

    @pytest.mark.asyncio
    async def test_parent_cycle_detection(self):
        """@parent prevents circular inheritance."""
        child = GameObject("child", tags=['thing'])
        self.sword.parent = child

        self.persistence.add(child)

        ctx = make_context(
            self.player,
            args="child = sword",
            left_args="child",
            right_args="sword"
        )
        await cmd_parent(ctx)

        assert "circular" in ctx.session.messages[0]

    @pytest.mark.asyncio
    async def test_tag_add(self):
        """@tag adds a tag to an object."""
        ctx = make_context(
            self.player,
            args="sword = weapon",
            left_args="sword",
            right_args="weapon"
        )
        await cmd_tag(ctx)

        assert self.sword.has_tag('weapon')
        assert "Added tag" in ctx.session.messages[0]

    @pytest.mark.asyncio
    async def test_tag_already_has(self):
        """@tag reports if object already has tag."""
        self.sword.add_tag('weapon')

        ctx = make_context(
            self.player,
            args="sword = weapon",
            left_args="sword",
            right_args="weapon"
        )
        await cmd_tag(ctx)

        assert "already has tag" in ctx.session.messages[0]

    @pytest.mark.asyncio
    async def test_untag_remove(self):
        """@untag removes a tag."""
        self.sword.add_tag('weapon')

        ctx = make_context(
            self.player,
            args="sword = weapon",
            left_args="sword",
            right_args="weapon"
        )
        await cmd_untag(ctx)

        assert not self.sword.has_tag('weapon')
        assert "Removed tag" in ctx.session.messages[0]

    @pytest.mark.asyncio
    async def test_lock_set(self):
        """@lock sets a lock expression."""
        ctx = make_context(
            self.player,
            args="sword = caller.has_tag('knight')",
            left_args="sword",
            right_args="caller.has_tag('knight')"
        )
        await cmd_lock(ctx)

        assert self.sword.locks['basic'] == "caller.has_tag('knight')"

    @pytest.mark.asyncio
    async def test_lock_with_type(self):
        """@lock/<type> sets specific lock type."""
        ctx = make_context(
            self.player,
            args="sword = caller.db.level >= 10",
            left_args="sword",
            right_args="caller.db.level >= 10",
            switches=['use']
        )
        await cmd_lock(ctx)

        assert self.sword.locks['use'] == "caller.db.level >= 10"

    @pytest.mark.asyncio
    async def test_unlock_clears_all(self):
        """@unlock removes all locks."""
        self.sword.locks['default'] = "expr1"
        self.sword.locks['use'] = "expr2"

        ctx = make_context(self.player, args="sword")
        await cmd_unlock(ctx)

        assert len(self.sword.locks) == 0
        assert "Removed 2 lock(s)" in ctx.session.messages[0]


class TestAdminCommands:
    """Test suite for admin OLC commands."""

    def setup_method(self):
        """Set up test environment."""
        self.persistence = MockPersistence()
        use_persistence(self.persistence)

        self.room = GameObject("Test Room", tags=['room'])
        self.room2 = GameObject("Other Room", tags=['room'])
        self.player = GameObject("Admin", tags=['player'], location=self.room)
        self.sword = GameObject("sword", tags=['thing'], location=self.room)
        self.npc = GameObject("Guard", tags=['npc'], location=self.room)

        self.persistence.add(self.room)
        self.persistence.add(self.room2)
        self.persistence.add(self.player)
        self.persistence.add(self.sword)
        self.persistence.add(self.npc)

    @pytest.mark.asyncio
    async def test_teleport_self(self):
        """@teleport moves player to destination."""
        ctx = make_context(self.player, args="Other Room")
        await cmd_teleport(ctx)

        assert self.player.location == self.room2
        assert "teleport to" in ctx.session.messages[0]

    @pytest.mark.asyncio
    async def test_teleport_object(self):
        """@teleport moves object to destination."""
        ctx = make_context(
            self.player,
            args="sword = Other Room",
            left_args="sword",
            right_args="Other Room"
        )
        await cmd_teleport(ctx)

        assert self.sword.location == self.room2
        assert "Teleported sword" in ctx.session.messages[0]

    @pytest.mark.asyncio
    async def test_teleport_to_me(self):
        """@teleport <object> = me moves object to player inventory."""
        ctx = make_context(
            self.player,
            args="sword = me",
            left_args="sword",
            right_args="me"
        )
        await cmd_teleport(ctx)

        assert self.sword.location == self.player

    @pytest.mark.asyncio
    async def test_chown_changes_owner(self):
        """@chown changes object ownership."""
        new_owner = GameObject("NewOwner", tags=['player'])
        self.persistence.add(new_owner)

        ctx = make_context(
            self.player,
            args="sword = NewOwner",
            left_args="sword",
            right_args="NewOwner"
        )
        await cmd_chown(ctx)

        assert self.sword.owner == new_owner
        assert "transferred" in ctx.session.messages[0]

    @pytest.mark.asyncio
    async def test_destroy_removes_object(self):
        """@destroy deletes an object."""
        ctx = make_context(self.player, args="sword")
        await cmd_destroy(ctx)

        assert self.sword in self.persistence.deleted
        assert "Destroyed sword" in ctx.session.messages[0]

    @pytest.mark.asyncio
    async def test_destroy_protected(self):
        """@destroy refuses to delete protected objects."""
        self.sword.add_tag('safe')

        ctx = make_context(self.player, args="sword")
        await cmd_destroy(ctx)

        assert self.sword not in self.persistence.deleted
        assert "protected" in ctx.session.messages[0]

    @pytest.mark.asyncio
    async def test_destroy_recursive(self):
        """@destroy deletes contained objects."""
        chest = GameObject("chest", tags=['thing', 'container'], location=self.room)
        gold = GameObject("gold", tags=['thing'], location=chest)
        self.persistence.add(chest)
        self.persistence.add(gold)

        ctx = make_context(self.player, args="chest")
        await cmd_destroy(ctx)

        assert chest in self.persistence.deleted
        assert gold in self.persistence.deleted

    @pytest.mark.asyncio
    async def test_find_by_name(self):
        """@find searches by name."""
        ctx = make_context(self.player, args="sword")
        await cmd_find(ctx)

        # Should find the sword
        found_msg = False
        for msg in ctx.session.messages:
            if "sword" in msg:
                found_msg = True
                break
        assert found_msg

    @pytest.mark.asyncio
    async def test_find_by_tag(self):
        """@find/tag searches by tag."""
        ctx = make_context(
            self.player,
            args="npc",
            switches=['tag']
        )
        await cmd_find(ctx)

        # Should find the Guard
        found_guard = False
        for msg in ctx.session.messages:
            if "Guard" in msg:
                found_guard = True
                break
        assert found_guard

    @pytest.mark.asyncio
    async def test_examine_shows_details(self):
        """@examine shows object details."""
        self.sword.description = "A test sword"
        self.sword.db.damage = 10
        self.sword.locks['use'] = "true"

        ctx = make_context(self.player, args="sword")
        await cmd_examine_full(ctx)

        messages = "\n".join(ctx.session.messages)
        assert "sword" in messages
        assert "ID:" in messages
        assert "Description:" in messages or "A test sword" in messages


class TestFindObjectGlobal:
    """Test suite for global object lookup."""

    def setup_method(self):
        """Set up test environment."""
        self.persistence = MockPersistence()
        use_persistence(self.persistence)

        self.room = GameObject("Test Room", tags=['room'])
        self.persistence.add(self.room)

    def test_find_by_id(self):
        """find_object_global finds by #id."""
        ctx = make_context(None)
        result = find_object_global(ctx, f"#{self.room.id}")
        assert result == self.room

    def test_find_by_name(self):
        """find_object_global finds by name."""
        ctx = make_context(None)
        result = find_object_global(ctx, "Test Room")
        assert result == self.room

    def test_find_by_name_case_insensitive(self):
        """find_object_global is case insensitive."""
        ctx = make_context(None)
        result = find_object_global(ctx, "test room")
        assert result == self.room

    def test_find_not_found(self):
        """find_object_global returns None when not found."""
        ctx = make_context(None)
        result = find_object_global(ctx, "nonexistent")
        assert result is None


class TestResolveTarget:
    """Test special target resolution (me, here)."""

    def setup_method(self):
        """Set up test environment."""
        self.persistence = MockPersistence()
        use_persistence(self.persistence)

        self.room = GameObject("Test Room", tags=['room'])
        self.player = GameObject("Builder", tags=['player'], location=self.room)
        self.persistence.add(self.room)
        self.persistence.add(self.player)

    @pytest.mark.asyncio
    async def test_resolve_me(self):
        """'me' resolves to the player."""
        ctx = make_context(
            self.player,
            args="me = Test description",
            left_args="me",
            right_args="Test description"
        )
        await cmd_desc(ctx)

        assert self.player.description == "Test description"

    @pytest.mark.asyncio
    async def test_resolve_here(self):
        """'here' resolves to player's location."""
        ctx = make_context(
            self.player,
            args="here = Room description",
            left_args="here",
            right_args="Room description"
        )
        await cmd_desc(ctx)

        assert self.room.description == "Room description"


class TestOLCAgainstRealPersistence:
    """
    Regression: @dig/@open/@link once stored a live GameObject reference in
    exit attributes, which json.dumps could not serialize — every OLC exit
    command crashed against the real database. OLC must build worlds that
    the real PersistenceManager can save, and the exits must still resolve.
    """

    @pytest.mark.asyncio
    async def test_dig_saves_and_exits_resolve(self):
        from realm.core.movement import resolve_exit_destination
        from realm.persistence.manager import PersistenceManager

        pm = PersistenceManager(":memory:")
        await pm.initialize()
        try:
            room = GameObject("Test Room", tags=['room'])
            player = GameObject("Builder", tags=['player', 'builder'], location=room)
            await pm.save(room)
            await pm.save(player)

            ctx = make_context(
                player,
                args="Test Lab = east",
                left_args="Test Lab",
                right_args="east",
                persistence=pm,
            )
            await cmd_dig(ctx)  # raised TypeError before the fix

            messages = "\n".join(ctx.session.messages)
            assert "Room created" in messages
            assert "error" not in messages.lower()

            exit_east = next(
                obj for obj in room.contents
                if obj.has_tag('exit') and obj.name == 'east'
            )
            new_room = resolve_exit_destination(exit_east, pm)
            assert new_room is not None and new_room.name == "Test Lab"

            # The return exit resolves back from the new room.
            exit_west = next(
                obj for obj in new_room.contents
                if obj.has_tag('exit') and obj.name == 'west'
            )
            assert resolve_exit_destination(exit_west, pm) == room
        finally:
            await pm.close()
