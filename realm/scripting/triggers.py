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


# Trigger sigils are game settings (COMMAND_SIGIL / LISTEN_SIGIL in
# config.py) — '$' and '^' by default, for worlds where those collide
# with prose or house conventions. Ambient module state, wired at
# server construction like the other singletons.
DEFAULT_COMMAND_SIGIL = '$'
DEFAULT_LISTEN_SIGIL = '^'
_command_sigil = DEFAULT_COMMAND_SIGIL
_listen_sigil = DEFAULT_LISTEN_SIGIL


def set_trigger_sigils(command: str = DEFAULT_COMMAND_SIGIL,
                       listen: str = DEFAULT_LISTEN_SIGIL) -> None:
    """Install the trigger sigils (game config). Any length (1-16
    characters); no whitespace, no letters/digits (a sigil of 'go'
    would swallow ordinary values), and no ':' — the colon is the
    pattern:action separator, so a sigil containing one would break
    every trigger it prefixes. A bad sigil is a config error and
    raises at boot, not mid-parse."""
    global _command_sigil, _listen_sigil
    for name, sigil in (("command", str(command)), ("listen", str(listen))):
        if (not sigil or len(sigil) > 16
                or any(c.isalnum() or c.isspace() or c == ':'
                       for c in sigil)):
            raise ValueError(
                f"{name} sigil must be 1-16 non-alphanumeric, non-space "
                f"characters with no ':' (got {sigil!r})")
    _command_sigil = str(command)
    _listen_sigil = str(listen)


def get_trigger_sigils() -> tuple[str, str]:
    return _command_sigil, _listen_sigil


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
    ``action_type`` — i.e. ``"ENTER"`` matches ``Action(action_type=ActionType.ON_ENTER)``.
    Comparison is case-insensitive and ignores the ``on_`` prefix.
    """

    event_type: str  # ENTER, LEAVE, LOOK, GET, DROP, etc.
    action: str


# Mapping of event types to attribute prefix
EVENT_ATTR_PREFIX = 'ON_'

#: Objects with this tag offer their $-commands in every room (searched
#: last). Only admins may add it (permissions.roles.register_protected_tag).
GLOBAL_COMMANDS_TAG = "global_commands"


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

    def get_command_triggers(self, obj: GameObject) -> list[CommandTrigger]:
        """Get all command triggers from an object (its own and any
        inherited through the @parent chain — a template's $-commands
        work on every child)."""
        triggers = []

        for key, value in obj.db.merged().items():
            if key.upper().startswith(self.CMD_PREFIX):
                trigger = self._parse_command_trigger(value)
                if trigger:
                    triggers.append(trigger)

        return triggers

    def get_listen_triggers(self, obj: GameObject) -> list[ListenTrigger]:
        """Get all listen triggers from an object (own + @parent-inherited)."""
        triggers = []

        for key, value in obj.db.merged().items():
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

        for key, value in obj.db.merged().items():
            if key.upper() == attr_name and isinstance(value, str) and value:
                triggers.append(EventTrigger(event_type=event_type, action=value))

        return triggers

    def _parse_command_trigger(self, value: str) -> CommandTrigger | None:
        """
        Parse a command trigger attribute value.

        Format: $pattern: action   (the sigil is a game setting —
        COMMAND_SIGIL in config.py; '$' by default)
        Example: $greet *: say Hello, %0!
        """
        if not isinstance(value, str):
            return None

        value = value.strip()
        if not value.startswith(_command_sigil):
            return None

        # Find the colon separator
        colon_pos = value.find(':')
        if colon_pos == -1:
            return None

        pattern = value[len(_command_sigil):colon_pos].strip()
        action = value[colon_pos + 1:].strip()

        if not pattern or not action:
            return None

        return CommandTrigger(_pattern=pattern, action=action)

    def _parse_listen_trigger(self, value: str) -> ListenTrigger | None:
        """
        Parse a listen trigger attribute value.

        Format: ^pattern: action   (the sigil is a game setting —
        LISTEN_SIGIL in config.py; '^' by default)
        Example: ^*treasure*: whisper %# I know where treasure is...
        """
        if not isinstance(value, str):
            return None

        value = value.strip()
        if not value.startswith(_listen_sigil):
            return None

        colon_pos = value.find(':')
        if colon_pos == -1:
            return None

        pattern = value[len(_listen_sigil):colon_pos].strip()
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
            # Skip halted objects (their own halt tag, or their owner's)
            if obj.is_halted:
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
            # Skip halted objects (their own halt tag, or their owner's)
            if obj.is_halted:
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

    Search order (nearest first, so a local command shadows a global one):
    1. Contents of current room
    2. The room itself
    3. Player's inventory
    4. Zone masters sharing a zone with the room
    5. Objects tagged ``global_commands`` (admin-only tag): their
       $-commands work from every room

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

    # 5. Global commands: the tag index makes this lookup cheap.
    from realm.persistence.manager import get_active_manager
    store = get_active_manager()
    if store is not None:
        for obj in store.find_cached(tag=GLOBAL_COMMANDS_TAG):
            add_if_new(obj)

    return search_list


def script_code_of(attr_name: str, value: object) -> str | None:
    """The executable code inside a script-shaped attribute, or None.

    Recognises scripts exactly the way the engine does — by the value's
    sigil (``$cmd``/``^listen``, whose code is the part after the first
    ``:``) or by the attribute's name (``on_check``, ``on_tick``,
    ``ON_<EVENT>``). Used by ``@set`` to tell a builder at the prompt when
    a script will not run, rather than letting it sit dead.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    command_sigil, listen_sigil = get_trigger_sigils()
    for sigil in (command_sigil, listen_sigil):
        if value.startswith(sigil) and ':' in value:
            # `.strip()` matters: builders write "$fetch *: force(...)" with a
            # space after the colon, and a leading space is an IndentationError
            # to ast.parse even though the engine runs it fine.
            return value.split(':', 1)[1].strip()
    name = attr_name.upper()
    if name in ('ON_CHECK', 'ON_TICK') or name.startswith(EVENT_ATTR_PREFIX):
        return value.strip()
    return None


def unknown_verb(code: str) -> str | None:
    """When ``code`` is one line that reads like a script command
    (``get key``) but names no installed verb and is not valid Python, the
    message saying so; else None."""
    import re

    from realm.core.safe_eval import validate_code
    from realm.scripting.verbs import installed
    line = code.strip()
    if '\n' in line or not re.match(r"^[@A-Za-z_][\w@]*\s", line):
        return None
    verbs = installed()
    if verbs.match(line) is not None or not validate_code(line):
        return None
    word = line.split(None, 1)[0]
    return (f"'{word}' is not a script verb in this world "
            f"(known: {', '.join(verbs.names())})")


def validate_script(code: str) -> list[str]:
    """Problems that would stop ``code`` from running, or ``[]``.

    A one-line script command (``say hi``, ``pose waves``, ``trigger me/x``)
    whose verb is installed is valid as written. A line that reads like a
    command but names no installed verb (``get key`` in a world without the
    ``items`` feature) is reported by name. Anything else is checked as
    sandboxed Python.
    """
    from realm.core.safe_eval import validate_code
    from realm.scripting.verbs import installed
    if installed().is_command_line(code):
        return []
    missing = unknown_verb(code)
    return [missing] if missing else validate_code(code)
