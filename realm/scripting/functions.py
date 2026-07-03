"""
Built-in script functions for REALM.

These functions are available to user scripts for common operations.
They are injected into the script namespace and provide safe access
to game functionality.

Categories:
- Object access: get(), name(), loc(), owner()
- Attribute access: get_attr(), set_attr(), has_attr()
- Tag operations: has_tag(), tags()
- String operations: ucfirst(), lcfirst(), capstr()
- Math operations: rand(), dice(), clamp()
- List operations: first(), rest(), member(), words()
- Communication: pemit(), remit(), oemit()
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.objects import GameObject


class ScriptFunctions:
    """
    Collection of built-in functions available to scripts.

    These are bound to a specific context (enactor, executor, location)
    and provide safe access to game operations.
    """

    def __init__(
        self,
        enactor: GameObject | None = None,
        executor: GameObject | None = None,
        location: GameObject | None = None,
        persistence: Any = None,  # PersistenceManager
        output_callback: Callable[[str], None] | None = None,
    ):
        self.enactor = enactor
        self.executor = executor
        self.location = location
        self._persistence = persistence
        self._output = output_callback or (lambda x: None)

        # Deliveries queued by communication functions. Scripts execute in a
        # worker thread, so functions must never touch sessions directly —
        # the engine drains this queue on the event loop after execution.
        # Entries: (kind, obj, message) with kind in 'pemit'/'remit'/'oemit'.
        self.command_queue: list[tuple[str, GameObject, str]] = []

    # --- Object lookup ---

    def get(self, spec: str) -> GameObject | None:
        """
        Get an object by ID or name.

        Args:
            spec: Object ID (starting with #) or name

        Returns:
            The GameObject or None if not found
        """
        if not self._persistence:
            return None

        spec = str(spec).strip()

        # ID lookup
        if spec.startswith('#'):
            return self._persistence.get_cached(spec[1:])

        # Name lookup — same tiered matcher as commands; scripts take the
        # first match rather than raising on ambiguity.
        from realm.core.search import match_objects
        matches = match_objects(spec, self._persistence.all_cached()).matches
        return matches[0] if matches else None

    def name(self, obj: GameObject | str | None) -> str:
        """Get an object's name."""
        if obj is None:
            return ""
        if isinstance(obj, str):
            resolved = self.get(obj)
            return resolved.name if resolved else ""
        return obj.name

    def loc(self, obj: GameObject | str | None) -> GameObject | None:
        """Get an object's location."""
        if obj is None:
            return None
        if isinstance(obj, str):
            obj = self.get(obj)
        if obj is None:
            return None
        return obj.location

    def owner(self, obj: GameObject | str | None) -> GameObject | None:
        """Get an object's owner."""
        if obj is None:
            return None
        if isinstance(obj, str):
            obj = self.get(obj)
        if obj is None:
            return None
        return obj.owner

    def contents(self, obj: GameObject | str | None) -> list[GameObject]:
        """Get an object's contents."""
        if obj is None:
            return []
        if isinstance(obj, str):
            obj = self.get(obj)
        if obj is None:
            return []
        return obj.contents

    # --- Attribute access ---

    def get_attr(
        self,
        obj: GameObject | str | None,
        attr_name: str,
        default: Any = None,
    ) -> Any:
        """Get an attribute from an object."""
        if obj is None:
            return default
        if isinstance(obj, str):
            obj = self.get(obj)
        if obj is None:
            return default
        return obj.db.get(attr_name, default)

    def set_attr(
        self,
        obj: GameObject | str | None,
        attr_name: str,
        value: Any,
    ) -> bool:
        """
        Set an attribute on an object.

        Returns True on success, False on failure.
        Note: Requires appropriate permissions (not checked here).
        """
        if obj is None:
            return False
        if isinstance(obj, str):
            obj = self.get(obj)
        if obj is None:
            return False

        obj.db.set(attr_name, value)
        return True

    def has_attr(self, obj: GameObject | str | None, attr_name: str) -> bool:
        """Check if an object has an attribute."""
        if obj is None:
            return False
        if isinstance(obj, str):
            obj = self.get(obj)
        if obj is None:
            return False
        return attr_name in obj.db

    def del_attr(self, obj: GameObject | str | None, attr_name: str) -> bool:
        """Delete an attribute from an object."""
        if obj is None:
            return False
        if isinstance(obj, str):
            obj = self.get(obj)
        if obj is None:
            return False

        if attr_name in obj.db:
            obj.db.delete(attr_name)
            return True
        return False

    # --- Tag operations ---

    def has_tag(self, obj: GameObject | str | None, tag: str) -> bool:
        """Check if an object has a tag."""
        if obj is None:
            return False
        if isinstance(obj, str):
            obj = self.get(obj)
        if obj is None:
            return False
        return obj.has_tag(tag)

    def tags(self, obj: GameObject | str | None) -> list[str]:
        """Get all tags on an object."""
        if obj is None:
            return []
        if isinstance(obj, str):
            obj = self.get(obj)
        if obj is None:
            return []
        return obj.tags.to_list()

    def add_tag(self, obj: GameObject | str | None, tag: str) -> bool:
        """Add a tag to an object."""
        if obj is None:
            return False
        if isinstance(obj, str):
            obj = self.get(obj)
        if obj is None:
            return False
        obj.add_tag(tag)
        return True

    def remove_tag(self, obj: GameObject | str | None, tag: str) -> bool:
        """Remove a tag from an object."""
        if obj is None:
            return False
        if isinstance(obj, str):
            obj = self.get(obj)
        if obj is None:
            return False
        obj.remove_tag(tag)
        return True

    # --- String functions ---

    @staticmethod
    def ucfirst(text: str) -> str:
        """Capitalize first character."""
        if not text:
            return ""
        return text[0].upper() + text[1:]

    @staticmethod
    def lcfirst(text: str) -> str:
        """Lowercase first character."""
        if not text:
            return ""
        return text[0].lower() + text[1:]

    @staticmethod
    def capstr(text: str) -> str:
        """Capitalize each word."""
        return text.title()

    @staticmethod
    def repeat(text: str, count: int) -> str:
        """Repeat text N times."""
        count = max(0, min(count, 1000))  # Limit to prevent abuse
        return text * count

    @staticmethod
    def strlen(text: str) -> int:
        """Get string length."""
        return len(str(text))

    @staticmethod
    def mid(text: str, start: int, length: int) -> str:
        """Extract substring (1-indexed like MUSH)."""
        start = max(0, start - 1)  # Convert to 0-indexed
        return text[start:start + length]

    @staticmethod
    def left(text: str, length: int) -> str:
        """Get leftmost N characters."""
        return text[:length]

    @staticmethod
    def right(text: str, length: int) -> str:
        """Get rightmost N characters."""
        return text[-length:] if length > 0 else ""

    @staticmethod
    def trim(text: str) -> str:
        """Remove leading/trailing whitespace."""
        return text.strip()

    @staticmethod
    def replace(text: str, old: str, new: str) -> str:
        """Replace all occurrences of old with new."""
        return text.replace(old, new)

    # --- Math functions ---

    @staticmethod
    def rand(low: int = 0, high: int = 100) -> int:
        """Random integer between low and high (inclusive)."""
        return random.randint(int(low), int(high))

    @staticmethod
    def dice(num: int = 1, sides: int = 6, modifier: int = 0) -> int:
        """
        Roll dice: NdS+M

        Args:
            num: Number of dice
            sides: Sides per die
            modifier: Added to total
        """
        num = max(1, min(num, 100))  # Limit dice count
        sides = max(1, min(sides, 1000))  # Limit sides
        total = sum(random.randint(1, sides) for _ in range(num))
        return total + modifier

    @staticmethod
    def clamp(value: int | float, low: int | float, high: int | float) -> int | float:
        """Clamp value between low and high."""
        return max(low, min(value, high))

    @staticmethod
    def floor(value: float) -> int:
        """Round down to integer."""
        import math
        return math.floor(value)

    @staticmethod
    def ceil(value: float) -> int:
        """Round up to integer."""
        import math
        return math.ceil(value)

    # --- List functions ---

    @staticmethod
    def first(lst: list | str, delimiter: str = ' ') -> str:
        """Get first element of list or first word of string."""
        if isinstance(lst, list):
            return str(lst[0]) if lst else ""
        parts = str(lst).split(delimiter)
        return parts[0] if parts else ""

    @staticmethod
    def rest(lst: list | str, delimiter: str = ' ') -> str | list:
        """Get all but first element."""
        if isinstance(lst, list):
            return lst[1:]
        parts = str(lst).split(delimiter)
        return delimiter.join(parts[1:])

    @staticmethod
    def last(lst: list | str, delimiter: str = ' ') -> str:
        """Get last element."""
        if isinstance(lst, list):
            return str(lst[-1]) if lst else ""
        parts = str(lst).split(delimiter)
        return parts[-1] if parts else ""

    @staticmethod
    def words(text: str, delimiter: str = ' ') -> int:
        """Count words/elements in text."""
        if not text:
            return 0
        return len(text.split(delimiter))

    @staticmethod
    def member(item: str, lst: list | str, delimiter: str = ' ') -> int:
        """
        Find position of item in list (1-indexed, 0 if not found).
        """
        if isinstance(lst, str):
            lst = lst.split(delimiter)
        try:
            return lst.index(item) + 1
        except ValueError:
            return 0

    @staticmethod
    def extract(lst: list | str, position: int, delimiter: str = ' ') -> str:
        """Get element at position (1-indexed)."""
        if isinstance(lst, str):
            lst = lst.split(delimiter)
        idx = position - 1
        if 0 <= idx < len(lst):
            return str(lst[idx])
        return ""

    @staticmethod
    def setunion(list1: str, list2: str, delimiter: str = ' ') -> str:
        """Union of two space-separated lists."""
        set1 = set(list1.split(delimiter)) if list1 else set()
        set2 = set(list2.split(delimiter)) if list2 else set()
        return delimiter.join(sorted(set1 | set2))

    @staticmethod
    def setinter(list1: str, list2: str, delimiter: str = ' ') -> str:
        """Intersection of two lists."""
        set1 = set(list1.split(delimiter)) if list1 else set()
        set2 = set(list2.split(delimiter)) if list2 else set()
        return delimiter.join(sorted(set1 & set2))

    @staticmethod
    def setdiff(list1: str, list2: str, delimiter: str = ' ') -> str:
        """Difference of two lists (in list1 but not list2)."""
        set1 = set(list1.split(delimiter)) if list1 else set()
        set2 = set(list2.split(delimiter)) if list2 else set()
        return delimiter.join(sorted(set1 - set2))

    # --- Communication functions ---

    def _resolve(self, spec: GameObject | str | None) -> GameObject | None:
        """Resolve a string spec to an object; pass objects through."""
        if isinstance(spec, str):
            return self.get(spec)
        return spec

    def pemit(self, target: GameObject | str, message: str) -> None:
        """Send a private message to a target (delivered after the script)."""
        target_obj = self._resolve(target)
        if target_obj is not None:
            self.command_queue.append(('pemit', target_obj, str(message)))

    def remit(self, room: GameObject | str, message: str) -> None:
        """Emit a message to everyone in a room (delivered after the script)."""
        room_obj = self._resolve(room)
        if room_obj is not None:
            self.command_queue.append(('remit', room_obj, str(message)))

    def oemit(self, exclude: GameObject | str, message: str) -> None:
        """Emit to the executor's room, excluding one object."""
        exclude_obj = self._resolve(exclude)
        if exclude_obj is not None:
            self.command_queue.append(('oemit', exclude_obj, str(message)))

    # --- Comparison functions ---

    @staticmethod
    def eq(a: Any, b: Any) -> bool:
        """Equality test."""
        return a == b

    @staticmethod
    def neq(a: Any, b: Any) -> bool:
        """Inequality test."""
        return a != b

    @staticmethod
    def gt(a: int | float, b: int | float) -> bool:
        """Greater than."""
        return a > b

    @staticmethod
    def gte(a: int | float, b: int | float) -> bool:
        """Greater than or equal."""
        return a >= b

    @staticmethod
    def lt(a: int | float, b: int | float) -> bool:
        """Less than."""
        return a < b

    @staticmethod
    def lte(a: int | float, b: int | float) -> bool:
        """Less than or equal."""
        return a <= b

    # --- Conditional functions ---

    @staticmethod
    def if_else(condition: bool, true_val: Any, false_val: Any) -> Any:
        """Conditional expression."""
        return true_val if condition else false_val

    @staticmethod
    def switch(value: Any, *cases: Any) -> Any:
        """
        Switch statement.

        Args: value, case1, result1, case2, result2, ..., default
        """
        i = 0
        while i < len(cases) - 1:
            if cases[i] == value:
                return cases[i + 1]
            i += 2
        # Return default if odd number of args
        if len(cases) % 2 == 1:
            return cases[-1]
        return None

    def to_dict(self) -> dict[str, Any]:
        """Export all functions as a dictionary for injection into script namespace."""
        return {
            # Object functions
            'get': self.get,
            'name': self.name,
            'loc': self.loc,
            'owner': self.owner,
            'contents': self.contents,
            # Attribute functions
            'get_attr': self.get_attr,
            'set_attr': self.set_attr,
            'has_attr': self.has_attr,
            'del_attr': self.del_attr,
            # Tag functions
            'has_tag': self.has_tag,
            'tags': self.tags,
            'add_tag': self.add_tag,
            'remove_tag': self.remove_tag,
            # String functions
            'ucfirst': self.ucfirst,
            'lcfirst': self.lcfirst,
            'capstr': self.capstr,
            'repeat': self.repeat,
            'strlen': self.strlen,
            'mid': self.mid,
            'left': self.left,
            'right': self.right,
            'trim': self.trim,
            'replace': self.replace,
            # Math functions
            'rand': self.rand,
            'dice': self.dice,
            'clamp': self.clamp,
            'floor': self.floor,
            'ceil': self.ceil,
            # List functions
            'first': self.first,
            'rest': self.rest,
            'last': self.last,
            'words': self.words,
            'member': self.member,
            'extract': self.extract,
            'setunion': self.setunion,
            'setinter': self.setinter,
            'setdiff': self.setdiff,
            # Communication
            'pemit': self.pemit,
            'remit': self.remit,
            'oemit': self.oemit,
            # Comparison
            'eq': self.eq,
            'neq': self.neq,
            'gt': self.gt,
            'gte': self.gte,
            'lt': self.lt,
            'lte': self.lte,
            # Conditional
            'if_else': self.if_else,
            'switch': self.switch,
            # Context shortcuts
            'me': self.executor,
            'here': self.location,
            'enactor': self.enactor,
        }
