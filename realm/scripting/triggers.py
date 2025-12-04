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
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.events import Event
    from realm.core.objects import GameObject


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
    Trigger that fires on game events.

    Set on objects via: &ON_EVENT obj = action

    Examples:
        &ON_ENTER obj = say Welcome!
        &ON_LOOK obj = @emit The mirror shimmers.
        &ON_GET obj = @trigger me/PICKED_UP
    """

    event_type: str  # ENTER, LEAVE, LOOK, GET, DROP, etc.
    action: str

    def matches_event(self, event: Event) -> bool:
        """Check if this trigger should fire for an event."""
        # Event type can be EventType enum value or string
        event_type_str = str(event.type).upper()
        if '.' in event_type_str:
            # Handle EventType.ENTER -> ENTER
            event_type_str = event_type_str.split('.')[-1]
        return event_type_str == self.event_type.upper()


# Mapping of event types to attribute prefix
EVENT_ATTR_PREFIX = 'ON_'

# Standard event triggers from plan.md
STANDARD_EVENTS = {
    'ENTER',      # Something enters this location
    'LEAVE',      # Something leaves this location
    'ARRIVE',     # This object arrives somewhere new
    'LOOK',       # This object is looked at
    'GET',        # This object is picked up
    'DROP',       # This object is dropped
    'GIVE',       # This object is given away
    'RECEIVE',    # This object receives something
    'ATTACK',     # This object attacks or is attacked
    'DAMAGE',     # This object takes damage
    'DEATH',      # This object dies
    'KILL',       # This object kills something
    'CONNECT',    # Player connects
    'DISCONNECT', # Player disconnects
    'TICK',       # Periodic timer
    'USE',        # This object is used
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
        """Get all event triggers of a specific type from an object."""
        triggers = []
        attr_name = f'{EVENT_ATTR_PREFIX}{event_type.upper()}'

        # Check for the event attribute
        action = obj.db.get(attr_name)
        if action and isinstance(action, str):
            triggers.append(EventTrigger(event_type=event_type, action=action))

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

    def find_event_triggers(
        self,
        event: Event,
        obj: GameObject,
    ) -> list[EventTrigger]:
        """
        Find event triggers on an object that match the event.

        Args:
            event: The game event that occurred
            obj: The object to check for triggers

        Returns:
            List of matching EventTrigger objects
        """
        # Skip objects with HALT flag
        if obj.has_tag('halt'):
            return []

        # Get the event type string
        event_type = str(event.type)
        if '.' in event_type:
            event_type = event_type.split('.')[-1]

        return self.get_event_triggers(obj, event_type)


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

    # 4. Zone objects - find zone tag on room
    if player.location:
        for tag in player.location.tags.to_list():
            if tag.startswith('zone:'):
                # Would need a zone registry to find zone objects
                # For now, skip this - could be added later
                pass

    # 5. Global command room - TODO: implement Master Room

    return search_list
