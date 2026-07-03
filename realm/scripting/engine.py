"""
Script execution engine for REALM.

Ties together:
- TriggerManager: finding matching triggers
- ScriptSandbox: safe execution
- ScriptFunctions: built-in functions injected into scripts
- The propagation engine: how scripts observe the world and act back on it

The engine is owned by GameServer (``server.script_engine``) and wired in
two places:

- The command dispatcher's unknown handler calls ``handle_unknown_command``
  so ``$pattern`` softcode commands act as a fallback for player input.
- ``handle_action`` is registered as a propagation observer, so ``^listen``
  triggers overhear speech and ``ON_<EVENT>`` attribute triggers fire for
  any propagated action — the same message stream behaviors see.

Script actions (say/pose/emit/whisper) are emitted back through the
propagation engine as real actions, so players hear them, behaviors can
react to them, and other objects' listen triggers can fire — bounded by
MAX_SCRIPT_DEPTH so NPCs answering NPCs can't recurse forever.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from realm.core.propagation import ROOM_TARGET_CHAIN, Action, propagate
from realm.scripting.functions import ScriptFunctions
from realm.scripting.sandbox import (
    ScriptContext,
    ScriptError,
    ScriptSandbox,
    SimpleScriptRunner,
)
from realm.scripting.triggers import (
    TriggerManager,
    TriggerMatch,
    get_search_objects,
)

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.gateway.session import Session
    from realm.server.dispatcher import CommandContext


logger = logging.getLogger(__name__)


# Action types whose extra["message"] counts as overhearable speech.
# Whispers are deliberately excluded — bystanders only see the vague
# "X whispers something to Y" line, so scripts shouldn't overhear either.
LISTENABLE_ACTIONS = {
    "event:speech",
    "event:shout",
    "event:ooc",
    "event:emit",
}


class ScriptEngine:
    """
    Central script execution engine.

    Handles:
    - Softcode command fallback (unknown commands search $-triggers)
    - Listen trigger execution (^patterns overhear propagated speech)
    - Event trigger execution (ON_<EVENT> attributes fire on actions)
    """

    # Script-initiated actions may trigger further scripts (an NPC's say
    # matching another NPC's listen). Each nested trigger execution adds a
    # level; past this depth triggers are skipped.
    MAX_SCRIPT_DEPTH = 3

    def __init__(self, persistence: Any = None):
        self.trigger_manager = TriggerManager()
        self.sandbox = ScriptSandbox()
        self._persistence = persistence
        self._depth = 0

    # --- Entry point: unknown command fallback ---

    async def handle_unknown_command(self, ctx: CommandContext) -> bool:
        """
        Handle an unknown command by searching for softcode triggers.

        Called by the dispatcher's unknown handler when no built-in
        command matches.

        Returns:
            True if a trigger was found and executed, False otherwise.
        """
        if not ctx.player:
            return False

        search_objects = get_search_objects(ctx.player)

        match = self.trigger_manager.find_command_match(
            ctx.raw_input,
            search_objects,
        )

        if match:
            await self._execute_trigger(match, ctx.player, session=ctx.session)
            return True

        return False

    # --- Entry point: propagation observer ---

    async def handle_action(self, action: Action) -> None:
        """
        Observe a propagated action and fire matching scripts.

        Registered with the propagation engine by GameServer. Runs listen
        triggers for overhearable speech and ON_<EVENT> triggers for every
        action type.
        """
        if action.blocked:
            return

        room = self._action_room(action)

        # ^listen triggers on overheard speech
        if action.action_type in LISTENABLE_ACTIONS and room is not None:
            message = action.extra.get("message")
            if message:
                await self.handle_speech(action.actor, str(message), room)

        # ON_<EVENT> attribute triggers
        await self._fire_event_triggers(action, room)

    async def handle_speech(
        self,
        speaker: GameObject | None,
        speech: str,
        location: GameObject,
    ) -> None:
        """
        Run ^listen triggers for speech heard at a location.

        Args:
            speaker: Who spoke (None for sourceless emits)
            speech: What was said
            location: Where it was heard
        """
        search_objects = list(location.contents) + [location]

        matches = self.trigger_manager.find_listen_matches(speech, search_objects)

        for match in matches:
            # Don't overhear yourself
            if speaker is not None and match.obj == speaker:
                continue
            await self._execute_trigger(match, speaker, location=location)

    async def _fire_event_triggers(
        self,
        action: Action,
        room: GameObject | None,
    ) -> None:
        """Fire ON_<EVENT> triggers on objects that witnessed the action."""
        event_type = self._event_suffix(action.action_type)
        if not event_type:
            return

        # Witnesses: the room, its contents, and the target — like the
        # propagation chain itself. The actor doesn't trigger its own
        # ON_<EVENT>; it gets ON_ARRIVE for movement instead (below).
        candidates: list[GameObject] = []
        seen: set[str] = set()

        def add(obj: GameObject | None) -> None:
            if obj is None or obj.id in seen:
                return
            if action.actor is not None and obj.id == action.actor.id:
                return
            seen.add(obj.id)
            candidates.append(obj)

        add(room)
        if room is not None:
            for obj in room.contents:
                add(obj)
        add(action.target)

        for obj in candidates:
            if obj.has_tag('halt'):
                continue
            for trigger in self.trigger_manager.get_event_triggers(obj, event_type):
                match = TriggerMatch(
                    trigger=trigger,  # type: ignore[arg-type]
                    captures=[],
                    full_match=action.action_type,
                    obj=obj,
                    action=trigger.action,
                )
                await self._execute_trigger(match, action.actor, location=room)

        # The mover's own hook: ON_ARRIVE fires on the actor when it enters
        # somewhere new (plan.md: "this object arrives somewhere new").
        if event_type == 'ENTER' and action.actor is not None:
            actor = action.actor
            if not actor.has_tag('halt'):
                for trigger in self.trigger_manager.get_event_triggers(actor, 'ARRIVE'):
                    match = TriggerMatch(
                        trigger=trigger,  # type: ignore[arg-type]
                        captures=[],
                        full_match=action.action_type,
                        obj=actor,
                        action=trigger.action,
                    )
                    await self._execute_trigger(match, actor, location=room)

    @staticmethod
    def _event_suffix(action_type: str) -> str:
        """``event:on_enter`` → ``ENTER``; ``item:get`` → ``GET``."""
        suffix = action_type.rsplit(":", 1)[-1].upper()
        if suffix.startswith("ON_"):
            suffix = suffix[3:]
        return suffix

    @staticmethod
    def _action_room(action: Action) -> GameObject | None:
        """The room where an action is audible/visible."""
        if action.actor is not None and action.actor.location is not None:
            return action.actor.location
        target = action.target
        if target is None:
            return None
        if target.location is not None:
            return target.location
        # Target may BE the room (broadcast actions).
        if target.contents or target.has_tag('room'):
            return target
        return None

    # --- Trigger execution ---

    async def _execute_trigger(
        self,
        match: TriggerMatch,
        enactor: GameObject | None,
        *,
        session: Session | None = None,
        location: GameObject | None = None,
    ) -> None:
        """Execute a matched trigger, depth-guarded."""
        if self._depth >= self.MAX_SCRIPT_DEPTH:
            logger.warning(
                f"Script depth limit ({self.MAX_SCRIPT_DEPTH}) reached; "
                f"skipping trigger on {match.obj.name}"
            )
            return

        if location is None and enactor is not None:
            location = enactor.location

        script_ctx = ScriptContext(
            enactor=enactor,
            executor=match.obj,
            location=location,
            captures=match.captures,
        )

        self._depth += 1
        try:
            action_code = match.action

            if SimpleScriptRunner.is_simple_script(action_code):
                # Simple expansion — substitute and run as a script command
                expanded = SimpleScriptRunner.expand_simple(action_code, script_ctx)
                await self._run_script_command(match.obj, expanded)
            else:
                # Full Python script execution with game functions injected
                functions = ScriptFunctions(
                    enactor=enactor,
                    executor=match.obj,
                    location=location,
                    persistence=self._persistence,
                )
                try:
                    _result, output = await self.sandbox.execute_async(
                        action_code,
                        script_ctx,
                        functions=functions.to_dict(),
                    )
                except ScriptError as e:
                    logger.warning(f"Script error on {match.obj.name}: {e}")
                    if session:
                        await session.send(f"Script error: {e}")
                    return

                # Output lines are script commands (say/pose/emit/whisper)
                for line in output:
                    line = line.strip()
                    if line:
                        await self._run_script_command(match.obj, line)

                # Deliveries queued by pemit/remit/oemit during execution
                self._deliver_queued(functions)
        finally:
            self._depth -= 1

    # --- Script command emission (via propagation) ---

    async def _run_script_command(self, executor: GameObject, command: str) -> None:
        """
        Run a command produced by a script, acting as the scripted object.

        Communication commands are emitted through the propagation engine as
        real actions — players hear them, behaviors react, other scripts'
        listen triggers can fire (depth-guarded). Anything else is logged
        and dropped until scripted objects can drive the full dispatcher.
        """
        command = command.strip()
        if not command:
            return
        lower = command.lower()

        if lower.startswith('say '):
            await self._emit_speech(executor, command[4:])

        elif lower.startswith('pose ') or command.startswith(':'):
            pose = command[5:] if lower.startswith('pose ') else command[1:]
            await self._emit_pose(executor, pose)

        elif lower.startswith('@emit ') or lower.startswith('emit ') or command.startswith('\\'):
            if command.startswith('\\'):
                message = command[1:]
            elif lower.startswith('@emit '):
                message = command[6:]
            else:
                message = command[5:]
            await self._emit_raw(executor, message)

        elif lower.startswith('whisper '):
            parts = command[8:].split('=', 1)
            if len(parts) == 2:
                await self._emit_whisper(executor, parts[0].strip(), parts[1].strip())

        else:
            logger.warning(
                f"Script on {executor.name} produced unsupported command: {command!r}"
            )

    async def _emit_speech(self, speaker: GameObject, message: str) -> None:
        """Scripted say — mirrors cmd_say's action shape."""
        location = speaker.location
        if location is None:
            return
        action = Action(
            actor=speaker,
            target=location,
            action_type="event:speech",
            chain=ROOM_TARGET_CHAIN,
            tags={"scripted"},
            extra={"message": message},
        )
        action.add_message("actor", f'You say, "{message}"', success_only=True)
        action.add_message("room", f'{{actor}} says, "{message}"', success_only=True)
        await propagate(action)

    async def _emit_pose(self, poser: GameObject, pose_text: str) -> None:
        """Scripted pose — mirrors cmd_pose's action shape."""
        location = poser.location
        if location is None:
            return
        action = Action(
            actor=poser,
            target=location,
            action_type="event:emote",
            chain=ROOM_TARGET_CHAIN,
            tags={"scripted"},
            extra={"pose": pose_text},
        )
        action.add_message("actor", f"{{actor}} {pose_text}", success_only=True)
        action.add_message("room", f"{{actor}} {pose_text}", success_only=True)
        await propagate(action)

    async def _emit_raw(self, executor: GameObject, message: str) -> None:
        """Scripted @emit — raw text to the executor's room."""
        location = executor.location
        if location is None:
            return
        action = Action(
            actor=executor,
            target=location,
            action_type="event:emit",
            chain=ROOM_TARGET_CHAIN,
            tags={"scripted"},
            extra={"message": message},
        )
        action.add_message("actor", message, success_only=True)
        action.add_message("room", message, success_only=True)
        await propagate(action)

    async def _emit_whisper(
        self,
        speaker: GameObject,
        target_spec: str,
        message: str,
    ) -> None:
        """Scripted whisper — mirrors cmd_whisper's action shape."""
        location = speaker.location
        if location is None:
            return

        target = None
        target_lower = target_spec.lower()
        for obj in location.contents:
            if obj.name.lower() == target_lower:
                target = obj
                break
        if target is None or target == speaker:
            return

        action = Action(
            actor=speaker,
            target=target,
            action_type="event:whisper",
            tags={"scripted"},
            extra={"message": message},
        )
        action.add_message("actor", f'You whisper to {{target}}, "{message}"', success_only=True)
        action.add_message("target", f'{{actor}} whispers, "{message}"', success_only=True)
        action.add_message("room", "{actor} whispers something to {target}.", success_only=True)
        await propagate(action)

    def _deliver_queued(self, functions: ScriptFunctions) -> None:
        """Deliver pemit/remit/oemit entries queued during script execution."""
        for kind, obj, message in functions.command_queue:
            if kind == 'pemit':
                obj.msg(message)
            elif kind == 'remit':
                obj.msg_contents(message)
            elif kind == 'oemit':
                room = functions.executor.location if functions.executor else None
                if room is not None:
                    room.msg_contents(message, exclude=[obj])
        functions.command_queue.clear()
