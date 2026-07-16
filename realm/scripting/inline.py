"""
Inline softcode in descriptions — the PennMUSH bracket, REALM-style.

Any description may embed ``[[ ... ]]`` blocks (the delimiters are a
game setting — ``INLINE_OPEN``/``INLINE_CLOSE`` in config.py — for
worlds that prefer ``${ ... }`` or similar; everything below uses the
default). At render time each
block runs through the script sandbox PER VIEWER, with the full
ScriptFunctions namespace (get_attr/set_attr/check/skill_check/rand/
now/...), ``me`` = the described object (the block runs with ITS
authority), and ``viewer``/``enactor`` = the looker. Whatever the block
assigns to ``result`` replaces the block; no result = empty string.
Errors and forbidden code fail closed to '' (logged).

The memoized passive-detection idiom, verbatim builder softcode:

    @desc here = A dusty cellar. [[k = 'det_' + viewer.id;
      r = get_attr(me, k) or ('PASS' if check_roll('detection', -2)
                              else 'FAIL');
      set_attr(me, k, r);
      result = 'You see a small hole in the wall.' if r == 'PASS' else '']]

State lives in ordinary attributes — cache outcomes, expire them with
``now()``, whatever you can code. ``;`` separates statements (an @desc
is one line). Blocks don't nest — but the *code inside* one nests
freely: it's Python, so ``fn1(fn2(x), y, fn3())``, nested subscripts
(``words[idx[0]]``), and ``']]'`` inside string literals all work; the
block scanner tracks brackets and quotes rather than stopping at the
first ``]]``.

Mutations made here mark objects dirty; the periodic persistence sweep
saves them (same durability as every other gameplay mutation). Queued
pemit/remit/oemit deliver immediately; world-op kinds that need the
event loop (combat/force/wait) are dropped with a log — trigger those
from ON_LOOK scripts instead.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)

MAX_BLOCKS = 8

_SYNC_KINDS = ('pemit', 'remit', 'oemit', 'save')

# Configurable block delimiters — ``[[ ]]`` by default; a game more at
# home with ``${ }`` (or anything else) sets INLINE_OPEN/INLINE_CLOSE
# in config.py. Ambient module state, wired at server construction like
# the other singletons.
DEFAULT_OPEN = '[['
DEFAULT_CLOSE = ']]'
_open = DEFAULT_OPEN
_close = DEFAULT_CLOSE

# When the closer starts with a bracket character, the scanner tracks
# THAT pair's nesting so code using it survives: subscripts under ]],
# dict/set literals under }, call parens under ).
_BRACKET_FOR_CLOSER = {']': '[', '}': '{', ')': '('}


def set_inline_delimiters(open_: str = DEFAULT_OPEN,
                          close_: str = DEFAULT_CLOSE) -> None:
    """Install the inline-block delimiters (game config). Both must be
    non-empty and distinct-from-each-other strings; a bad pair is a
    config error and raises rather than silently mangling every
    description in the game."""
    global _open, _close
    open_, close_ = str(open_), str(close_)
    if not open_.strip() or not close_.strip():
        raise ValueError("inline delimiters must be non-empty")
    if open_ == close_:
        raise ValueError(
            "inline open and close delimiters must differ "
            f"(both were {open_!r})")
    _open, _close = open_, close_


def get_inline_delimiters() -> tuple[str, str]:
    return _open, _close


def _find_block(text: str, start: int) -> tuple[int, int] | None:
    """Locate the next inline block at or after ``start``.

    The closing delimiter is the first one at bracket-depth zero
    outside any string literal — so nested subscripts (``a[b[0]]``
    under ``]]``), dict literals (``{'a': 1}`` under ``}``), and a
    closer inside quotes don't end the block early (a lazy regex
    would). Returns ``(open_idx, close_idx)`` with ``close_idx`` at the
    first char of the terminator, or None (no block / unterminated —
    an unterminated block stays literal text)."""
    open_idx = text.find(_open, start)
    if open_idx == -1:
        return None
    close_char = _close[0]
    open_bracket = _BRACKET_FOR_CLOSER.get(close_char)
    i = open_idx + len(_open)
    depth = 0
    quote: str | None = None
    n = len(text)
    while i < n:
        ch = text[i]
        if quote is not None:
            if ch == '\\':
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in ('"', "'"):
            quote = ch
        elif open_bracket is not None and ch == open_bracket:
            depth += 1
        elif ch == close_char:
            if depth > 0:
                depth -= 1
            elif text.startswith(_close, i):
                return open_idx, i
            # a lone unmatched closer-char at depth 0 that isn't the
            # full delimiter (']' under ']]'): literal, keep scanning
        i += 1
    return None


def eval_inline(text: str, me: GameObject, viewer: GameObject | None) -> str:
    """Render a description's inline blocks for this viewer."""
    if not text or _open not in text:
        return text

    from realm.persistence.manager import get_active_manager
    from realm.scripting.functions import ScriptFunctions
    from realm.scripting.sandbox import ScriptContext, ScriptError, ScriptSandbox

    sandbox = ScriptSandbox()
    functions = ScriptFunctions(
        enactor=viewer,
        executor=me,
        location=me.location if me.location is not None else me,
        persistence=get_active_manager(),
    )
    namespace = functions.to_dict()
    namespace['viewer'] = viewer
    # check() in conditions rolls AS THE VIEWER (their skills, their fear).
    if viewer is not None:
        from realm.core.checks import check as _check
        from realm.core.checks import skill_level as _skill_level
        namespace['check_roll'] = (
            lambda skill, mod=0: bool(_check(viewer, str(skill), int(mod))))
        namespace['skill'] = lambda name: _skill_level(viewer, str(name))

    def run_block(code: str) -> str:
        ctx = ScriptContext(enactor=viewer, executor=me, location=me.location)
        try:
            result, _output = sandbox.execute(code, ctx, functions=namespace)
        except ScriptError as e:
            logger.warning(f"Inline block on {me.name} failed: {e}")
            return ''
        return '' if result is None else str(result)

    parts: list[str] = []
    pos = 0
    count = 0
    while True:
        found = _find_block(text, pos)
        if found is None:
            break
        open_idx, close_idx = found
        parts.append(text[pos:open_idx])
        count += 1
        if count <= MAX_BLOCKS:
            parts.append(
                run_block(text[open_idx + len(_open):close_idx].strip()))
        pos = close_idx + len(_close)
    parts.append(text[pos:])
    rendered = ''.join(parts)

    # Deliver the message kinds now; drop loop-bound ops with a log.
    for kind, obj, payload in functions.command_queue:
        if kind == 'pemit':
            obj.msg(payload)
        elif kind == 'remit':
            obj.msg_contents(payload)
        elif kind == 'oemit':
            room = me.location
            if room is not None:
                room.msg_contents(payload, exclude=[obj])
        elif kind != 'save':  # dirty-sweep persistence covers saves
            logger.warning(
                f"Inline block on {me.name} queued '{kind}' — not allowed "
                f"in descriptions; use an ON_LOOK script.")
    functions.command_queue.clear()

    return rendered


__all__ = ["eval_inline", "MAX_BLOCKS",
           "set_inline_delimiters", "get_inline_delimiters",
           "DEFAULT_OPEN", "DEFAULT_CLOSE"]
