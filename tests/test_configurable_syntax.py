"""
Configurable softcode surface syntax: the $-command sigil, the ^listen
sigil, and the | color-markup marker are game settings (COMMAND_SIGIL /
LISTEN_SIGIL / MARKUP_MARKER in config.py), joining INLINE_OPEN/CLOSE.
Defaults unchanged; a world that wants literal pipes in its prose (or
'$' in its economy text) remaps them at boot.
"""

from __future__ import annotations

import pytest

from realm.core import markup
from realm.core.markup import set_markup_marker, wrap
from realm.scripting.triggers import (
    TriggerManager,
    get_trigger_sigils,
    set_trigger_sigils,
)


class TestTriggerSigils:

    def test_defaults(self):
        assert get_trigger_sigils() == ('$', '^')
        tm = TriggerManager()
        assert tm._parse_command_trigger('$greet:say hi') is not None
        assert tm._parse_listen_trigger('^*gold*:say mine') is not None

    def test_remapped_sigils_parse_and_defaults_go_inert(self):
        set_trigger_sigils(command='!', listen='~')
        try:
            tm = TriggerManager()
            cmd = tm._parse_command_trigger('!greet *:say hi %0')
            assert cmd is not None and cmd._pattern == 'greet *'
            listen = tm._parse_listen_trigger('~*gold*:say mine')
            assert listen is not None and listen._pattern == '*gold*'
            # The old sigils are now just text, not triggers.
            assert tm._parse_command_trigger('$greet:say hi') is None
            assert tm._parse_listen_trigger('^*gold*:say mine') is None
        finally:
            set_trigger_sigils()

    def test_sigils_of_any_length(self):
        """1 char or 10 — the parser slices by sigil length, never
        assumes a single character."""
        for sigil in ('$$', '!!!', '$' * 10, '<==>'):
            set_trigger_sigils(command=sigil)
            try:
                tm = TriggerManager()
                cmd = tm._parse_command_trigger(f'{sigil}greet:say hi')
                assert cmd is not None and cmd._pattern == 'greet'
                # A partial sigil is not a trigger.
                assert tm._parse_command_trigger(
                    f'{sigil[:-1]}greet:say hi') is None or len(sigil) == 1
            finally:
                set_trigger_sigils()

    def test_bad_sigils_fail_loud(self):
        with pytest.raises(ValueError):
            set_trigger_sigils(command='go')       # alphanumeric
        with pytest.raises(ValueError):
            set_trigger_sigils(listen='')          # empty
        with pytest.raises(ValueError):
            set_trigger_sigils(command='! ')       # whitespace
        with pytest.raises(ValueError):
            set_trigger_sigils(command='!' * 17)   # beyond the sanity cap
        with pytest.raises(ValueError):
            set_trigger_sigils(command='::')       # colon breaks the
        #                                            pattern:action split
        assert get_trigger_sigils() == ('$', '^')  # nothing half-applied


@pytest.mark.asyncio
class TestTriggerSigilsEndToEnd:

    async def test_remapped_command_sigil_via_dispatcher(self):
        from realm.testing import Simulator
        set_trigger_sigils(command='!')
        try:
            sim = Simulator()
            try:
                room = sim.room("Hall")
                alice = sim.player("Alice", location=room)
                sign = sim.obj("a sign", location=room)
                sign.db.set("cmd_ponder", "!ponder:say The sign creaks.")
                await sim.do(alice, "ponder")
                assert any("creaks" in line for line in sim.seen(alice))
                # And the default sigil is inert under the remap.
                sign.db.set("cmd_mutter", "$mutter:say Should not fire.")
                await sim.do(alice, "mutter")
                assert not any("Should not fire" in line
                               for line in sim.seen(alice))
            finally:
                sim.close()
        finally:
            set_trigger_sigils()


class TestMarkupMarker:

    def test_default_wrap_and_roundtrip(self):
        assert wrap('c', 'Lab') == '|cLab|n'
        assert markup.strip('|cLab|n') == 'Lab'
        assert '\x1b[' in markup.to_ansi('|rX|n')

    def test_remapped_marker(self):
        set_markup_marker('~')
        try:
            assert wrap('g', 'ok') == '~gok~n'
            assert markup.strip('~gok~n') == 'ok'
            assert '\x1b[' in markup.to_ansi('~rX~n')
            # Pipes are now literal prose — untouched by every renderer.
            table_row = '| hp | 10 |'
            assert markup.strip(table_row) == table_row
            assert markup.to_ansi(table_row) == table_row
            # The escape rule follows the marker: doubled = literal.
            assert markup.strip('~~tilde') == '~tilde'
        finally:
            set_markup_marker()

    def test_engine_emitters_follow_the_marker(self):
        """render_room and friends emit via wrap(), so a remapped
        marker never leaks stale '|c' literals to players."""
        from realm.core.objects import GameObject
        from realm.core.render import render_room

        set_markup_marker('~')
        try:
            room = GameObject("Vault", tags=["room"])
            viewer = GameObject("Alice", tags=["player"], location=room)
            out = render_room(room, viewer)
            assert '~cVault~n' in out
            assert '|c' not in out
            assert markup.strip(out).count('Vault') == 1
        finally:
            set_markup_marker()

    def test_multichar_marker(self):
        """A marker of any length: codes read as <marker><letter>, the
        doubled-marker escape follows, partial markers stay literal."""
        set_markup_marker('%%')
        try:
            assert wrap('r', 'hot') == '%%rhot%%n'
            assert markup.strip('%%rhot%%n') == 'hot'
            assert '\x1b[0;31m' in markup.to_ansi('%%rhot%%n')
            assert markup.strip('%%%%escaped') == '%%escaped'  # doubled
            assert markup.strip('50% done') == '50% done'      # partial:
        finally:                                               # literal
            set_markup_marker()

    def test_bad_marker_fails_loud(self):
        for bad in ('', 'a', '7', ' ', '|' * 17, '~a'):
            with pytest.raises(ValueError):
                set_markup_marker(bad)
        assert markup.MARKER == '|'


class TestSettingsCarrySyntax:

    def test_defaults(self):
        from realm.config.loader import Settings
        s = Settings()
        assert (s.command_sigil, s.listen_sigil, s.markup_marker) == \
            ('$', '^', '|')
        assert (s.inline_open, s.inline_close) == ('[[', ']]')
