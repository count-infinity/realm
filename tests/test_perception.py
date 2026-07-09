"""
Tests for the perception system: darkness/nightvision/light,
invisibility, per-looker message rendering, and sight-gated targeting.

The core promise: every naming surface — messages, room display,
targeting — routes through the same rules, so a hidden actor is
"Someone" in messages, absent from look, and untargetable, all at once.
"""

from __future__ import annotations

import pytest

from realm.commands.base import find_object, find_player
from realm.commands.builtin.communication import cmd_say
from realm.commands.builtin.inventory import cmd_get
from realm.core.objects import GameObject
from realm.core.perception import can_see, can_see_room, perceived_name, room_is_lit
from realm.core.propagation import reset_engine
from realm.core.render import render_room
from realm.gateway.session import Session
from realm.server.dispatcher import CommandContext, CommandDispatcher


@pytest.fixture(autouse=True)
def fresh_propagation_engine():
    reset_engine()
    yield
    reset_engine()


def make_player(name: str, location: GameObject | None = None) -> tuple[GameObject, Session]:
    player = GameObject(name=name, location=location)
    player.add_tag("player")
    sess = Session(protocol="test", address="127.0.0.1")
    sess.link_player(player)
    return player, sess


def drain(sess: Session) -> list[str]:
    out: list[str] = []
    while not sess._output_queue.empty():
        out.append(sess._output_queue.get_nowait())
    return out


def make_ctx(sess: Session, args: str = "") -> CommandContext:
    dispatcher = CommandDispatcher()
    return CommandContext(
        session=sess,
        player=sess.player,
        raw_input=args,
        command_name="test",
        args=args,
        dispatcher=dispatcher,
    )


# --- Rules ---------------------------------------------------------------------


class TestPerceptionRules:

    def test_normal_room_is_lit(self):
        assert room_is_lit(GameObject("Plaza", tags=["room"]))

    def test_dark_room_is_unlit(self):
        assert not room_is_lit(GameObject("Cellar", tags=["room", "dark"]))

    def test_light_source_in_room_lights_it(self):
        cellar = GameObject("Cellar", tags=["room", "dark"])
        GameObject("torch", location=cellar, tags=["thing", "light"])
        assert room_is_lit(cellar)

    def test_wielded_light_source_lights_room(self):
        cellar = GameObject("Cellar", tags=["room", "dark"])
        carrier, _ = make_player("Alice", location=cellar)
        # A held-up (wielded) torch lights the way...
        GameObject("torch", location=carrier, tags=["thing", "light", "wielded"])
        assert room_is_lit(cellar)

    def test_carried_but_unwielded_light_does_not_light(self):
        cellar = GameObject("Cellar", tags=["room", "dark"])
        carrier, _ = make_player("Alice", location=cellar)
        # ...but a lantern buried in the pack does not.
        GameObject("lantern", location=carrier, tags=["thing", "light"])
        assert not room_is_lit(cellar)

    def test_nightvision_sees_dark_room(self):
        cellar = GameObject("Cellar", tags=["room", "dark"])
        alice, _ = make_player("Alice", location=cellar)
        assert not can_see_room(alice, cellar)
        alice.add_tag("nightvision")
        assert can_see_room(alice, cellar)

    def test_darkness_hides_objects(self):
        cellar = GameObject("Cellar", tags=["room", "dark"])
        gem = GameObject("gem", location=cellar, tags=["thing"])
        alice, _ = make_player("Alice", location=cellar)
        assert not can_see(alice, gem)
        alice.add_tag("nightvision")
        assert can_see(alice, gem)

    def test_invisible_needs_see_invisible(self):
        room = GameObject("Plaza", tags=["room"])
        ghost, _ = make_player("Ghost", location=room)
        ghost.add_tag("invisible")
        alice, _ = make_player("Alice", location=room)

        assert not can_see(alice, ghost)
        alice.add_tag("see_invisible")
        assert can_see(alice, ghost)

    def test_admin_sees_everything(self):
        cellar = GameObject("Cellar", tags=["room", "dark"])
        ghost, _ = make_player("Ghost", location=cellar)
        ghost.add_tag("invisible")
        admin, _ = make_player("Odin", location=cellar)
        admin.add_tag("admin")

        assert can_see_room(admin, cellar)
        assert can_see(admin, ghost)

    def test_you_always_see_yourself(self):
        cellar = GameObject("Cellar", tags=["room", "dark"])
        alice, _ = make_player("Alice", location=cellar)
        assert can_see(alice, alice)

    def test_perceived_name_masks(self):
        room = GameObject("Plaza", tags=["room"])
        ghost, _ = make_player("Ghost", location=room)
        ghost.add_tag("invisible")
        gem = GameObject("gem", location=room, tags=["thing", "invisible"])
        alice, _ = make_player("Alice", location=room)

        assert perceived_name(ghost, alice) == "Someone"
        assert perceived_name(gem, alice) == "something"
        assert perceived_name(ghost, None) == "Ghost"


# --- Per-looker messages ---------------------------------------------------------


@pytest.mark.asyncio
class TestPerLookerMessages:

    async def test_invisible_speaker_reads_as_someone(self):
        room = GameObject("Plaza", tags=["room"])
        alice, sess_a = make_player("Alice", location=room)
        alice.add_tag("invisible")
        bob, sess_b = make_player("Bob", location=room)

        await cmd_say(make_ctx(sess_a, "psst"))

        assert drain(sess_a) == ['You say, "psst"']
        assert drain(sess_b) == ['Someone says, "psst"']

    async def test_two_bystanders_see_different_lines(self):
        """The point of per-looker rendering: same action, different text."""
        room = GameObject("Plaza", tags=["room"])
        alice, sess_a = make_player("Alice", location=room)
        alice.add_tag("invisible")
        bob, sess_b = make_player("Bob", location=room)
        eve, sess_e = make_player("Eve", location=room)
        eve.add_tag("see_invisible")

        await cmd_say(make_ctx(sess_a, "hello"))

        assert drain(sess_b) == ['Someone says, "hello"']
        assert drain(sess_e) == ['Alice says, "hello"']

    async def test_unseen_actor_get_masks_with_no_article(self):
        room = GameObject("Plaza", tags=["room"])
        alice, sess_a = make_player("Alice", location=room)
        alice.add_tag("invisible")
        bob, sess_b = make_player("Bob", location=room)
        GameObject("apple", location=room, tags=["thing"])

        await cmd_get(make_ctx(sess_a, "apple"))

        assert drain(sess_a) == ["You pick up an apple."]
        assert drain(sess_b) == ["Someone picks up an apple."]


# --- Rendering -------------------------------------------------------------------


class TestDarknessRendering:

    def test_pitch_black_room(self):
        cellar = GameObject("Cellar", tags=["room", "dark"])
        GameObject("gem", location=cellar, tags=["thing"])
        alice, _ = make_player("Alice", location=cellar)

        text = render_room(cellar, alice)

        assert text == "It is pitch black here. You can't see a thing."

    def test_nightvision_renders_normally(self):
        cellar = GameObject("Cellar", tags=["room", "dark"])
        GameObject("gem", location=cellar, tags=["thing"])
        alice, _ = make_player("Alice", location=cellar)
        alice.add_tag("nightvision")

        text = render_room(cellar, alice)

        assert "Cellar" in text and "a gem" in text

    def test_torch_lights_room_for_everyone(self):
        cellar = GameObject("Cellar", tags=["room", "dark"])
        GameObject("gem", location=cellar, tags=["thing"])
        alice, _ = make_player("Alice", location=cellar)
        GameObject("torch", location=alice, tags=["thing", "light", "wielded"])

        assert "a gem" in render_room(cellar, alice)

    def test_invisible_object_hidden_from_look(self):
        room = GameObject("Plaza", tags=["room"])
        GameObject("gem", location=room, tags=["thing", "invisible"])
        alice, _ = make_player("Alice", location=room)

        assert "gem" not in render_room(room, alice)

    def test_secret_exit_hidden_from_exits_line(self):
        room = GameObject("Plaza", tags=["room"])
        GameObject("north", location=room, tags=["exit"])
        GameObject("bookcase", location=room, tags=["exit", "invisible"])
        alice, _ = make_player("Alice", location=room)

        text = render_room(room, alice)

        assert "north" in text and "Exits:" in text
        assert "bookcase" not in text


# --- Targeting -------------------------------------------------------------------


@pytest.mark.asyncio
class TestSightGatedTargeting:

    async def test_cannot_target_in_darkness(self):
        cellar = GameObject("Cellar", tags=["room", "dark"])
        GameObject("gem", location=cellar, tags=["thing"])
        alice, sess = make_player("Alice", location=cellar)

        assert find_object(make_ctx(sess), "gem") is None

        alice.add_tag("nightvision")
        assert find_object(make_ctx(sess), "gem") is not None

    async def test_cannot_target_invisible_item(self):
        room = GameObject("Plaza", tags=["room"])
        GameObject("gem", location=room, tags=["thing", "invisible"])
        alice, sess = make_player("Alice", location=room)

        assert find_object(make_ctx(sess), "gem") is None

    async def test_cannot_whisper_to_unseen_player(self):
        room = GameObject("Plaza", tags=["room"])
        ghost, _ = make_player("Ghost", location=room)
        ghost.add_tag("invisible")
        alice, sess = make_player("Alice", location=room)

        assert find_player(make_ctx(sess), "Ghost") is None

    async def test_own_inventory_visible_in_darkness(self):
        cellar = GameObject("Cellar", tags=["room", "dark"])
        alice, sess = make_player("Alice", location=cellar)
        GameObject("lockpick", location=alice, tags=["thing"])

        # You can still fumble with what you're carrying.
        assert find_object(make_ctx(sess), "lockpick") is not None

    async def test_secret_exit_still_traversable(self):
        from realm.core.movement import move_through_exit

        room_a = GameObject("Study", tags=["room"])
        room_b = GameObject("Hidden Vault", tags=["room"])
        bookcase = GameObject("bookcase", location=room_a, tags=["exit", "invisible"])
        bookcase.db.destination_obj = room_b
        alice, sess = make_player("Alice", location=room_a)

        # Hidden from the room display...
        assert "bookcase" not in render_room(room_a, alice)
        # ...but usable by name for those in the know.
        moved = await move_through_exit(alice, room_b, exit_obj=bookcase)
        assert moved is True
        assert alice.location is room_b


class TestDisplayMarkers:
    """CoffeeMud-style (glowing)/(magic)/(hidden) markers in room listings."""

    def test_glowing_shown_to_all(self):
        from realm.core.perception import display_markers
        torch = GameObject("torch", tags=["thing", "glowing"])
        bob = GameObject("Bob", tags=["player"])
        assert display_markers(torch, bob) == " (glowing)"

    def test_magic_only_with_detection(self):
        from realm.core.perception import display_markers
        wand = GameObject("wand", tags=["thing", "magic"])
        mundane = GameObject("Mundane", tags=["player"])
        mage = GameObject("Mage", tags=["player", "detect_magic"])
        assert display_markers(wand, mundane) == ""
        assert display_markers(wand, mage) == " (magic)"

    def test_hidden_marker_for_admin_only(self):
        from realm.core.perception import display_markers
        key = GameObject("key", tags=["thing", "hidden"])
        admin = GameObject("Ada", tags=["player", "admin"])
        assert display_markers(key, admin) == " (hidden)"

    def test_room_render_shows_markers(self):
        room = GameObject("Cave", tags=["room"])
        GameObject("crystal", location=room, tags=["thing", "glowing"])
        bob = GameObject("Bob", tags=["player"], location=room)
        assert "(glowing)" in render_room(room, bob)
