"""The examine lock gates the DETAIL sections of examine and look.

The lock existed since the lock system shipped but was never consulted —
`lock_examine` did nothing. Now: name and base description stay the public
surface; detail lines, visual attributes, tags and id are detail, hidden
when the viewer fails the lock. Default is open (matching how the world
always behaved), so only objects a builder explicitly locks change.
"""

from __future__ import annotations

import pytest

from realm.commands import CommandDispatcher
from realm.commands.builtin import register_all_commands
from realm.core.describe import may_examine
from realm.core.objects import GameObject
from realm.gateway.session import Session
from realm.permissions.locks import LockType, set_lock


def _drain(session) -> str:
    output = []
    while not session._output_queue.empty():
        output.append(session._output_queue.get_nowait())
    return "\n".join(output)


class TestExamineLock:

    def setup_method(self):
        self.dispatcher = CommandDispatcher()
        register_all_commands(self.dispatcher)
        self.room = GameObject("Vault", tags=['room'])
        self.player = GameObject("Snoop", tags=['player'], location=self.room)
        self.session = Session()
        self.session.link_player(self.player)

        self.relic = GameObject("relic", tags=['thing'], location=self.room)
        self.relic.description = "A dull grey box."
        self.relic.db.desc_extras = [["", "Fine runes cover the underside."]]

    @pytest.mark.asyncio
    async def test_default_is_open(self):
        await self.dispatcher.dispatch(self.session, "examine relic")
        out = _drain(self.session)
        assert "A dull grey box." in out
        assert "Fine runes cover the underside." in out
        assert "Tags:" in out

    @pytest.mark.asyncio
    async def test_locked_examine_shows_only_the_surface(self):
        set_lock(self.relic, LockType.EXAMINE, "False")
        await self.dispatcher.dispatch(self.session, "examine relic")
        out = _drain(self.session)
        assert "A dull grey box." in out              # public surface stays
        assert "can't make out any further detail" in out
        assert "Fine runes" not in out                # detail hidden
        assert "Tags:" not in out
        assert self.relic.id not in out

    @pytest.mark.asyncio
    async def test_locked_look_still_shows_description(self):
        set_lock(self.relic, LockType.EXAMINE, "False")
        await self.dispatcher.dispatch(self.session, "look relic")
        out = _drain(self.session)
        assert "A dull grey box." in out
        assert "Fine runes" not in out

    @pytest.mark.asyncio
    async def test_lock_expression_can_admit_a_viewer(self):
        set_lock(self.relic, LockType.EXAMINE, "caller.has_tag('scholar')")
        await self.dispatcher.dispatch(self.session, "examine relic")
        assert "Fine runes" not in _drain(self.session)

        self.player.add_tag('scholar')
        await self.dispatcher.dispatch(self.session, "examine relic")
        assert "Fine runes" in _drain(self.session)

    def test_staff_bypass(self):
        set_lock(self.relic, LockType.EXAMINE, "False")
        admin = GameObject("Warden", tags=['player', 'admin'],
                           location=self.room)
        assert may_examine(self.relic, admin)         # LOCK_BYPASS
        assert not may_examine(self.relic, self.player)
