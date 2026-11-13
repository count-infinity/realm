"""
Softcode functions: Space-separated list functions.

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
def first(lst: list | str, delimiter: str = ' ') -> str:
    """Get first element of list or first word of string.

    Example: first('north south east') # 'north'
    """
    if isinstance(lst, list):
        return str(lst[0]) if lst else ""
    parts = str(lst).split(delimiter)
    return parts[0] if parts else ""

@softfn(takes_frame=False, group='Text', readonly=True)
def rest(lst: list | str, delimiter: str = ' ') -> str | list:
    """Get all but first element.

    Example: rest('north south east')  # 'south east'
    """
    if isinstance(lst, list):
        return lst[1:]
    parts = str(lst).split(delimiter)
    return delimiter.join(parts[1:])

@softfn(takes_frame=False, group='Text', readonly=True)
def last(lst: list | str, delimiter: str = ' ') -> str:
    """Get last element.

    Example: last('north south east')  # 'east'
    """
    if isinstance(lst, list):
        return str(lst[-1]) if lst else ""
    parts = str(lst).split(delimiter)
    return parts[-1] if parts else ""

@softfn(takes_frame=False, group='Text', readonly=True)
def words(text: str, delimiter: str = ' ') -> int:
    """Count words/elements in text.

    Example: words('a b c')            # 3
    """
    if not text:
        return 0
    return len(text.split(delimiter))

@softfn(takes_frame=False, group='Text', readonly=True)
def member(item: str, lst: list | str, delimiter: str = ' ') -> int:
    """
    Find position of item in list (1-indexed, 0 if not found).

    Example: member('south', 'north south east')  # 2
    """
    if isinstance(lst, str):
        lst = lst.split(delimiter)
    try:
        return lst.index(item) + 1
    except ValueError:
        return 0

@softfn(takes_frame=False, group='Text', readonly=True)
def extract(lst: list | str, position: int, delimiter: str = ' ') -> str:
    """Get element at position (1-indexed).

    Example: extract('a b c', 2)       # 'b'
    """
    if isinstance(lst, str):
        lst = lst.split(delimiter)
    idx = position - 1
    if 0 <= idx < len(lst):
        return str(lst[idx])
    return ""

@softfn(takes_frame=False, group='Text', readonly=True)
def setunion(list1: str, list2: str, delimiter: str = ' ') -> str:
    """Union of two space-separated lists.

    Example: setunion('a b', 'b c')    # 'a b c'
    """
    set1 = set(list1.split(delimiter)) if list1 else set()
    set2 = set(list2.split(delimiter)) if list2 else set()
    return delimiter.join(sorted(set1 | set2))

@softfn(takes_frame=False, group='Text', readonly=True)
def setinter(list1: str, list2: str, delimiter: str = ' ') -> str:
    """Intersection of two lists.

    Example: setinter('a b', 'b c')    # 'b'
    """
    set1 = set(list1.split(delimiter)) if list1 else set()
    set2 = set(list2.split(delimiter)) if list2 else set()
    return delimiter.join(sorted(set1 & set2))

@softfn(takes_frame=False, group='Text', readonly=True)
def setdiff(list1: str, list2: str, delimiter: str = ' ') -> str:
    """Difference of two lists (in list1 but not list2).

    Example: setdiff('a b', 'b c')     # 'a'
    """
    set1 = set(list1.split(delimiter)) if list1 else set()
    set2 = set(list2.split(delimiter)) if list2 else set()
    return delimiter.join(sorted(set1 - set2))
