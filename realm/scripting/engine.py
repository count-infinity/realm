"""
Script execution engine for REALM.

Ties together:
- TriggerManager: Finding matching triggers
- ScriptSandbox: Safe execution
- ScriptFunctions: Built-in functions
- Command dispatcher integration

This is the main entry point for executing softcode.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from realm.scripting.sandbox import (
    ScriptSandbox,
    ScriptContext,
    ScriptError,
    SimpleScriptRunner,
)
from realm.scripting.triggers import (
    TriggerManager,
    TriggerMatch,
    get_search_objects,
)
from realm.scripting.functions import ScriptFunctions

if TYPE_CHECKING:
    from realm.core.events import Event
    from realm.core.objects import GameObject
    from realm.gateway.session import Session
    from realm.server.dispatcher import CommandContext


logger = logging.getLogger(__name__)


class ScriptEngine:
    """
    Central script execution engine.

    Handles:
    - Softcode command fallback (unknown commands check triggers)
    - Listen trigger execution (on speech events)
    - Event trigger execution (on game events)
    """

    def __init__(self, persistence: Any = None):
        self.trigger_manager = TriggerManager()
        self.sandbox = ScriptSandbox()
        self._persistence = persistence

    async def handle_unknown_command(self, ctx: CommandContext) -> bool:
        """
        Handle an unknown command by searching for softcode triggers.

        This is called by the command dispatcher when no built-in command matches.

        Args:
            ctx: The command context

        Returns:
            True if a trigger was found and executed, False otherwise
        """
        if not ctx.player:
            return False

        # Get objects to search for triggers
        search_objects = get_search_objects(ctx.player)

        # Look for a matching command trigger
        match = self.trigger_manager.find_command_match(
            ctx.raw_input,
            search_objects,
        )

        if match:
            await self._execute_trigger(match, ctx.player, ctx.session)
            return True

        return False

    async def handle_speech(
        self,
        speaker: GameObject,
        speech: str,
        location: GameObject,
    ) -> None:
        """
        Handle speech/emote for listen triggers.

        Called when someone speaks or emotes. Searches for ^pattern triggers.

        Args:
            speaker: Who spoke
            speech: What was said
            location: Where it happened
        """
        # Get objects to search - room contents plus room itself
        search_objects = list(location.contents) + [location]

        # Find all matching listen triggers
        matches = self.trigger_manager.find_listen_matches(speech, search_objects)

        # Execute each matching trigger
        for match in matches:
            # Don't trigger on yourself
            if match.obj == speaker:
                continue

            await self._execute_trigger(match, speaker, None)

    async def handle_event(self, event: Event) -> None:
        """
        Handle a game event by checking for event triggers.

        Called by the EventBus after an event passes validation.

        Args:
            event: The game event
        """
        # Collect objects that might have triggers for this event
        objects_to_check: list[GameObject] = []

        # Target object
        if event.target:
            objects_to_check.append(event.target)

        # Location and its contents
        if event.location:
            objects_to_check.append(event.location)
            objects_to_check.extend(event.location.contents)

        # Source (less common to have triggers on source)
        if event.source and event.source not in objects_to_check:
            objects_to_check.append(event.source)

        # Check each object for matching triggers
        for obj in objects_to_check:
            triggers = self.trigger_manager.find_event_triggers(event, obj)

            for trigger in triggers:
                await self._execute_event_trigger(trigger, obj, event)

    async def _execute_trigger(
        self,
        match: TriggerMatch,
        enactor: GameObject,
        session: Session | None,
    ) -> None:
        """Execute a matched trigger."""
        # Build script context
        script_ctx = ScriptContext(
            enactor=enactor,
            executor=match.obj,
            location=enactor.location,
            captures=match.captures,
        )

        # Check if this is a simple command or needs Python execution
        action = match.action

        if SimpleScriptRunner.is_simple_script(action):
            # Simple expansion - just substitute and execute as command
            expanded = SimpleScriptRunner.expand_simple(action, script_ctx)
            await self._queue_command(match.obj, expanded, session)
        else:
            # Full Python script execution
            try:
                result, output = await self.sandbox.execute_async(
                    action,
                    script_ctx,
                )

                # Process output lines as commands
                for line in output:
                    line = line.strip()
                    if line:
                        await self._queue_command(match.obj, line, session)

            except ScriptError as e:
                logger.warning(f"Script error on {match.obj.name}: {e}")
                if session:
                    await session.send(f"Script error: {e}")

    async def _execute_event_trigger(
        self,
        trigger: Any,  # EventTrigger
        obj: GameObject,
        event: Event,
    ) -> None:
        """Execute an event trigger."""
        # Build script context from event
        script_ctx = ScriptContext(
            enactor=event.source,
            executor=obj,
            location=event.location,
            captures=[],  # Event triggers don't have captures
            extra={
                'event': event,
                'event_type': str(event.type),
                'target': event.target,
                'data': event.data,
            },
        )

        action = trigger.action

        if SimpleScriptRunner.is_simple_script(action):
            expanded = SimpleScriptRunner.expand_simple(action, script_ctx)
            await self._queue_command(obj, expanded, None)
        else:
            try:
                result, output = await self.sandbox.execute_async(
                    action,
                    script_ctx,
                )

                for line in output:
                    line = line.strip()
                    if line:
                        await self._queue_command(obj, line, None)

            except ScriptError as e:
                logger.warning(f"Event script error on {obj.name}: {e}")

    async def _queue_command(
        self,
        executor: GameObject,
        command: str,
        session: Session | None,
    ) -> None:
        """
        Queue a command for execution by an object.

        For now, we handle simple built-in commands directly.
        More complex routing would go through the dispatcher.
        """
        command = command.strip()
        if not command:
            return

        # Handle common simple commands directly
        if command.lower().startswith('say '):
            message = command[4:]
            await self._emit_speech(executor, message)

        elif command.lower().startswith('pose ') or command.startswith(':'):
            message = command[5:] if command.lower().startswith('pose ') else command[1:]
            await self._emit_pose(executor, message)

        elif command.lower().startswith('@emit ') or command.startswith('\\'):
            message = command[6:] if command.lower().startswith('@emit ') else command[1:]
            await self._emit_raw(executor.location, message)

        elif command.lower().startswith('whisper '):
            # whisper target=message
            parts = command[8:].split('=', 1)
            if len(parts) == 2:
                await self._emit_whisper(executor, parts[0].strip(), parts[1].strip())

        else:
            # For other commands, log them (full implementation would re-route to dispatcher)
            logger.debug(f"Script queued command from {executor.name}: {command}")

    async def _emit_speech(self, speaker: GameObject, message: str) -> None:
        """Emit speech to a room."""
        if not speaker.location:
            return

        # Format: Speaker says, "message"
        formatted = f'{speaker.name} says, "{message}"'

        # Send to all in room
        for obj in speaker.location.contents:
            if obj.has_tag('player'):
                # Players would receive via their session
                # For now, just log
                logger.debug(f"Speech to {obj.name}: {formatted}")

    async def _emit_pose(self, poser: GameObject, message: str) -> None:
        """Emit a pose to a room."""
        if not poser.location:
            return

        # Format: Name message (e.g., "Bob waves hello")
        formatted = f'{poser.name} {message}'

        for obj in poser.location.contents:
            if obj.has_tag('player'):
                logger.debug(f"Pose to {obj.name}: {formatted}")

    async def _emit_raw(self, location: GameObject | None, message: str) -> None:
        """Emit raw text to a room."""
        if not location:
            return

        for obj in location.contents:
            if obj.has_tag('player'):
                logger.debug(f"Emit to {obj.name}: {message}")

    async def _emit_whisper(
        self,
        speaker: GameObject,
        target_spec: str,
        message: str,
    ) -> None:
        """Send a whisper to a target."""
        # Find target in same room
        if not speaker.location:
            return

        target = None
        target_lower = target_spec.lower()

        for obj in speaker.location.contents:
            if obj.name.lower() == target_lower:
                target = obj
                break

        if target:
            logger.debug(f"Whisper from {speaker.name} to {target.name}: {message}")


# Global engine instance (set by GameServer)
_engine: ScriptEngine | None = None


def get_engine() -> ScriptEngine | None:
    """Get the global script engine."""
    return _engine


def set_engine(engine: ScriptEngine) -> None:
    """Set the global script engine."""
    global _engine
    _engine = engine


async def softcode_fallback(ctx: CommandContext) -> None:
    """
    Command dispatcher fallback handler for softcode.

    This is registered with the dispatcher as the unknown command handler.
    """
    engine = get_engine()
    if engine:
        found = await engine.handle_unknown_command(ctx)
        if found:
            return

    # No trigger found
    await ctx.session.send(f"Unknown command: {ctx.command_name}")
