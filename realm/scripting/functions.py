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


# Attributes softcode may never read (secrets live in ordinary attrs).
PROTECTED_ATTRS = {'password'}


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
        enactor_consent: bool = False,
    ):
        self.enactor = enactor
        self.executor = executor
        self.location = location
        self._persistence = persistence
        # True ONLY when the enactor deliberately invoked this object —
        # typed its $-command, or traversed the exit whose ON_FAIL is
        # running. Grants move_to/enter_instance the right to relocate the
        # ENACTOR (a portal moving its walker). Merely being overheard
        # (^listen) or witnessed (ON_ENTER) is NOT consent — those paths
        # leave this False, so scripts there need real control() authority.
        self.enactor_consent = enactor_consent

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

        Example: get('rusty key')  or  get('#3fa9...')
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
        """Get an object's name.

        Example: name(enactor)
        """
        target = self._resolve(obj)
        return target.name if target else ""

    def loc(self, obj: GameObject | str | None) -> GameObject | None:
        """Get an object's location.

        Example: loc(enactor)
        """
        target = self._resolve(obj)
        return target.location if target else None

    def owner(self, obj: GameObject | str | None) -> GameObject | None:
        """Get an object's owner.

        Example: owner(me) == enactor
        """
        target = self._resolve(obj)
        return target.owner if target else None

    def contents(self, obj: GameObject | str | None) -> list[GameObject]:
        """Get an object's contents.

        Example: [o for o in contents(here) if has_tag(o, 'npc')]
        """
        target = self._resolve(obj)
        return target.contents if target else []

    # --- Attribute access ---

    def get_attr(
        self,
        obj: GameObject | str | None,
        attr_name: str,
        default: Any = None,
    ) -> Any:
        """Get an attribute from an object.

        Example: get_attr(enactor, 'hp', 0)
        """
        if str(attr_name) in PROTECTED_ATTRS:
            return default
        target = self._resolve(obj)
        if target is None:
            return default
        from realm.core.attrflags import readable_attr
        if not readable_attr(target, str(attr_name), self.executor):
            return default
        return target.db.get(attr_name, default)

    # --- Authority ---

    def controls(self, obj: GameObject | str | None) -> bool:
        """Does the executor control this object? (The mutation gate.)

        Example: controls('lever')
        """
        from realm.permissions.locks import controls as _controls
        target = self._resolve(obj)
        return _controls(self.executor, target)

    def _may_mutate(self, obj: GameObject | None) -> bool:
        """Scripts run AS the executor; mutations require its authority."""
        from realm.permissions.locks import controls as _controls
        return _controls(self.executor, obj)

    def _may_relocate(self, obj: GameObject | None) -> bool:
        """Relocation authority — broader than mutation: the executor may
        also move what stands in a room the executor owns (Penn's
        room-owner teleport). Used only by movement functions."""
        from realm.permissions.locks import may_relocate as _may_relocate
        return _may_relocate(self.executor, obj)

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

        Example: set_attr(me, 'visits', get_attr(me, 'visits', 0) + 1)
        """
        target = self._controlled(obj)
        if target is None:
            return False
        from realm.core.attrflags import writable_attr
        ok, _reason = writable_attr(target, str(attr_name))
        if not ok:
            return False
        target.db.set(attr_name, value)
        self._touch(target)
        return True

    def has_attr(self, obj: GameObject | str | None, attr_name: str) -> bool:
        """Check if an object has an attribute.

        Example: has_attr(me, 'charged')
        """
        if str(attr_name) in PROTECTED_ATTRS:
            return False
        target = self._resolve(obj)
        if target is None:
            return False
        from realm.core.attrflags import readable_attr
        if not readable_attr(target, str(attr_name), self.executor):
            return False
        return attr_name in target.db

    def del_attr(self, obj: GameObject | str | None, attr_name: str) -> bool:
        """Delete an attribute from an object the executor controls.

        Example: del_attr(me, 'charged')
        """
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
        """Check if an object has a tag.

        Example: has_tag(enactor, 'player')
        """
        target = self._resolve(obj)
        return target.has_tag(tag) if target else False

    def tags(self, obj: GameObject | str | None) -> list[str]:
        """Get all tags on an object.

        Example: 'npc' in tags(enactor)
        """
        target = self._resolve(obj)
        return target.tags.to_list() if target else []

    def add_tag(self, obj: GameObject | str | None, tag: str) -> bool:
        """Add a tag to an object the executor controls.

        Example: add_tag(me, 'glowing')
        """
        target = self._controlled(obj)
        if target is None:
            return False
        target.add_tag(tag)
        self._touch(target)
        return True

    def remove_tag(self, obj: GameObject | str | None, tag: str) -> bool:
        """Remove a tag from an object the executor controls.

        Example: remove_tag(me, 'hostile')
        """
        target = self._controlled(obj)
        if target is None:
            return False
        target.remove_tag(tag)
        self._touch(target)
        return True

    # --- World manipulation (the engine API; all authority-gated) ---

    def exits(self, room: GameObject | str | None = None) -> list[GameObject]:
        """Open exits of a room (default: the executor's location).

        Example: move(name(exits(here)[0]))
        """
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

        Example: sword = create_obj('iron sword')
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
        """Destroy an object the executor controls (players never).

        Example: destroy_obj('slag')
        """
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
        Move an object the executor controls straight to a destination — the
        wizard/admin relocation. Now a thin alias for ``move_to(force=True)``:
        it tunnels past on_check **wards** (a Bound field), but still honors
        the destination's **locks** (its teleport lock included) and requires
        control of the object. A forced arrival still fires ``on_enter``.

        Example: teleport_obj(enactor, 'The Oubliette')
        """
        return self.move_to(obj, destination, force=True)

    def move_to(
        self,
        target: GameObject | str | None,
        destination: GameObject | str | None,
        *,
        tags: list[str] | None = None,
        force: bool = False,
    ) -> bool:
        """
        Relocate a player/object to a destination with the movement checks
        baked in — the one relocation verb. The move is always tagged
        ``movement``, so a Bound ward (``block() if has_atag('movement')``)
        stops it; pass extra ``tags`` (e.g. ``['magic']``) so anti-magic wards
        catch it too. Both the origin and the destination get an event-veto,
        plus the destination's ENTER/TELEPORT locks. Returns whether the move
        was *authorized and queued* — wards/locks run after the script ends,
        and a veto fizzles the move then, delivering the reason to the mover.
        (``tags`` here = ``extra_tags`` on the core ``movement.move_to``.)

        ``force=True`` (== ``teleport_obj``) skips the on_check **wards** but
        NOT the **locks** — the wizard bypass. It requires full control of the
        target; without force, the enactor may also move *themselves* (a
        ``cast teleport`` moves the caster).

        Example — a teleport spell:
        ``&spell.teleport = move_to(enactor, 'The Sanctum', tags=['magic'])``
        """
        tgt = self._resolve(target)
        dest = self._resolve(destination)
        if tgt is None or dest is None or tgt is dest:
            return False
        # Relocation authority (own the target, or own the room it's in) —
        # broader than mutation, per Penn's tport_control_ok. The checked
        # path also lets a CONSENTING enactor be moved (they typed this
        # object's $-command or walked its exit — not merely spoke near it).
        if force:
            if not self._may_relocate(tgt):
                return False
        elif not (self._may_relocate(tgt)
                  or (tgt is self.enactor and self.enactor_consent)):
            return False
        extra = [str(t) for t in (tags or [])]
        self.command_queue.append(('move_to', tgt, (dest.id, extra, bool(force))))
        return True

    def enter_instance(
        self,
        player: GameObject | str | None,
        template: str,
        *,
        mode: str = "solo",
        return_room: GameObject | str | None = None,
        idle_ttl: float | None = None,
    ) -> bool:
        """
        Send a player into a private, transient copy of a template area,
        materializing one on demand — and reusing their own copy (or their
        leader's, if it's ``shared``) if one already exists. The area opts in
        by tagging a room ``instance_template``; the copy is reaped when it's
        sat empty past ``idle_ttl``. The executor must control the player.

        ``mode`` — ``'solo'`` (private) or ``'shared'`` (the owner's
        followers route into the owner's copy). ``return_room`` — where a
        straggler is evacuated when the copy is reaped (else their home).
        Returns whether the entry was *authorized and queued*; the
        materialize-and-move happens after the script ends.

        Callable when the executor controls the player, or the player is the
        enactor (they walked into the portal). Example — an exit's ON_FAIL:
        ``&exit ON_FAIL = enter_instance(enactor, 'crypt')``
        """
        from realm.core.instances import ENTRY_TAG, TEMPLATE_TAG
        from realm.permissions.locks import LockType, check_lock

        target = self._resolve(player)
        if target is None:
            return False
        # The executor must have relocation authority over the player (own
        # them, or own the room they're in) — OR the player is a CONSENTING
        # enactor: they typed this object's $-command or walked the exit
        # whose ON_FAIL is running. Being overheard or witnessed is not
        # consent. Entry is still gated by the template's ENTER lock below.
        if not (self._may_relocate(target)
                or (target is self.enactor and self.enactor_consent)):
            return False
        template = str(template)
        # Opt-in gate: only a zone with an instance_template-tagged room can
        # be instanced.
        rooms = self.zone_rooms(template)
        if not any(r.has_tag(TEMPLATE_TAG) for r in rooms):
            return False
        # Destination-side authority: the template entry room's ENTER lock
        # (default-open) decides who may be sent in — checked against the
        # PLAYER being sent (the walker), matching move_to's convention, so
        # an author can gate a dungeon behind a key/role the entrant holds.
        entry = (next((r for r in rooms if r.has_tag(ENTRY_TAG)), None)
                 or next((r for r in rooms if r.has_tag(TEMPLATE_TAG)), None))
        if entry is not None and not check_lock(entry, LockType.ENTER, target):
            return False
        ret = self._resolve(return_room) if return_room is not None else None
        ttl = float(idle_ttl) if idle_ttl is not None else None
        self.command_queue.append(
            ('enter_instance', target,
             (template, str(mode), ret.id if ret else None, ttl)))
        return True

    def enter_wilderness(self, player: GameObject | str | None,
                         region: str, x, y) -> bool:
        """
        Send a player to the wilderness cell at ``(region, x, y)``,
        materializing it on demand — the scripted seam into a
        coordinate-keyed region. (Walking between cells needs no softcode:
        the cells' exits are real exits with deferred destinations.)

        Callable when the executor controls the player, or the player is
        the consenting enactor. Entry is gated by the region master's
        ENTER lock, checked against the player being sent. Returns whether
        the entry was *authorized and queued*; the materialize-and-move
        happens after the script ends.

        Example: enter_wilderness(enactor, 'wilds', 10, 10)
        """
        from realm.core.wilderness import get_region
        from realm.permissions.locks import LockType, check_lock

        target = self._resolve(player)
        if target is None:
            return False
        if not (self._may_relocate(target)
                or (target is self.enactor and self.enactor_consent)):
            return False
        try:
            x_i, y_i = int(x), int(y)
        except (TypeError, ValueError):
            return False
        region_obj = get_region(str(region))
        if region_obj is None:
            return False
        if not check_lock(region_obj, LockType.ENTER, target):
            return False
        self.command_queue.append(
            ('wilderness', target, (str(region), x_i, y_i)))
        return True

    def behaviors(self, obj: GameObject | str | None) -> list[str]:
        """Behavior ids attached to an object.

        Example: 'wandering' in behaviors('rat')
        """
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
        """Attach a registered behavior to an object the executor controls.

        Example: attach_behavior('golem', 'script_ticker', interval=5)
        """
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
        """Detach a behavior (by id) from an object the executor controls.

        Example: detach_behavior('golem', 'wandering')
        """
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

        Example: damage(enactor, 3)
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
        """Restore HP (capped at max_hp) to something in the executor's room.

        Example: heal(enactor, 5)
        """
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

        Example: start_combat('beast', enactor)
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

        Example: apply_effect(enactor, 'modifier_effect', kind='fear',
                 duration=8, check_mods={'all': -2})
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
        """Strip an active effect by kind (cure poison, calm fear).

        Example: remove_effect(enactor, 'fear')
        """
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
        """Set a lock on an object the executor controls (validated).

        Example: set_lock(me, 'basic', "caller.has_tag('keyholder')")
        """
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
        """Clear a lock from an object the executor controls.

        Example: clear_lock(me, 'basic')
        """
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
        """Would ``caller`` (default: the executor) pass this lock?

        Example: test_lock('vault door', 'enter')
        """
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
        """An object's balance.

        Example: credits(enactor) >= 10
        """
        from realm.core.economy import get_credits
        target = self._resolve(obj)
        return get_credits(target) if target is not None else 0

    def adjust_credits(self, obj: GameObject | str | None, delta: int) -> bool:
        """Mint or burn money on an object the executor controls.

        Example: adjust_credits(me, 100)
        """
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
        """Move money FROM something the executor controls.

        Example: transfer_credits(me, enactor, 25)
        """
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

    def tag_values(self, obj, prefix: str) -> list:
        """All values of a namespaced tag: tag_values(here, 'zone')
        -> ['castle', 'haunted'].

        Example: tag_values(here, 'zone')  # -> ['castle', 'haunted']
        """
        target = self._resolve(obj)
        if target is None:
            return []
        p = str(prefix).rstrip(':') + ':'
        return [t[len(p):] for t in target.tags.to_list() if t.startswith(p)]

    def tag_value(self, obj, prefix: str):
        """First value of a namespaced tag: tag_value(here, 'zone')
        -> 'castle' (None if untagged).

        Example: tag_value(here, 'zone')   # -> 'castle'
        """
        values = self.tag_values(obj, prefix)
        return values[0] if values else None

    @staticmethod
    def ansi(codes: str, text: str) -> str:
        """
        Penn-style color: ansi('rh', 'My thing') — lowercase letters =
        foreground (r g y b m c w x), 'h' brightens it, UPPERCASE =
        background, u = underline, i = inverse video. Returns
        |-markup + reset.

        Example: ansi('rh', 'DANGER')
        """
        fg = None
        bg = None
        bright = False
        flags = ''
        for ch in str(codes):
            if ch in 'rgybmcwx':
                fg = ch
            elif ch in 'RGYBMCWX':
                bg = ch.lower()
            elif ch == 'h':
                bright = True
            elif ch == 'u':
                flags += '|u'
            elif ch == 'i':
                flags += '|v'   # Penn 'i' = inverse video
        markup = ''
        if fg:
            markup += '|' + (fg.upper() if bright else fg)
        elif bright:
            markup += '|h'
        if bg:
            markup += '|[' + bg
        return f"{markup}{flags}{text}|n"

    @staticmethod
    def escape(text: str) -> str:
        """Escape color markup in player-provided text (|| literals).

        Example: say('They said: ' + escape(arg0))
        """
        from realm.core.markup import escape as _escape
        return _escape(str(text))

    # --- World queries ---

    def search_world(self, tag=None, attr=None, value=None,
                     name=None, limit: int = 100):
        """
        Query the world: search_world(tag='zone:castle'),
        search_world(attr='xp_multiplier'), combinable. Results capped
        (default 100). Protected attributes can't be queried.

        Example: search_world(tag='zone:castle')
        """
        from realm.core.query import _UNSET, find_objects
        if attr is not None and str(attr) in PROTECTED_ATTRS:
            return []
        if attr is not None:
            from realm.core.attrflags import readable_attr
            results = find_objects(
                tag=str(tag) if tag else None,
                attr=str(attr),
                value=value if value is not None else _UNSET,
                name_like=str(name) if name else None,
                limit=max(1, min(int(limit), 500)),
            )
            return [o for o in results
                    if readable_attr(o, str(attr), self.executor)]
        return find_objects(
            tag=str(tag) if tag else None,
            attr=str(attr) if attr else None,
            value=value if value is not None else _UNSET,
            name_like=str(name) if name else None,
            limit=max(1, min(int(limit), 500)),
        )

    def zone_rooms(self, zone: str):
        """Rooms tagged into a zone: zone_rooms('castle').

        Example: zone_rooms('castle')
        """
        from realm.core.zones import zone_rooms as _zone_rooms
        return _zone_rooms(str(zone))

    def zones_of(self, obj):
        """The zone names an object belongs to (no 'zone:' prefix).

        Example: zones_of(here)
        """
        from realm.core.zones import zone_tags
        target = self._resolve(obj)
        return [t.split(':', 1)[1] for t in zone_tags(target)]

    # --- Dispositions (NPC attitude memory) ---

    def disposition(self, npc, other=None) -> int:
        """How npc feels about other (default: the enactor).

        Example: disposition(me, enactor) >= 2
        """
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

        Example: adjust_disposition(me, enactor, 1)
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
        """Memoized first-impression roll (npc must be in executor's reach).

        Example: reaction_roll(me)
        """
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

        Example: force('minion', 'say Yes, master.')
        """
        target = self._controlled(obj)
        if target is None:
            return False
        self.command_queue.append(('force', target, str(command)))
        return True

    def eval_attr(self, obj, attr_name: str, *args):
        """
        Evaluate an attribute as a FUNCTION and return its ``result`` —
        Penn's u(). The code runs with the CALLER's authority (executor
        unchanged) and the args bound as arg0..argN / %0..%9. Secret
        attributes respect their read gate; errors return None.

        Example: eval_attr(me, 'render_side', n)
        """
        if getattr(self, '_eval_depth', 0) >= 8:
            return None
        target = self._resolve(obj)
        if target is None:
            return None
        from realm.core.attrflags import readable_attr
        if str(attr_name) in PROTECTED_ATTRS or not readable_attr(
                target, str(attr_name), self.executor):
            return None
        code = target.db.get(str(attr_name))
        if not isinstance(code, str) or not code.strip():
            return None

        from realm.scripting.sandbox import (
            ScriptContext,
            ScriptError,
            ScriptSandbox,
        )
        ctx = ScriptContext(
            enactor=self.enactor,
            executor=self.executor,
            location=self.location,
            captures=[str(a) for a in args],
        )
        self._eval_depth = getattr(self, '_eval_depth', 0) + 1
        try:
            result, _output = ScriptSandbox().execute(
                code, ctx, functions=self.to_dict())
        except ScriptError:
            return None
        finally:
            self._eval_depth -= 1
        return result

    # --- Scheduling ---

    def prompt(self, target, text: str, callback: str,
               persistent: bool = False) -> bool:
        """
        Ask a player a question; their next line runs the ``callback``
        attribute (on the executor) with the answer as arg0 — a softcode
        wizard. Chain by prompting again inside the callback.
        ``persistent=True`` survives a reboot. Requires the executor to
        control the target's own object (self/owned/admin).

        Example: prompt(enactor, 'What is your name?', 'on_name')
        """
        who = self._resolve(target)
        if who is None or not who.has_tag('player'):
            return False
        self.command_queue.append(
            ('prompt', who, (str(text), str(callback),
                             self.executor.id if self.executor else None,
                             bool(persistent))))
        return True

    def wait(self, seconds: float, command: str) -> None:
        """
        Run a script command as the executor ~seconds from now (one-shot,
        fired from the server heartbeat; pending waits don't survive a
        reboot).

        Example: wait(4, 'say The fuse burns down...')
        """
        if self.executor is not None:
            self.command_queue.append(
                ('wait', self.executor, (float(seconds), str(command))))

    # --- String functions ---

    @staticmethod
    def ucfirst(text: str) -> str:
        """Capitalize first character.

        Example: ucfirst('hello')          # 'Hello'
        """
        if not text:
            return ""
        return text[0].upper() + text[1:]

    @staticmethod
    def lcfirst(text: str) -> str:
        """Lowercase first character.

        Example: lcfirst('Hello')          # 'hello'
        """
        if not text:
            return ""
        return text[0].lower() + text[1:]

    @staticmethod
    def capstr(text: str) -> str:
        """Capitalize each word.

        Example: capstr('the iron king')   # 'The Iron King'
        """
        return text.title()

    @staticmethod
    def repeat(text: str, count: int) -> str:
        """Repeat text N times.

        Example: repeat('-', 40)
        """
        count = max(0, min(count, 1000))  # Limit to prevent abuse
        return text * count

    @staticmethod
    def strlen(text: str) -> int:
        """Get string length.

        Example: strlen(name(enactor))
        """
        return len(str(text))

    @staticmethod
    def mid(text: str, start: int, length: int) -> str:
        """Extract substring (1-indexed like MUSH).

        Example: mid('lighthouse', 5, 5)   # 'house'
        """
        start = max(0, start - 1)  # Convert to 0-indexed
        return text[start:start + length]

    @staticmethod
    def left(text: str, length: int) -> str:
        """Get leftmost N characters.

        Example: left('lighthouse', 5)     # 'light'
        """
        return text[:length]

    @staticmethod
    def right(text: str, length: int) -> str:
        """Get rightmost N characters.

        Example: right('lighthouse', 5)    # 'house'
        """
        return text[-length:] if length > 0 else ""

    @staticmethod
    def trim(text: str) -> str:
        """Remove leading/trailing whitespace.

        Example: trim('  hello  ')
        """
        return text.strip()

    @staticmethod
    def replace(text: str, old: str, new: str) -> str:
        """Replace all occurrences of old with new.

        Example: replace(arg0, 'gold', 'lead')
        """
        return text.replace(old, new)

    # --- Math functions ---

    @staticmethod
    def rand(low: int = 0, high: int = 100) -> int:
        """Random integer between low and high (inclusive).

        Example: rand(1, 100)
        """
        return random.randint(int(low), int(high))

    @staticmethod
    def now() -> int:
        """Current time as epoch seconds — cache expiry, cooldowns.

        Example: now() - get_attr(me, 'lit_at', 0) > 300
        """
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

        Example: dice(3, 6)   # 3d6
        """
        num = max(1, min(num, 100))  # Limit dice count
        sides = max(1, min(sides, 1000))  # Limit sides
        total = sum(random.randint(1, sides) for _ in range(num))
        return total + modifier

    @staticmethod
    def clamp(value: int | float, low: int | float, high: int | float) -> int | float:
        """Clamp value between low and high.

        Example: clamp(damage, 1, 10)
        """
        return max(low, min(value, high))

    @staticmethod
    def floor(value: float) -> int:
        """Round down to integer.

        Example: floor(7.9)                # 7
        """
        import math
        return math.floor(value)

    @staticmethod
    def ceil(value: float) -> int:
        """Round up to integer.

        Example: ceil(7.1)                 # 8
        """
        import math
        return math.ceil(value)

    # --- List functions ---

    @staticmethod
    def first(lst: list | str, delimiter: str = ' ') -> str:
        """Get first element of list or first word of string.

        Example: first('north south east') # 'north'
        """
        if isinstance(lst, list):
            return str(lst[0]) if lst else ""
        parts = str(lst).split(delimiter)
        return parts[0] if parts else ""

    @staticmethod
    def rest(lst: list | str, delimiter: str = ' ') -> str | list:
        """Get all but first element.

        Example: rest('north south east')  # 'south east'
        """
        if isinstance(lst, list):
            return lst[1:]
        parts = str(lst).split(delimiter)
        return delimiter.join(parts[1:])

    @staticmethod
    def last(lst: list | str, delimiter: str = ' ') -> str:
        """Get last element.

        Example: last('north south east')  # 'east'
        """
        if isinstance(lst, list):
            return str(lst[-1]) if lst else ""
        parts = str(lst).split(delimiter)
        return parts[-1] if parts else ""

    @staticmethod
    def words(text: str, delimiter: str = ' ') -> int:
        """Count words/elements in text.

        Example: words('a b c')            # 3
        """
        if not text:
            return 0
        return len(text.split(delimiter))

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def setunion(list1: str, list2: str, delimiter: str = ' ') -> str:
        """Union of two space-separated lists.

        Example: setunion('a b', 'b c')    # 'a b c'
        """
        set1 = set(list1.split(delimiter)) if list1 else set()
        set2 = set(list2.split(delimiter)) if list2 else set()
        return delimiter.join(sorted(set1 | set2))

    @staticmethod
    def setinter(list1: str, list2: str, delimiter: str = ' ') -> str:
        """Intersection of two lists.

        Example: setinter('a b', 'b c')    # 'b'
        """
        set1 = set(list1.split(delimiter)) if list1 else set()
        set2 = set(list2.split(delimiter)) if list2 else set()
        return delimiter.join(sorted(set1 & set2))

    @staticmethod
    def setdiff(list1: str, list2: str, delimiter: str = ' ') -> str:
        """Difference of two lists (in list1 but not list2).

        Example: setdiff('a b', 'b c')     # 'a'
        """
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
        """Send a private message to a target (delivered after the script).

        Example: pemit(enactor, 'A voice only you can hear...')
        """
        target_obj = self._resolve(target)
        if target_obj is not None:
            self.command_queue.append(('pemit', target_obj, str(message)))

    def remit(self, room: GameObject | str, message: str) -> None:
        """Emit a message to everyone in a room (delivered after the script).

        Example: remit(here, 'The ground trembles.')
        """
        room_obj = self._resolve(room)
        if room_obj is not None:
            self.command_queue.append(('remit', room_obj, str(message)))

    def oemit(self, exclude: GameObject | str, message: str) -> None:
        """Emit to the executor's room, excluding one object.

        Example: oemit(enactor, 'Bob vanishes in smoke.')
        """
        exclude_obj = self._resolve(exclude)
        if exclude_obj is not None:
            self.command_queue.append(('oemit', exclude_obj, str(message)))

    def act(self, target: GameObject | str, message: str = "",
            targeting: str = "remote", action_type: str = "event:act") -> bool:
        """
        Fire a PROPAGATED action that can reach BEYOND your own room —
        unlike pemit/remit (which just deliver text), this runs the
        two-pass engine, so behaviors can veto or react at both ends.

        ``targeting`` chooses the audience:
          - ``'remote'`` — the TARGET's room (a different room from yours):
            scry, remote cast. A ward in *your* room or the destination can
            block it, and occupants there witness/react.
          - ``'zone'`` — every room in the target's zone (an alarm).
          - ``'room'`` — the target's room, local but propagated.

        The message reaches the far room's occupants (the ``'remote'``
        audience). Reaching a destination is authority-gated by its
        ``reach`` lock (open by default, like teleport) — a room or zone can
        set ``lock_reach`` to lock out remote actions. Example — a scry:
        ``act(thing, 'A scrying eye blinks open.', targeting='remote')``.
        """
        obj = self._resolve(target)
        if obj is None:
            return False
        self.command_queue.append(
            ('act', obj, (str(message), str(targeting), str(action_type))))
        return True

    def oob(self, target: GameObject | str, package: str, data: dict) -> None:
        """
        Send structured out-of-band data (GMCP) to a player's client —
        custom UI panels from softcode. Delivered after the script,
        like pemit. No-op for clients without an OOB channel.

        Example: oob(enactor, 'Ship.Status', {'hull': 87})
        """
        target_obj = self._resolve(target)
        if target_obj is not None and isinstance(data, dict):
            self.command_queue.append(('oob', target_obj, (str(package), data)))

    # --- Skill checks (contests power scripted social/skill outcomes) ---

    def skill_check(self, obj, skill: str, modifier: int = 0) -> bool:
        """Roll a skill check for an object (name/#id or object).

        Example: skill_check(enactor, 'stealth', -2)
        """
        from realm.core.checks import check as _check
        target = self._resolve(obj)
        if target is None:
            return False
        return bool(_check(target, str(skill), int(modifier)))

    def contest(self, actor, actor_skill: str, opponent, opponent_skill: str) -> bool:
        """Opposed quick contest; True if the actor wins.

        Example: contest(enactor, 'fast_talk', me, 'detect_lies')
        """
        from realm.core.checks import contest as _contest
        a = self._resolve(actor)
        b = self._resolve(opponent)
        if a is None or b is None:
            return False
        return _contest(a, str(actor_skill), b, str(opponent_skill))


    # --- Conditional functions ---

    @staticmethod
    def if_else(condition: bool, true_val: Any, false_val: Any) -> Any:
        """Conditional expression.

        Example: if_else(credits(enactor) >= 10, 'Welcome!', 'No coin, no entry.')
        """
        return true_val if condition else false_val

    @staticmethod
    def switch(value: Any, *cases: Any) -> Any:
        """
        Switch statement.

        Args: value, case1, result1, case2, result2, ..., default

        Example: switch(tag_value(here, 'zone'), 'castle', 'Halt!',
                 'forest', 'Rustle...', 'Silence.')
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

    #: The subset of the softcode vocabulary that is SAFE on the check
    #: pass — pure reads, queries, dice, and formatting. Everything that
    #: mutates or queues world state is deliberately absent, so an
    #: ``on_check`` script (which runs on the veto path) can decide but not
    #: act. An allowlist, not a denylist: a new function is excluded from
    #: check scripts until it's proven read-only and added here.
    _READONLY = frozenset({
        # object / attribute / tag reads
        'get', 'name', 'loc', 'owner', 'contents', 'exits',
        'get_attr', 'has_attr', 'has_tag', 'tags', 'tag_value', 'tag_values',
        # world reads
        'controls', 'search_world', 'zone_rooms', 'zones_of', 'test_lock',
        'credits', 'disposition',
        # dice / checks (roll and resolve; no world mutation)
        'roll', 'margin_under', 'margin_over', 'net_successes', 'highest',
        'band', 'rand', 'now', 'dice', 'clamp', 'floor', 'ceil',
        'skill_check', 'contest',
        # strings
        'ucfirst', 'lcfirst', 'capstr', 'repeat', 'strlen', 'mid', 'left',
        'right', 'trim', 'replace', 'ansi', 'escape',
        # lists
        'first', 'rest', 'last', 'words', 'member', 'extract',
        'setunion', 'setinter', 'setdiff',
        # conditional + context values
        'if_else', 'switch', 'me', 'here', 'enactor',
    })

    def readonly_dict(self) -> dict[str, Any]:
        """The check-pass namespace: only the read/query/dice/format subset
        of to_dict() (see ``_READONLY``). No mutators, so decision-pass
        softcode is structurally unable to change the world."""
        return {k: v for k, v in self.to_dict().items() if k in self._READONLY}

    def to_dict(self) -> dict[str, Any]:
        """Export all functions as a dictionary for injection into script namespace."""
        from realm.core import dice
        from realm.scripting.bindings import registered_bindings

        namespace = {
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
            'move_to': self.move_to,
            'enter_instance': self.enter_instance,
            'enter_wilderness': self.enter_wilderness,
            'behaviors': self.behaviors,
            'attach_behavior': self.attach_behavior,
            'detach_behavior': self.detach_behavior,
            # Combat channels + locks + scheduling
            'damage': self.damage,
            'heal': self.heal,
            'start_combat': self.start_combat,
            'apply_effect': self.apply_effect,
            'tag_value': self.tag_value,
            'tag_values': self.tag_values,
            'ansi': self.ansi,
            'escape': self.escape,
            'search_world': self.search_world,
            'zone_rooms': self.zone_rooms,
            'zones_of': self.zones_of,
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
            'prompt': self.prompt,
            'eval_attr': self.eval_attr,
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
            # Dice & resolution primitives (realm.core.dice) — the pieces a
            # game system's resolution rule composes from.
            'roll': dice.roll,
            'margin_under': dice.margin_under,
            'margin_over': dice.margin_over,
            'net_successes': dice.net_successes,
            'highest': dice.highest,
            'band': dice.band,
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
            'act': self.act,
            'oob': self.oob,
            # Comparison
            # Conditional
            'if_else': self.if_else,
            'switch': self.switch,
            # Context shortcuts
            'me': self.executor,
            'here': self.location,
            'enactor': self.enactor,
        }
        # Native bindings registered by the operator/pack author extend
        # (and may override) the vocabulary — the trusted escape hatch.
        namespace.update(registered_bindings())
        return namespace
