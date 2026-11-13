"""
The softcode function registry (KERNEL_PLAN 3.1, 3.2).

A function is declared once, with its flags. The three sets below were
copied from the hand-kept lists the registry replaced (``to_dict()``,
``_READONLY``, ``_HARM_GATED``) on 2026-11-13; the registry must reproduce
them exactly. ``me``, ``here`` and ``enactor`` are context names, not
functions, so they are not in the registry.
"""

from __future__ import annotations

import pytest

from realm.scripting.functions import ScriptFrame
from realm.scripting.registry import registered, softcode_function, unregister

CONTEXT_NAMES = {"me", "here", "enactor"}

TO_DICT = {
    'V', 'act', 'add_tag', 'adjust_credits', 'adjust_disposition', 'ansi',
    'apply_effect', 'attach_behavior', 'band', 'behaviors', 'call',
    'cancel_wait', 'capstr', 'cast', 'ceil', 'check_roll', 'clamp',
    'clear_lock', 'contents', 'contest', 'controls', 'create_obj', 'credits',
    'damage', 'decr', 'del_attr', 'destroy_obj', 'detach_behavior', 'dice',
    'disposition', 'enactor', 'enter_instance', 'enter_wilderness', 'escape',
    'eval_attr', 'exits', 'expire', 'extract', 'first', 'floor', 'force',
    'get', 'get_attr', 'has_attr', 'has_entitlement', 'has_tag', 'heal',
    'here', 'highest', 'if_else', 'incr', 'last', 'lcfirst', 'left', 'loc',
    'margin_over', 'margin_under', 'me', 'member', 'mid', 'move_to', 'name',
    'net_successes', 'now', 'oemit', 'oob', 'owner', 'pemit', 'prompt',
    'rand', 'reaction_roll', 'remit', 'remove_effect', 'remove_tag', 'repeat',
    'replace', 'rest', 'right', 'roll', 'search_world', 'set_attr',
    'set_lock', 'setdiff', 'setinter', 'setunion', 'skill_check',
    'start_combat', 'strlen', 'switch', 'tag_value', 'tag_values', 'tags',
    'teleport_obj', 'test_lock', 'transfer_credits', 'trim', 'ucfirst',
    'wait', 'words', 'zone_rooms', 'zones_of',
}

READONLY = {
    'V', 'ansi', 'band', 'capstr', 'ceil', 'check_roll', 'clamp', 'contents',
    'contest', 'controls', 'credits', 'dice', 'disposition', 'enactor',
    'escape', 'exits', 'extract', 'first', 'floor', 'get', 'get_attr',
    'has_attr', 'has_entitlement', 'has_tag', 'here', 'highest', 'if_else',
    'last', 'lcfirst', 'left', 'loc', 'margin_over', 'margin_under', 'me',
    'member', 'mid', 'name', 'net_successes', 'now', 'owner', 'rand',
    'repeat', 'replace', 'rest', 'right', 'roll', 'search_world', 'setdiff',
    'setinter', 'setunion', 'skill_check', 'strlen', 'switch', 'tag_value',
    'tag_values', 'tags', 'test_lock', 'trim', 'ucfirst', 'words',
    'zone_rooms', 'zones_of',
}

HARM = {'adjust_credits', 'apply_effect', 'damage', 'remove_effect'}

# Added after the copy: the subject helpers (KERNEL_PLAN 3.3) and
# use_ability (3.5, harm-gated).
ADDED = {'skill', 'check'}
TO_DICT |= ADDED | {'use_ability'}
READONLY |= ADDED
HARM |= {'use_ability'}


class TestParityWithTheOldLists:

    def test_registry_holds_every_exported_function(self):
        assert set(registered()) == TO_DICT - CONTEXT_NAMES

    def test_readonly_flags(self):
        flagged = {n for n, f in registered().items() if f.readonly}
        assert flagged == READONLY - CONTEXT_NAMES

    def test_harm_flags(self):
        assert {n for n, f in registered().items() if f.harm} == HARM

    def test_to_dict_is_unchanged(self):
        assert set(ScriptFrame().to_dict()) == TO_DICT

    def test_readonly_dict_is_unchanged(self):
        assert set(ScriptFrame().readonly_dict()) == READONLY

    def test_every_function_has_a_group(self):
        assert all(f.group for f in registered().values())


class TestRegistration:

    def test_native_function_joins_the_vocabulary(self):
        @softcode_function(group="Game", readonly=True)
        def triple(x):
            return 3 * x

        try:
            entry = registered()["triple"]
            assert entry.readonly and not entry.harm and not entry.takes_frame
            assert ScriptFrame().to_dict()["triple"](2) == 6
            assert "triple" in ScriptFrame().readonly_dict()
        finally:
            unregister("triple")

    def test_taken_name_raises(self):
        with pytest.raises(ValueError, match="controls"):
            @softcode_function("controls")
            def mine(*args):
                return True

    def test_replace_true_overrides(self):
        from realm.scripting import registry
        original = registered()["capstr"]

        @softcode_function("capstr", group="Text", readonly=True, replace=True)
        def shout(text):
            return text.upper()

        try:
            assert ScriptFrame().to_dict()["capstr"]("hi") == "HI"
        finally:
            registry._REGISTRY["capstr"] = original
