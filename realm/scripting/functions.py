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
    ):
        self.enactor = enactor
        self.executor = executor
        self.location = location
        self._persistence = persistence

        # Deliveries queued by communication functions. Scripts execute in a
        # worker thread, so functions must never touch sessions directly —
        # the engine drains this queue on the event loop after execution.
        # Entries: (kind, obj, payload). Message kinds (pemit/remit/oemit)
        # carry a string; world-op kinds (save/destroy/death_check/combat/
        # wait) carry op-specific payloads. Drained by ScriptEngine.
        self.command_queue: list[tuple[str, GameObject, Any]] = []

    # --- Object lookup ---

    def get(self, spec: str) -> GameObject | None:
        """
        Get an object by ID or name.

        Args:
            spec: Object ID (starting with #) or name

        Returns:
            The GameObject or None if not found
        """
        spec = str(spec).strip()

        # ID lookup
        if spec.startswith('#'):
            if not self._persistence:
                return None
            return self._persistence.get_cached(spec[1:])

        # Name lookup — local first (executor's room + inventory), like
        # player commands; then the whole world. Same tiered matcher as
        # commands; scripts take the first match rather than raising on
        # ambiguity.
        from realm.core.search import match_objects

        local: list[GameObject] = []
        if self.executor is not None:
            room = self.executor.location
            if room is not None:
                local.extend(room.contents)
                local.append(room)
            local.extend(self.executor.contents)
            local.append(self.executor)
        matches = match_objects(spec, local).matches
        if matches:
            return matches[0]

        if not self._persistence:
            return None
        matches = match_objects(spec, self._persistence.all_cached()).matches
        return matches[0] if matches else None

    def name(self, obj: GameObject | str | None) -> str:
        """Get an object's name."""
        target = self._resolve(obj)
        return target.name if target else ""

    def loc(self, obj: GameObject | str | None) -> GameObject | None:
        """Get an object's location."""
        target = self._resolve(obj)
        return target.location if target else None

    def owner(self, obj: GameObject | str | None) -> GameObject | None:
        """Get an object's owner."""
        target = self._resolve(obj)
        return target.owner if target else None

    def contents(self, obj: GameObject | str | None) -> list[GameObject]:
        """Get an object's contents."""
        target = self._resolve(obj)
        return target.contents if target else []

    # --- Attribute access ---

    def get_attr(
        self,
        obj: GameObject | str | None,
        attr_name: str,
        default: Any = None,
    ) -> Any:
        """Get an attribute from an object."""
        target = self._resolve(obj)
        return target.db.get(attr_name, default) if target else default

    # --- Authority ---

    def controls(self, obj: GameObject | str | None) -> bool:
        """Does the executor control this object? (The mutation gate.)"""
        from realm.permissions.locks import controls as _controls
        target = self._resolve(obj)
        return _controls(self.executor, target)

    def _may_mutate(self, obj: GameObject | None) -> bool:
        """Scripts run AS the executor; mutations require its authority."""
        from realm.permissions.locks import controls as _controls
        return _controls(self.executor, obj)

    def _controlled(self, obj: GameObject | str | None) -> GameObject | None:
        """Resolve + authority in one step: None means no or not allowed."""
        target = self._resolve(obj)
        if target is None or not self._may_mutate(target):
            return None
        return target

    def _touch(self, obj: GameObject) -> None:
        """Queue a persistence save for a mutated object."""
        self.command_queue.append(('save', obj, ''))

    def set_attr(
        self,
        obj: GameObject | str | None,
        attr_name: str,
        value: Any,
    ) -> bool:
        """
        Set an attribute on an object the executor controls.

        Returns True on success, False on failure (including no
        authority — see docs/design/engine_vision.md).
        """
        target = self._controlled(obj)
        if target is None:
            return False
        target.db.set(attr_name, value)
        self._touch(target)
        return True

    def has_attr(self, obj: GameObject | str | None, attr_name: str) -> bool:
        """Check if an object has an attribute."""
        target = self._resolve(obj)
        return attr_name in target.db if target else False

    def del_attr(self, obj: GameObject | str | None, attr_name: str) -> bool:
        """Delete an attribute from an object the executor controls."""
        target = self._controlled(obj)
        if target is None:
            return False
        if attr_name in target.db:
            target.db.delete(attr_name)
            self._touch(target)
            return True
        return False

    # --- Tag operations ---

    def has_tag(self, obj: GameObject | str | None, tag: str) -> bool:
        """Check if an object has a tag."""
        target = self._resolve(obj)
        return target.has_tag(tag) if target else False

    def tags(self, obj: GameObject | str | None) -> list[str]:
        """Get all tags on an object."""
        target = self._resolve(obj)
        return target.tags.to_list() if target else []

    def add_tag(self, obj: GameObject | str | None, tag: str) -> bool:
        """Add a tag to an object the executor controls."""
        target = self._controlled(obj)
        if target is None:
            return False
        target.add_tag(tag)
        self._touch(target)
        return True

    def remove_tag(self, obj: GameObject | str | None, tag: str) -> bool:
        """Remove a tag from an object the executor controls."""
        target = self._controlled(obj)
        if target is None:
            return False
        target.remove_tag(tag)
        self._touch(target)
        return True

    # --- World manipulation (the engine API; all authority-gated) ---

    def exits(self, room: GameObject | str | None = None) -> list[GameObject]:
        """Open exits of a room (default: the executor's location)."""
        room_obj = self._resolve(room) if room is not None else self.location
        if room_obj is None:
            return []
        return [o for o in room_obj.contents if o.has_tag('exit')]

    def create_obj(
        self,
        name: str,
        tags: list[str] | None = None,
        location: GameObject | str | None = None,
    ) -> GameObject | None:
        """
        Create a new thing, owned by the executor's owner (or the
        executor itself), at the executor's location by default.
        """
        from realm.core.objects import GameObject as GameObjectCls

        where = self._resolve(location) if location is not None else (
            self.executor.location if self.executor else None)
        # Creation lands in the executor's own room, or one it controls —
        # no seeding objects into strangers' rooms.
        if (location is not None and where is not None
                and self.executor is not None
                and where is not self.executor.location
                and not self._may_mutate(where)):
            return None
        owner = None
        if self.executor is not None:
            owner = self.executor.owner or self.executor
        obj = GameObjectCls(
            name=str(name),
            tags=[str(t) for t in (tags or ['thing'])],
            owner=owner,
        )
        obj.location = where
        self.command_queue.append(('save', obj, ''))
        return obj

    def destroy_obj(self, obj: GameObject | str | None) -> bool:
        """Destroy an object the executor controls (players never)."""
        target = self._resolve(obj)
        if target is None or target.has_tag('player'):
            return False
        if not self._may_mutate(target):
            return False
        self.command_queue.append(('destroy', target, ''))
        return True

    def teleport_obj(
        self,
        obj: GameObject | str | None,
        destination: GameObject | str | None,
    ) -> bool:
        """
        Move an object the executor controls straight to a destination.
        The destination's teleport lock is checked against the executor.
        """
        from realm.permissions.locks import LockType, check_lock

        target = self._resolve(obj)
        dest = self._resolve(destination)
        if target is None or dest is None or target is dest:
            return False
        if not self._may_mutate(target):
            return False
        if self.executor is not None and not check_lock(
            dest, LockType.TELEPORT, self.executor
        ):
            return False
        target.location = dest
        self.command_queue.append(('save', target, ''))
        return True

    def behaviors(self, obj: GameObject | str | None) -> list[str]:
        """Behavior ids attached to an object."""
        target = self._resolve(obj)
        if target is None:
            return []
        return [b.behavior_id for b in target.get_behaviors()]

    def attach_behavior(
        self,
        obj: GameObject | str | None,
        behavior_id: str,
        **params: Any,
    ) -> bool:
        """Attach a registered behavior to an object the executor controls."""
        from realm.core.behaviors import BehaviorRegistry

        target = self._resolve(obj)
        if target is None or not self._may_mutate(target):
            return False
        behavior = BehaviorRegistry.create(str(behavior_id), **params)
        if behavior is None:
            return False
        target.add_behavior(behavior)
        self.command_queue.append(('save', target, ''))
        return True

    def detach_behavior(self, obj: GameObject | str | None, behavior_id: str) -> bool:
        """Detach a behavior (by id) from an object the executor controls."""
        target = self._resolve(obj)
        if target is None or not self._may_mutate(target):
            return False
        for behavior in target.get_behaviors():
            if behavior.behavior_id == str(behavior_id):
                target.remove_behavior(behavior)
                self.command_queue.append(('save', target, ''))
                return True
        return False

    # --- Combat channels (proximity authority: same room as the executor) ---

    def _in_reach(self, target: GameObject | None) -> bool:
        """
        Proximity authority for combat channels: a trap can hurt whoever
        is standing on it, not someone across the map.
        """
        if target is None or self.executor is None:
            return False
        if target is self.executor:
            return True
        if target.location is self.executor:
            return True  # standing inside the executor (room traps, containers)
        return (target.location is not None
                and target.location is self.executor.location)

    def damage(self, obj: GameObject | str | None, amount: int) -> bool:
        """
        Deal damage to something in the executor's room. Lethal damage
        routes through the combat manager's death path (corpses, CP
        awards, unconsciousness) after the script finishes.
        """
        target = self._resolve(obj)
        if not self._in_reach(target) or int(amount) <= 0:
            return False
        hp = target.db.get('hp')
        if hp is None:
            return False
        target.db.hp = int(hp) - int(amount)
        self.command_queue.append(('death_check', target, self.executor))
        self.command_queue.append(('save', target, ''))
        return True

    def heal(self, obj: GameObject | str | None, amount: int) -> bool:
        """Restore HP (capped at max_hp) to something in the executor's room."""
        target = self._resolve(obj)
        if not self._in_reach(target) or int(amount) <= 0:
            return False
        hp = target.db.get('hp')
        max_hp = target.db.get('max_hp')
        if hp is None or max_hp is None:
            return False
        target.db.hp = min(int(max_hp), int(hp) + int(amount))
        self.command_queue.append(('save', target, ''))
        return True

    def start_combat(
        self,
        attacker: GameObject | str | None,
        target: GameObject | str | None,
    ) -> bool:
        """
        Throw an attacker the executor controls into combat with a
        target in the same room (queued; the encounter starts after the
        script finishes).
        """
        atk = self._resolve(attacker)
        tgt = self._resolve(target)
        if atk is None or tgt is None or atk is tgt:
            return False
        if not self._may_mutate(atk):
            return False
        if atk.location is None or atk.location is not tgt.location:
            return False
        self.command_queue.append(('combat', atk, tgt))
        return True

    # Effect behaviors softcode may apply with proximity (not control)
    # authority — a banshee can frighten whoever hears the wail.
    EFFECT_BEHAVIOR_IDS = ('modifier_effect', 'damage_over_time', 'regeneration')

    def apply_effect(
        self,
        obj: GameObject | str | None,
        effect_id: str,
        **params: Any,
    ) -> bool:
        """
        Attach an effect (modifier_effect / damage_over_time /
        regeneration) to something in the executor's room.

            apply_effect(enactor, 'modifier_effect', kind='fear',
                         duration=8, check_mods={'all': -2},
                         apply_msg='Terror grips you!')
        """
        from realm.core.behaviors import BehaviorRegistry

        if str(effect_id) not in self.EFFECT_BEHAVIOR_IDS:
            return False
        target = self._resolve(obj)
        if not self._in_reach(target):
            return False
        behavior = BehaviorRegistry.create(str(effect_id), **params)
        if behavior is None:
            return False
        target.add_behavior(behavior)
        self.command_queue.append(('save', target, ''))
        return True

    def remove_effect(self, obj: GameObject | str | None, kind: str) -> bool:
        """Strip an active effect by kind (cure poison, calm fear)."""
        target = self._resolve(obj)
        if not self._in_reach(target):
            return False
        from realm.behaviors.effects import TimedEffectBehavior
        for behavior in target.get_behaviors():
            if isinstance(behavior, TimedEffectBehavior) and behavior.kind == str(kind):
                target.remove_behavior(behavior)
                self.command_queue.append(('save', target, ''))
                return True
        return False

    # --- Locks ---

    def set_lock(
        self,
        obj: GameObject | str | None,
        lock_type: str,
        expression: str,
    ) -> bool:
        """Set a lock on an object the executor controls (validated)."""
        from realm.permissions.locks import set_lock as _set_lock

        target = self._resolve(obj)
        if target is None or not self._may_mutate(target):
            return False
        try:
            if not _set_lock(target, str(lock_type), str(expression)):
                return False
        except ValueError:
            return False
        self.command_queue.append(('save', target, ''))
        return True

    def clear_lock(self, obj: GameObject | str | None, lock_type: str) -> bool:
        """Clear a lock from an object the executor controls."""
        from realm.permissions.locks import clear_lock as _clear_lock

        target = self._resolve(obj)
        if target is None or not self._may_mutate(target):
            return False
        if _clear_lock(target, str(lock_type)):
            self.command_queue.append(('save', target, ''))
            return True
        return False

    def test_lock(
        self,
        obj: GameObject | str | None,
        lock_type: str,
        caller: GameObject | str | None = None,
    ) -> bool:
        """Would ``caller`` (default: the executor) pass this lock?"""
        from realm.permissions.locks import check_lock as _check_lock

        target = self._resolve(obj)
        who = self._resolve(caller) if caller is not None else self.executor
        if target is None or who is None:
            return False
        try:
            return _check_lock(target, str(lock_type), who)
        except ValueError:
            return False

    # --- Money ---

    def credits(self, obj: GameObject | str | None) -> int:
        """An object's balance."""
        from realm.core.economy import get_credits
        target = self._resolve(obj)
        return get_credits(target) if target is not None else 0

    def adjust_credits(self, obj: GameObject | str | None, delta: int) -> bool:
        """Mint or burn money on an object the executor controls."""
        from realm.core.economy import adjust_credits as _adjust
        target = self._resolve(obj)
        if target is None or not self._may_mutate(target):
            return False
        if _adjust(target, int(delta)):
            self.command_queue.append(('save', target, ''))
            return True
        return False

    def transfer_credits(
        self,
        source: GameObject | str | None,
        dest: GameObject | str | None,
        amount: int,
    ) -> bool:
        """Move money FROM something the executor controls."""
        from realm.core.economy import transfer_credits as _transfer
        src = self._resolve(source)
        dst = self._resolve(dest)
        if src is None or dst is None or not self._may_mutate(src):
            return False
        if _transfer(src, dst, int(amount)):
            self.command_queue.append(('save', src, ''))
            self.command_queue.append(('save', dst, ''))
            return True
        return False

    # --- Dispositions (NPC attitude memory) ---

    def disposition(self, npc, other=None) -> int:
        """How npc feels about other (default: the enactor)."""
        from realm.core.disposition import get_disposition
        npc_obj = self._resolve(npc)
        other_obj = self._resolve(other) if other is not None else self.enactor
        if npc_obj is None or other_obj is None:
            return 0
        return get_disposition(npc_obj, other_obj)

    def adjust_disposition(self, npc, other, delta: int) -> bool:
        """
        Shift an NPC's attitude. Authority: the executor must control
        the NPC (its own opinions) — you can't script others' minds
        about yourself.
        """
        from realm.core.disposition import adjust_disposition as _adjust
        npc_obj = self._resolve(npc)
        other_obj = self._resolve(other)
        if npc_obj is None or other_obj is None:
            return False
        if not self._may_mutate(npc_obj):
            return False
        _adjust(npc_obj, other_obj, int(delta))
        self.command_queue.append(('save', npc_obj, ''))
        return True

    def reaction_roll(self, npc, other=None, modifier: int = 0) -> int:
        """Memoized first-impression roll (npc must be in executor's reach)."""
        from realm.core.disposition import reaction_roll as _roll
        npc_obj = self._resolve(npc)
        other_obj = self._resolve(other) if other is not None else self.enactor
        if npc_obj is None or other_obj is None or not self._in_reach(npc_obj):
            return 0
        value = _roll(npc_obj, other_obj, int(modifier))
        self.command_queue.append(('save', npc_obj, ''))
        return value

    def force(self, obj: GameObject | str | None, command: str) -> bool:
        """
        Make something the executor controls run a command (queued;
        executes through the real dispatcher after the script). The
        possession primitive — see @force.
        """
        target = self._controlled(obj)
        if target is None:
            return False
        self.command_queue.append(('force', target, str(command)))
        return True

    # --- Scheduling ---

    def wait(self, seconds: float, command: str) -> None:
        """
        Run a script command as the executor ~seconds from now (one-shot,
        fired from the server heartbeat; pending waits don't survive a
        reboot).
        """
        if self.executor is not None:
            self.command_queue.append(
                ('wait', self.executor, (float(seconds), str(command))))

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
    def now() -> int:
        """Current time as epoch seconds — cache expiry, cooldowns."""
        import time
        return int(time.time())

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

    # --- Skill checks (contests power scripted social/skill outcomes) ---

    def skill_check(self, obj, skill: str, modifier: int = 0) -> bool:
        """Roll a skill check for an object (name/#id or object)."""
        from realm.core.checks import check as _check
        target = self._resolve(obj)
        if target is None:
            return False
        return bool(_check(target, str(skill), int(modifier)))

    def contest(self, actor, actor_skill: str, opponent, opponent_skill: str) -> bool:
        """Opposed quick contest; True if the actor wins."""
        from realm.core.checks import contest as _contest
        a = self._resolve(actor)
        b = self._resolve(opponent)
        if a is None or b is None:
            return False
        return _contest(a, str(actor_skill), b, str(opponent_skill))


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
            # World manipulation (authority-gated)
            'controls': self.controls,
            'exits': self.exits,
            'create_obj': self.create_obj,
            'destroy_obj': self.destroy_obj,
            'teleport_obj': self.teleport_obj,
            'behaviors': self.behaviors,
            'attach_behavior': self.attach_behavior,
            'detach_behavior': self.detach_behavior,
            # Combat channels + locks + scheduling
            'damage': self.damage,
            'heal': self.heal,
            'start_combat': self.start_combat,
            'apply_effect': self.apply_effect,
            'credits': self.credits,
            'adjust_credits': self.adjust_credits,
            'transfer_credits': self.transfer_credits,
            'disposition': self.disposition,
            'adjust_disposition': self.adjust_disposition,
            'reaction_roll': self.reaction_roll,
            'remove_effect': self.remove_effect,
            'set_lock': self.set_lock,
            'clear_lock': self.clear_lock,
            'test_lock': self.test_lock,
            'wait': self.wait,
            'force': self.force,
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
            'now': self.now,
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
            # Skill checks
            'skill_check': self.skill_check,
            'contest': self.contest,
            # Communication
            'pemit': self.pemit,
            'remit': self.remit,
            'oemit': self.oemit,
            # Comparison
            # Conditional
            'if_else': self.if_else,
            'switch': self.switch,
            # Context shortcuts
            'me': self.executor,
            'here': self.location,
            'enactor': self.enactor,
        }
