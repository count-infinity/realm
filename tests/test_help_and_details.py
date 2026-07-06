"""
Help system (registry-derived) and per-viewer conditional descriptions
(the thief's passive detection).
"""

from __future__ import annotations

import pytest

from realm.core.checks import set_check_resolver
from realm.core.describe import detail_lines
from realm.core.objects import GameObject
from realm.core.propagation import reset_engine
from realm.core.render import render_room
from tests.test_olc import MockPersistence, make_context, use_persistence


@pytest.fixture(autouse=True)
def fresh():
    reset_engine()
    yield
    set_check_resolver(None)
    reset_engine()


def level_resolver(obj, skill, modifier):
    from realm.core.checks import CheckResult, skill_level
    effective = skill_level(obj, skill) + modifier
    return CheckResult(effective >= 10, effective - 10, 10, effective, skill)


class TestDetailLines:

    def test_skill_gated_detail(self):
        set_check_resolver(level_resolver)
        room = GameObject("Cellar", tags=["room"])
        room.db.desc_extras = [
            ["check('observation', -2)", "You notice a small hole in the wall."],
            ["", "Crates are stacked everywhere."],
        ]
        thief = GameObject("thief", tags=["player"])
        thief.db.skill_observation = 14
        mook = GameObject("mook", tags=["player"])
        mook.db.intelligence = 10  # untrained observation: IQ-5 = 5

        assert detail_lines(room, thief) == [
            "You notice a small hole in the wall.",
            "Crates are stacked everywhere.",
        ]
        assert detail_lines(room, mook) == ["Crates are stacked everywhere."]

    def test_stable_skill_threshold_and_tags(self):
        room = GameObject("Crypt", tags=["room"])
        room.db.desc_extras = [
            ["skill('occultism') >= 12", "The sigils are Zohar-derived."],
            ["has_tag('ghost')", "The walls remember you."],
        ]
        scholar = GameObject("scholar", tags=["player"])
        scholar.db.skill_occultism = 14
        ghost = GameObject("ghost", tags=["player", "ghost"])

        assert detail_lines(room, scholar) == ["The sigils are Zohar-derived."]
        assert detail_lines(room, ghost) == ["The walls remember you."]

    def test_render_room_includes_details(self):
        set_check_resolver(level_resolver)
        room = GameObject("Cellar", tags=["room"])
        room.description = "A damp cellar."
        room.db.desc_extras = [["check('observation')", "A glint of metal."]]
        thief = GameObject("thief", tags=["player"], location=room)
        thief.db.skill_observation = 15

        assert "A glint of metal." in render_room(room, thief)

    def test_bad_condition_fails_closed(self):
        room = GameObject("Cellar", tags=["room"])
        room.db.desc_extras = [["__import__('os')", "hacked"],
                               ["not python at all", "broken"]]
        bob = GameObject("Bob", tags=["player"])
        assert detail_lines(room, bob) == []


@pytest.mark.asyncio
class TestDetailCommand:

    def setup_method(self):
        self.persistence = MockPersistence()
        use_persistence(self.persistence)

    async def test_detail_add_and_clear(self):
        from realm.commands.olc.modify import cmd_detail

        room = GameObject("Cellar", tags=["room"])
        bob = GameObject("Bob", tags=["player", "builder"], location=room)

        ctx = make_context(bob, left_args="here",
                           right_args="check('observation', -2) -> You notice a hole.")
        await cmd_detail(ctx)
        assert room.db.get("desc_extras") == [
            ["check('observation', -2)", "You notice a hole."]]

        ctx2 = make_context(bob, left_args="here", switches=["clear"])
        await cmd_detail(ctx2)
        assert room.db.get("desc_extras") is None

    async def test_bad_condition_rejected(self):
        from realm.commands.olc.modify import cmd_detail

        room = GameObject("Cellar", tags=["room"])
        bob = GameObject("Bob", tags=["player", "builder"], location=room)
        ctx = make_context(bob, left_args="here",
                           right_args="getattr(viewer, 'db') -> gotcha")
        await cmd_detail(ctx)
        assert room.db.get("desc_extras") is None
        assert any("Bad condition" in m for m in ctx.session.messages)


@pytest.mark.asyncio
class TestHelp:

    def setup_method(self):
        self.persistence = MockPersistence()
        use_persistence(self.persistence)

    def _ctx(self, player, args=""):
        from realm.commands.builtin import register_all_commands
        ctx = make_context(player, args=args)
        register_all_commands(ctx.dispatcher)
        return ctx

    async def test_help_lists_by_category(self):
        from realm.commands.builtin.utility import cmd_help

        room = GameObject("Plaza", tags=["room"])
        bob = GameObject("Bob", tags=["player"], location=room)
        ctx = self._ctx(bob)
        await cmd_help(ctx)
        text = "\n".join(ctx.session.messages)
        assert "Combat:" in text and "Economy:" in text and "Social:" in text
        assert "@set" not in text  # builder commands hidden from players

    async def test_builders_see_building_category(self):
        from realm.commands.builtin.utility import cmd_help

        room = GameObject("Plaza", tags=["room"])
        bea = GameObject("Bea", tags=["player", "builder"], location=room)
        ctx = self._ctx(bea)
        await cmd_help(ctx)
        text = "\n".join(ctx.session.messages)
        assert "Building:" in text and "@detail" in text

    async def test_help_command_detail_via_alias(self):
        from realm.commands.builtin.utility import cmd_help

        room = GameObject("Plaza", tags=["room"])
        bob = GameObject("Bob", tags=["player"], location=room)
        ctx = self._ctx(bob, args="fasttalk")
        await cmd_help(ctx)
        text = "\n".join(ctx.session.messages)
        assert "usage: fasttalk <npc>" in text

    async def test_help_search_fallback(self):
        from realm.commands.builtin.utility import cmd_help

        room = GameObject("Plaza", tags=["room"])
        bob = GameObject("Bob", tags=["player"], location=room)
        ctx = self._ctx(bob, args="merchant")
        await cmd_help(ctx)
        text = "\n".join(ctx.session.messages)
        assert "Related:" in text and "buy" in text


class TestInlineSoftcode:
    """[[...]] blocks in descriptions: Penn-style inline eval with state."""

    def _cellar(self):
        room = GameObject("Cellar", tags=["room"])
        thief = GameObject("thief", tags=["player"], location=room)
        thief.db.skill_detection = 14
        mook = GameObject("mook", tags=["player"], location=room)
        return room, thief, mook

    def test_simple_substitution(self):
        from realm.scripting.inline import eval_inline

        room, thief, _ = self._cellar()
        room.description = "Dust everywhere. [[result = 'Cobwebs: ' + str(2 + 2)]]"
        assert eval_inline(room.description, room, thief) == \
            "Dust everywhere. Cobwebs: 4"

    def test_memoized_detection_pattern(self):
        """The user's pseudocode, near-verbatim: cache the roll per viewer."""
        from realm.scripting.inline import eval_inline

        set_check_resolver(level_resolver)
        room, thief, mook = self._cellar()
        room.description = (
            "A dusty cellar."
            "[[k = 'det_' + viewer.id; "
            "r = get_attr(me, k) or ('PASS' if check_roll('detection', -2) else 'FAIL'); "
            "set_attr(me, k, r); "
            "result = ' You see a small hole in the wall.' if r == 'PASS' else '']]"
        )

        # Thief passes (skill 14 - 2 >= 10) and the outcome is CACHED.
        assert "small hole" in eval_inline(room.description, room, thief)
        assert room.db.get(f"det_{thief.id}") == "PASS"
        # Mook fails; cached FAIL means no re-roll next look.
        assert "small hole" not in eval_inline(room.description, room, mook)
        assert room.db.get(f"det_{mook.id}") == "FAIL"
        # Cached results stick across looks (no flicker).
        assert "small hole" in eval_inline(room.description, room, thief)
        assert "small hole" not in eval_inline(room.description, room, mook)

    def test_state_writes_respect_authority(self):
        from realm.scripting.inline import eval_inline

        room, thief, _ = self._cellar()
        # The block runs AS the room — it can't rewrite the viewer.
        room.description = "[[result = set_attr(viewer, 'hp', 0)]]"
        out = eval_inline(room.description, room, thief)
        assert out == "False"
        assert thief.db.get("hp") is None

    def test_forbidden_code_fails_closed(self):
        from realm.scripting.inline import eval_inline

        room, thief, _ = self._cellar()
        room.description = "Safe. [[import os; result = 'owned']] Still safe."
        assert eval_inline(room.description, room, thief) == "Safe.  Still safe."

    def test_now_available_for_expiry(self):
        from realm.scripting.inline import eval_inline

        room, thief, _ = self._cellar()
        room.description = "[[result = 'fresh' if now() > 0 else 'stale']]"
        assert eval_inline(room.description, room, thief) == "fresh"

    def test_render_room_evaluates_blocks(self):
        set_check_resolver(level_resolver)
        room, thief, mook = self._cellar()
        room.description = ("A cellar.[[result = ' A glint of metal.' "
                            "if skill('detection') >= 12 else '']]")
        assert "glint of metal" in render_room(room, thief)
        assert "glint of metal" not in render_room(room, mook)

    def test_block_cap(self):
        from realm.scripting.inline import eval_inline

        room, thief, _ = self._cellar()
        room.description = "[[result='x']]" * 20
        assert eval_inline(room.description, room, thief) == "x" * 8


class TestOwnerDelegation:
    """Penn semantics: your objects act with your authority."""

    def test_siblings_trust_each_other(self):
        from realm.permissions.locks import controls
        from realm.scripting.functions import ScriptFunctions

        bob = GameObject("Bob", tags=["player"])
        gadget = GameObject("gadget", owner=bob)
        stash = GameObject("stash", owner=bob)
        assert controls(gadget, stash) is True

        funcs = ScriptFunctions(executor=gadget)
        assert funcs.set_attr(stash, "combo", 1234) is True
        assert stash.db.get("combo") == 1234

    def test_object_wields_builder_owner_powers(self):
        from realm.permissions.locks import controls

        bea = GameObject("Bea", tags=["player", "builder"])
        gadget = GameObject("gadget", owner=bea)
        world_prop = GameObject("fountain")  # unowned world object
        assert controls(gadget, world_prop) is True  # Bea controls it, so...

    def test_strangers_still_denied(self):
        from realm.permissions.locks import controls

        bob = GameObject("Bob", tags=["player"])
        eve = GameObject("Eve", tags=["player"])
        bobs = GameObject("bobs-thing", owner=bob)
        eves = GameObject("eves-thing", owner=eve)
        assert controls(bobs, eves) is False
        assert controls(bobs, eve) is False  # nor Eve herself

    def test_owner_chain_cycles_terminate(self):
        from realm.permissions.locks import controls

        a = GameObject("a")
        b = GameObject("b")
        a.owner = b
        b.owner = a  # pathological cycle — must not recurse forever
        stranger = GameObject("stranger", owner=GameObject("Eve", tags=["player"]))
        assert controls(a, stranger) is False

    def test_inline_block_reaches_sibling_state(self):
        """The user's use case: description code reads/writes the owner's
        other objects."""
        from realm.scripting.inline import eval_inline

        bob = GameObject("Bob", tags=["player"])
        room = GameObject("Study", tags=["room"], owner=bob)
        ledger = GameObject("ledger", tags=["thing"], owner=bob, location=room)
        ledger.db.balance = 42
        room.description = (
            "[[result = 'The ledger shows ' + "
            "str(get_attr(get('ledger'), 'balance')) + ' marks.'; "
            "set_attr(get('ledger'), 'audited', True)]]")

        viewer = GameObject("guest", tags=["player"], location=room)
        out = eval_inline(room.description, room, viewer)
        assert out == "The ledger shows 42 marks."
        assert ledger.db.get("audited") is True  # sibling WRITE via delegation


@pytest.mark.asyncio
class TestChownHalts:

    async def test_chown_halts_scripted_objects(self):
        from realm.commands.olc.admin import cmd_chown

        pers = MockPersistence()
        use_persistence(pers)
        room = GameObject("Plaza", tags=["room"])
        admin = GameObject("Ada", tags=["player", "admin"], location=room)
        eve = GameObject("Eve", tags=["player"], location=room)
        trap = GameObject("music box", location=room, owner=eve)
        trap.db.on_look = "set_attr(me, 'sprung', True)"
        pers.add(admin); pers.add(eve); pers.add(trap)

        ctx = make_context(admin, left_args="music box", right_args="Ada")
        await cmd_chown(ctx)
        assert trap.owner is admin
        assert trap.has_tag("halt")
