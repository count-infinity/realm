"""
Configurable softcode surface syntax: the $-command sigil, the ^listen
sigil, and the | color-markup marker are game settings (COMMAND_SIGIL /
LISTEN_SIGIL / MARKUP_MARKER in config.py), joining INLINE_OPEN/CLOSE.
Defaults unchanged; a world that wants literal pipes in its prose (or
'$' in its economy text) remaps them in config. Use sites read the
running world's setting; a bad value fails when Settings is built.
"""

from __future__ import annotations

import pytest

from realm.config.loader import Settings
from realm.core import markup
from realm.core.markup import wrap
from realm.core.world import setting
from realm.scripting.triggers import TriggerManager


class TestTriggerSigils:

    def test_defaults(self):
        assert (setting("COMMAND_SIGIL"), setting("LISTEN_SIGIL")) == ('$', '^')
        tm = TriggerManager()
        assert tm._parse_command_trigger('$greet:say hi') is not None
        assert tm._parse_listen_trigger('^*gold*:say mine') is not None

    def test_remapped_sigils_parse_and_defaults_go_inert(self, configure):
        configure(command_sigil='!', listen_sigil='~')
        tm = TriggerManager()
        cmd = tm._parse_command_trigger('!greet *:say hi %0')
        assert cmd is not None and cmd._pattern == 'greet *'
        listen = tm._parse_listen_trigger('~*gold*:say mine')
        assert listen is not None and listen._pattern == '*gold*'
        # The old sigils are now just text, not triggers.
        assert tm._parse_command_trigger('$greet:say hi') is None
        assert tm._parse_listen_trigger('^*gold*:say mine') is None

    def test_sigils_of_any_length(self, configure):
        """1 char or 10 — the parser slices by sigil length, never
        assumes a single character."""
        for sigil in ('$$', '!!!', '$' * 10, '<==>'):
            configure(command_sigil=sigil)
            tm = TriggerManager()
            cmd = tm._parse_command_trigger(f'{sigil}greet:say hi')
            assert cmd is not None and cmd._pattern == 'greet'
            # A partial sigil is not a trigger.
            assert tm._parse_command_trigger(
                f'{sigil[:-1]}greet:say hi') is None or len(sigil) == 1

    @pytest.mark.parametrize("field,bad", [
        ("command_sigil", "go"),        # alphanumeric
        ("listen_sigil", ""),           # empty
        ("command_sigil", "! "),        # whitespace
        ("command_sigil", "!" * 17),    # beyond the sanity cap
        ("command_sigil", "::"),        # colon breaks the pattern:action split
    ])
    def test_bad_sigils_fail_loud(self, field, bad):
        with pytest.raises(ValueError):
            Settings(**{field: bad})


@pytest.mark.asyncio
class TestTriggerSigilsEndToEnd:

    async def test_remapped_command_sigil_via_dispatcher(self):
        from realm.testing import Simulator
        with Simulator(settings=Settings(command_sigil='!')) as sim:
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


class TestMarkupMarker:

    def test_default_wrap_and_roundtrip(self):
        assert wrap('c', 'Lab') == '|cLab|n'
        assert markup.strip('|cLab|n') == 'Lab'
        assert '\x1b[' in markup.to_ansi('|rX|n')

    def test_remapped_marker(self, configure):
        configure(markup_marker='~')
        assert wrap('g', 'ok') == '~gok~n'
        assert markup.strip('~gok~n') == 'ok'
        assert '\x1b[' in markup.to_ansi('~rX~n')
        # Pipes are now literal prose — untouched by every renderer.
        table_row = '| hp | 10 |'
        assert markup.strip(table_row) == table_row
        assert markup.to_ansi(table_row) == table_row
        # The escape rule follows the marker: doubled = literal.
        assert markup.strip('~~tilde') == '~tilde'

    def test_engine_emitters_follow_the_marker(self, configure):
        """render_room and friends emit via wrap(), so a remapped
        marker never leaks stale '|c' literals to players."""
        from realm.core.objects import GameObject
        from realm.core.render import render_room

        configure(markup_marker='~')
        room = GameObject("Vault", tags=["room"])
        viewer = GameObject("Alice", tags=["player"], location=room)
        out = render_room(room, viewer)
        assert '~cVault~n' in out
        assert '|c' not in out
        assert markup.strip(out).count('Vault') == 1

    def test_multichar_marker(self, configure):
        """A marker of any length: codes read as <marker><letter>, the
        doubled-marker escape follows, partial markers stay literal."""
        configure(markup_marker='%%')
        assert wrap('r', 'hot') == '%%rhot%%n'
        assert markup.strip('%%rhot%%n') == 'hot'
        assert '\x1b[0;31m' in markup.to_ansi('%%rhot%%n')
        assert markup.strip('%%%%escaped') == '%%escaped'  # doubled
        assert markup.strip('50% done') == '50% done'      # partial: literal

    @pytest.mark.parametrize("bad", ['', 'a', '7', ' ', '|' * 17, '~a'])
    def test_bad_marker_fails_loud(self, bad):
        with pytest.raises(ValueError):
            Settings(markup_marker=bad)

    def test_the_marker_belongs_to_the_world(self, configure):
        """Closing the world takes its marker with it: nothing to restore."""
        configure(markup_marker='~')
        assert markup.marker() == '~'


def test_no_world_reads_the_defaults():
    assert markup.marker() == '|'
    assert setting("EMOTE_SIGIL") == '/'


class TestSettingsCarrySyntax:

    def test_defaults(self):
        s = Settings()
        assert (s.command_sigil, s.listen_sigil, s.markup_marker) == \
            ('$', '^', '|')
        assert (s.inline_open, s.inline_close) == ('[[', ']]')

    def test_inline_delimiters_must_differ(self):
        with pytest.raises(ValueError, match="must differ"):
            Settings(inline_open='%%', inline_close='%%')

    def test_world_beat_floor(self):
        with pytest.raises(ValueError, match="WORLD_BEAT"):
            Settings(world_beat=0.01)
