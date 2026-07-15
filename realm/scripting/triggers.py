"""
Trigger system for REALM scripting.

Triggers define when scripts execute:
- $pattern - Command triggers: match player input
- ^pattern - Listen triggers: match overheard speech
- ON_EVENT - Event triggers: match game events

Pattern syntax:
- * matches any sequence of characters (greedy)
- ? matches a single character
- Literal text must match exactly (case-insensitive)

Examples:
    $greet * -> matches "greet bob", "greet everyone"
    ^*treasure* -> matches speech containing "treasure"
    ON_ENTER -> fires when something enters
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.core.propagation import Action


@dataclass
class TriggerMatch:
    """Result of a successful trigger match."""

    trigger: Trigger
    captures: list[str]  # Captured wildcard groups
    full_match: str  # The complete matched string
    obj: GameObject  # Object that owns the trigger
    action: str  # Action to execute


class Trigger(ABC):
    """Base class for all trigger types."""

    @abstractmethod
    def matches(self, text: str) -> list[str] | None:
        """
        Check if text matches this trigger's pattern.

        Returns:
            List of captured groups if matches, None otherwise
        """
        pass

    @property
    @abstractmethod
    def pattern(self) -> str:
        """The original pattern string."""
        pass


@dataclass
class CommandTrigger(Trigger):
    """
    Trigger that matches player commands.

    Set on objects via: &CMD_name obj = $pattern: action

    Examples:
        $greet * -> say Hello, %0!
        $push button -> @trigger me/ON_PUSH
        $buy * from * -> @force %1=sell %0 to %#
    """

    _pattern: str
    action: str
    _regex: re.Pattern = field(init=False, repr=False)

    def __post_init__(self):
        self._regex = self._compile_pattern(self._pattern)

    @staticmethod
    def _compile_pattern(pattern: str) -> re.Pattern:
        """Convert a MUSH-style pattern to regex."""
        # Escape regex special chars except * and ?
        escaped = re.escape(pattern)
        # Convert * to capture group
        escaped = escaped.replace(r'\*', '(.*)')
        # Convert ? to single char
        escaped = escaped.replace(r'\?', '(.)')
        # Match entire string, case-insensitive
        return re.compile(f'^{escaped}$', re.IGNORECASE)

    @property
    def pattern(self) -> str:
        return self._pattern

    def matches(self, text: str) -> list[str] | None:
        """Match against player input."""
        match = self._regex.match(text.strip())
        if match:
            return list(match.groups())
        return None


@dataclass
class ListenTrigger(Trigger):
    """
    Trigger that matches overheard speech.

    Set on objects via: &LISTEN_name obj = ^pattern: action

    Examples:
        ^*treasure* -> whisper %# I hear you're looking for treasure...
        ^hello* -> say Hello to you too!
        ^*help* -> say Try asking the wizard.
    """

    _pattern: str
    action: str
    _regex: re.Pattern = field(init=False, repr=False)

    def __post_init__(self):
        self._regex = self._compile_pattern(self._pattern)

    @staticmethod
    def _compile_pattern(pattern: str) -> re.Pattern:
        """Convert a MUSH-style pattern to regex."""
        escaped = re.escape(pattern)
        escaped = escaped.replace(r'\*', '(.*)')
        escaped = escaped.replace(r'\?', '(.)')
        return re.compile(f'^{escaped}$', re.IGNORECASE | re.DOTALL)

    @property
    def pattern(self) -> str:
        return self._pattern

    def matches(self, text: str) -> list[str] | None:
        """Match against speech/emote text."""
        match = self._regex.match(text)
        if match:
            return list(match.groups())
        return None


@dataclass
class EventTrigger:
    """
    Trigger that fires on propagated actions.

    Set on objects via: &ON_EVENT obj = action

    Examples:
        &ON_ENTER obj = say Welcome!
        &ON_LOOK obj = @emit The mirror shimmers.
        &ON_GET obj = @trigger me/PICKED_UP

    The ``event_type`` matches against the suffix of an Action's
    ``action_type`` — i.e. ``"ENTER"`` matches ``Action(action_type="event:on_enter")``.
    Comparison is case-insensitive and ignores the ``on_`` prefix.
    """

    event_type: str  # ENTER, LEAVE, LOOK, GET, DROP, etc.
    action: str

    def matches_event(self, action: Action) -> bool:
        """Check if this trigger should fire for a propagated action."""
        # Take the suffix of "domain:on_event" or "domain:event" and compare.
        suffix = action.action_type.rsplit(":", 1)[-1].upper()
        if suffix.startswith("ON_"):
            suffix = suffix[3:]
        return suffix == self.event_type.upper()


# Mapping of event types to attribute prefix
EVENT_ATTR_PREFIX = 'ON_'

# The lifecycle events the engine fires, keyed by the ``ON_<name>`` a witness
# reacts with, with a one-line description. DOCUMENTARY — matching is by
# suffix, so an ``ON_<anything>`` attribute works if some code (or ``act()``)
# fires an ``…:<name>`` action. This is the single source of truth: the
# softcode reference (`scripts/gen_softcode_docs.py`) renders it, so a new
# hook self-documents. Kept grouped, in sync with the real fire sites.
STANDARD_EVENTS = {
    # Movement / location
    'ENTER':      "something enters this location",
    'LEAVE':      "something leaves this location",
    'ARRIVE':     "this object arrives somewhere new",
    'FAIL':       "a move was thwarted (dead-end/locked exit) — @afail",
    # Perception / interaction
    'LOOK':       "this object is looked at",
    'USE':        "this object is used",
    'PUSH':       "this object is pushed (button, lever)",
    # Item lifecycle
    'GET':        "this object is picked up",
    'DROP':       "this object is dropped",
    'GIVE':       "this object is given away",
    'RECEIVE':    "this object is given something (recipient side)",
    'PUT':        "this object is put in a container",
    'WEAR':       "this object is worn",
    'REMOVE':     "this object is taken off (gated: cursed gear can refuse)",
    'WIELD':      "this weapon is readied (gated)",
    'UNWIELD':    "this weapon is lowered (gated)",
    'OPEN':       "this door/container is opened",
    'CLOSE':      "this door/container is closed",
    'LOCK':       "this is locked (gated)",
    'UNLOCK':     "this is unlocked (gated: a sealed door can refuse)",
    # Combat
    'ATTACK':     "this object attacks or is attacked",
    'DAMAGE':     "this object takes damage",
    'HITPRCNT':   "HP fell through this object's db.hitprcnt threshold",
    'DEATH':      "this object dies",
    'CAST':       "an ability is directed at this object (resist via on_check)",
    # Existence
    'LOAD':       "this object was just spawned",
    'EXPIRE':     "this object's db.expires_at elapsed (then it's destroyed)",
    'TICK':       "periodic timer (on_tick behavior)",
    # Session
    'CONNECT':    "player connects",
    'DISCONNECT': "player disconnects",
    'PAYMENT':    "this object was paid",
}


class TriggerManager:
    """
    Manages triggers for the game world.

    Responsibilities:
    - Parse trigger attributes from objects
    - Match player input against command triggers
    - Match speech against listen triggers
    - Fire event triggers when events occur
    """

    # Prefixes for trigger attributes
    CMD_PREFIX = 'CMD_'  # &CMD_GREET = $greet *: action
    LISTEN_PREFIX = 'LISTEN_'  # &LISTEN_MAGIC = ^*magic*: action

    def __init__(self):
        # Cache of parsed triggers per object
        self._trigger_cache: dict[str, dict[str, list[Trigger]]] = {}

    def invalidate_cache(self, obj_id: str) -> None:
        """Clear cached triggers for an object."""
        self._trigger_cache.pop(obj_id, None)

    def get_command_triggers(self, obj: GameObject) -> list[CommandTrigger]:
        """Get all command triggers from an object."""
        triggers = []

        for key, value in obj.db.all().items():
            if key.upper().startswith(self.CMD_PREFIX):
                trigger = self._parse_command_trigger(value)
                if trigger:
                    triggers.append(trigger)

        return triggers

    def get_listen_triggers(self, obj: GameObject) -> list[ListenTrigger]:
        """Get all listen triggers from an object."""
        triggers = []

        for key, value in obj.db.all().items():
            if key.upper().startswith(self.LISTEN_PREFIX):
                trigger = self._parse_listen_trigger(value)
                if trigger:
                    triggers.append(trigger)

        return triggers

    def get_event_triggers(self, obj: GameObject, event_type: str) -> list[EventTrigger]:
        """
        Get all event triggers of a specific type from an object.

        Attribute keys match case-insensitively (``on_enter`` and
        ``ON_ENTER`` both work), consistent with CMD_/LISTEN_ parsing.
        """
        triggers = []
        attr_name = f'{EVENT_ATTR_PREFIX}{event_type.upper()}'

        for key, value in obj.db.all().items():
            if key.upper() == attr_name and isinstance(value, str) and value:
                triggers.append(EventTrigger(event_type=event_type, action=value))

        return triggers

    def _parse_command_trigger(self, value: str) -> CommandTrigger | None:
        """
        Parse a command trigger attribute value.

        Format: $pattern: action
        Example: $greet *: say Hello, %0!
        """
        if not isinstance(value, str):
            return None

        value = value.strip()
        if not value.startswith('$'):
            return None

        # Find the colon separator
        colon_pos = value.find(':')
        if colon_pos == -1:
            return None

        pattern = value[1:colon_pos].strip()  # Remove $ prefix
        action = value[colon_pos + 1:].strip()

        if not pattern or not action:
            return None

        return CommandTrigger(_pattern=pattern, action=action)

    def _parse_listen_trigger(self, value: str) -> ListenTrigger | None:
        """
        Parse a listen trigger attribute value.

        Format: ^pattern: action
        Example: ^*treasure*: whisper %# I know where treasure is...
        """
        if not isinstance(value, str):
            return None

        value = value.strip()
        if not value.startswith('^'):
            return None

        colon_pos = value.find(':')
        if colon_pos == -1:
            return None

        pattern = value[1:colon_pos].strip()  # Remove ^ prefix
        action = value[colon_pos + 1:].strip()

        if not pattern or not action:
            return None

        return ListenTrigger(_pattern=pattern, action=action)

    def find_command_match(
        self,
        command: str,
        search_objects: list[GameObject],
    ) -> TriggerMatch | None:
        """
        Search for a command trigger that matches the input.

        Searches objects in order (typically: room contents, room, inventory,
        zone objects, global command room).

        Args:
            command: The player's input command
            search_objects: Objects to search for triggers

        Returns:
            TriggerMatch if found, None otherwise
        """
        for obj in search_objects:
            # Skip objects with HALT flag
            if obj.has_tag('halt'):
                continue

            triggers = self.get_command_triggers(obj)
            for trigger in triggers:
                captures = trigger.matches(command)
                if captures is not None:
                    return TriggerMatch(
                        trigger=trigger,
                        captures=captures,
                        full_match=command,
                        obj=obj,
                        action=trigger.action,
                    )

        return None

    def find_listen_matches(
        self,
        speech: str,
        search_objects: list[GameObject],
    ) -> list[TriggerMatch]:
        """
        Find all listen triggers that match the speech.

        Unlike commands, multiple listen triggers can fire for the same speech.

        Args:
            speech: The spoken/emoted text
            search_objects: Objects to search for triggers

        Returns:
            List of TriggerMatch for all matching triggers
        """
        matches = []

        for obj in search_objects:
            # Skip objects with HALT flag
            if obj.has_tag('halt'):
                continue

            triggers = self.get_listen_triggers(obj)
            for trigger in triggers:
                captures = trigger.matches(speech)
                if captures is not None:
                    matches.append(TriggerMatch(
                        trigger=trigger,
                        captures=captures,
                        full_match=speech,
                        obj=obj,
                        action=trigger.action,
                    ))

        return matches


def get_search_objects(player: GameObject) -> list[GameObject]:
    """
    Get the standard list of objects to search for triggers.

    Search order (from plan.md):
    1. Contents of current room
    2. The room itself
    3. Player's inventory
    4. Zone objects (tagged with matching zone)
    5. Global command room (Master Room) - TODO

    Args:
        player: The player who typed the command

    Returns:
        List of objects to search, in priority order
    """
    search_list: list[GameObject] = []
    seen_ids: set[str] = set()

    def add_if_new(obj: GameObject) -> None:
        if obj.id not in seen_ids:
            seen_ids.add(obj.id)
            search_list.append(obj)

    # 1. Room contents (excluding player)
    if player.location:
        for obj in player.location.contents:
            if obj != player:
                add_if_new(obj)

        # 2. The room itself
        add_if_new(player.location)

    # 3. Player's inventory
    for obj in player.contents:
        add_if_new(obj)

    # 4. Zone masters: zone-wide $-commands/^listens (the Zone Master
    # Room pattern) — any zone_master sharing a zone: tag with the room.
    if player.location:
        from realm.core.zones import zone_masters
        for master in zone_masters(player.location):
            add_if_new(master)

    # 5. Global command room - TODO: implement Master Room

    return search_list
