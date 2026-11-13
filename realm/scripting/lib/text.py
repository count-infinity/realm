"""
Softcode functions: String functions.

Each function is registered with ``@softfn``; one that takes the run's
``ScriptFrame`` as ``frame`` reads the executor, enactor, store and queue
from it. See ``realm/scripting/registry.py`` for the flags.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.scripting.registry import softfn

if TYPE_CHECKING:
    pass

@softfn(takes_frame=False, group='Text', readonly=True)
def ucfirst(text: str) -> str:
    """Capitalize first character.

    Example: ucfirst('hello')          # 'Hello'
    """
    if not text:
        return ""
    return text[0].upper() + text[1:]

@softfn(takes_frame=False, group='Text', readonly=True)
def lcfirst(text: str) -> str:
    """Lowercase first character.

    Example: lcfirst('Hello')          # 'hello'
    """
    if not text:
        return ""
    return text[0].lower() + text[1:]

@softfn(takes_frame=False, group='Text', readonly=True)
def capstr(text: str) -> str:
    """Capitalize each word.

    Example: capstr('the iron king')   # 'The Iron King'
    """
    return text.title()

@softfn(takes_frame=False, group='Text', readonly=True)
def repeat(text: str, count: int) -> str:
    """Repeat text N times.

    Example: repeat('-', 40)
    """
    count = max(0, min(count, 1000))  # Limit to prevent abuse
    return text * count

@softfn(takes_frame=False, group='Text', readonly=True)
def strlen(text: str) -> int:
    """Get string length.

    Example: strlen(name(enactor))
    """
    return len(str(text))

@softfn(takes_frame=False, group='Text', readonly=True)
def mid(text: str, start: int, length: int) -> str:
    """Extract substring (1-indexed like MUSH).

    Example: mid('lighthouse', 5, 5)   # 'house'
    """
    start = max(0, start - 1)  # Convert to 0-indexed
    return text[start:start + length]

@softfn(takes_frame=False, group='Text', readonly=True)
def left(text: str, length: int) -> str:
    """Get leftmost N characters.

    Example: left('lighthouse', 5)     # 'light'
    """
    return text[:length]

@softfn(takes_frame=False, group='Text', readonly=True)
def right(text: str, length: int) -> str:
    """Get rightmost N characters.

    Example: right('lighthouse', 5)    # 'house'
    """
    return text[-length:] if length > 0 else ""

@softfn(takes_frame=False, group='Text', readonly=True)
def trim(text: str) -> str:
    """Remove leading/trailing whitespace.

    Example: trim('  hello  ')
    """
    return text.strip()

@softfn(takes_frame=False, group='Text', readonly=True)
def replace(text: str, old: str, new: str) -> str:
    """Replace all occurrences of old with new.

    Example: replace(arg0, 'gold', 'lead')
    """
    return text.replace(old, new)
