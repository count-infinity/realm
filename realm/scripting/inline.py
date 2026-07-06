"""
Inline softcode in descriptions — the PennMUSH bracket, REALM-style.

Any description may embed ``[[ ... ]]`` blocks. At render time each
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
is one line). Blocks don't nest.

Mutations made here mark objects dirty; the periodic persistence sweep
saves them (same durability as every other gameplay mutation). Queued
pemit/remit/oemit deliver immediately; world-op kinds that need the
event loop (combat/force/wait) are dropped with a log — trigger those
from ON_LOOK scripts instead.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)

INLINE_PATTERN = re.compile(r"\[\[(.+?)\]\]", re.S)
MAX_BLOCKS = 8

_SYNC_KINDS = ('pemit', 'remit', 'oemit', 'save')


def eval_inline(text: str, me: GameObject, viewer: GameObject | None) -> str:
    """Render a description's ``[[...]]`` blocks for this viewer."""
    if not text or '[[' not in text:
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

    count = 0

    def substitute(match: re.Match) -> str:
        nonlocal count
        count += 1
        if count > MAX_BLOCKS:
            return ''
        code = match.group(1).strip()
        ctx = ScriptContext(enactor=viewer, executor=me, location=me.location)
        try:
            result, _output = sandbox.execute(code, ctx, functions=namespace)
        except ScriptError as e:
            logger.warning(f"Inline block on {me.name} failed: {e}")
            return ''
        return '' if result is None else str(result)

    rendered = INLINE_PATTERN.sub(substitute, text)

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


__all__ = ["eval_inline", "MAX_BLOCKS"]
