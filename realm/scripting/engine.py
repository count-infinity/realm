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

from realm.core.propagation import Action
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


# --- Ambient engine accessor -------------------------------------------------
# Set by GameServer at startup so behaviors (script_ticker) and builder
# commands (@tr) can reach the live engine — same pattern as the combat
# manager and persistence manager.

_active_engine: ScriptEngine | None = None


def set_script_engine(engine: ScriptEngine | None) -> None:
    global _active_engine
    _active_engine = engine


def get_script_engine() -> ScriptEngine | None:
    return _active_engine


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
        self.dispatcher = None  # set by GameServer; enables force()
        self._depth = 0
        # One-shot scheduled commands: (fire_at_monotonic, executor, command).
        # In-memory only — like MUSH @waits, pending waits don't survive a
        # reboot. Fired from the server heartbeat via tick_waits().
        self._waits: list[tuple[float, GameObject, str]] = []

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
            # The use lock gates who may fire this object's $-commands
            # (default True — an unset lock changes nothing).
            from realm.permissions.locks import LockType, check_lock
            if not check_lock(match.obj, LockType.USE, ctx.player):
                return False

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

        from realm.permissions.locks import LockType, check_lock

        for match in matches:
            # Don't overhear yourself
            if speaker is not None and match.obj == speaker:
                continue
            # The listen lock gates whose speech this object's ^patterns
            # may overhear (default True).
            if speaker is not None and not check_lock(
                match.obj, LockType.LISTEN, speaker
            ):
                continue
            await self._execute_trigger(match, speaker, location=location)

    # --- Entry point: named-attribute triggering (@tr) ---

    async def run_object_script(
        self,
        obj: GameObject,
        attr_name: str,
        *,
        enactor: GameObject | None = None,
    ) -> bool:
        """
        Execute the script stored in ``obj``'s ``attr_name`` attribute,
        with ``obj`` as executor — the MUSH ``@tr obj/attr`` primitive.

        Used by the @tr builder command, the ``trigger`` script command,
        and the script_ticker behavior (which fires ``on_tick``). Depth-
        guarded like every other trigger path, and honors the ``halt``
        tag.

        Returns:
            True if a script was found and executed.
        """
        if obj.has_tag('halt'):
            return False

        code = obj.db.get(attr_name)
        if code is None:
            code = obj.db.get(attr_name.upper())
        if code is None:
            code = obj.db.get(attr_name.lower())
        if not isinstance(code, str) or not code.strip():
            return False

        match = TriggerMatch(
            trigger=None,  # type: ignore[arg-type]
            captures=[],
            full_match=attr_name,
            obj=obj,
            action=code,
        )
        await self._execute_trigger(match, enactor or obj, location=obj.location)
        return True

    async def run_check_hook(self, obj: GameObject, action: Action) -> None:
        """
        Run ``obj``'s ``on_check`` softcode DURING the propagation check
        pass — giving data/softcode the interception power a Python behavior
        has there: veto (``block``) and modify (``mod`` / ``set_adata``),
        bound to the in-flight action. This is how resistance, wards, armor,
        and counterspells become data (see docs).

        It is **decision-only by construction**: the script runs against a
        restricted READ-ONLY namespace (``ScriptFunctions.readonly_dict`` —
        reads, dice, formatting) plus the check verbs, so it cannot mutate
        or queue world state. Reacting to an action belongs in ``on_react``
        / ``ON_<EVENT>`` triggers, which run after.

        No shared-depth guard here: a check hook has no way to propagate
        (its namespace has no act/emit/force/damage), so it can't recurse —
        and a ward must not silently *fail open* just because an unrelated
        script chain spent the depth budget. The sandbox's own call/time
        limits bound it.
        """
        if obj.has_tag('halt'):
            return
        code = obj.db.get('on_check')
        if not isinstance(code, str) or not code.strip():
            return
        from realm.scripting.sandbox import ScriptContext

        ctx = ScriptContext(enactor=action.actor, executor=obj,
                            location=obj.location)
        functions = ScriptFunctions(
            enactor=action.actor, executor=obj, location=obj.location,
            persistence=self._persistence)
        namespace = functions.readonly_dict()
        namespace.update(self._check_namespace(action))
        try:
            await self.sandbox.execute_async(code, ctx, functions=namespace)
        except ScriptError as exc:
            logger.warning(f"on_check error on {obj.name}: {exc}")

    @staticmethod
    def _check_namespace(action: Action) -> dict:
        """The extra softcode names available to an ``on_check`` script —
        the in-flight action plus the veto/modify verbs."""
        return {
            'atype': action.action_type,       # the action's type string
            'actor': action.actor,             # who is acting
            'target': action.target,           # what it targets
            'has_atag': lambda tag: action.has_tag(str(tag)),
            'adata': lambda key, default=None: action.extra.get(key, default),
            'set_adata': lambda key, value: action.extra.__setitem__(
                str(key), value),
            'block': lambda reason='': action.block(str(reason)),
            'mod': lambda value: action.add_modifier(int(value), 'on_check'),
            'is_blocked': lambda: action.blocked,
        }

    def _install_softcode_prompt(self, player, text, callback,
                                 executor_id, persistent):
        """Capture a player's next line into a softcode callback script."""
        from realm.persistence.manager import get_active_manager

        session = getattr(player, '_session', None) or self._session_for(player)
        if session is None:
            return
        if persistent:
            player.db.input_prompt = {
                'callback': callback, 'executor': executor_id}

        async def handler(sess, line: str) -> bool:
            word = line.split()[0].lower() if line.split() else ""
            if word in ('help', 'quit', 'exit'):
                return False
            sess.input_handler = None
            player.db.delete('input_prompt')
            manager = get_active_manager()
            executor = manager.get_cached(executor_id) if (
                manager and executor_id) else player
            if executor is None:
                executor = player
            # Run the callback AS the executor, answer bound as arg0/%0.
            await self._run_named_with_args(executor, callback, [line],
                                            enactor=player)
            return True

        session.input_handler = handler
        # asyncio can't await here (drain is sync-ish); send via msg.
        player.msg(text)

    def _session_for(self, player):
        """Find a player's live session, if any."""
        mgr = getattr(self, 'session_manager', None)
        if mgr is None:
            return None
        for s in mgr.all_sessions():
            if s.player is player:
                return s
        return None

    async def _run_named_with_args(self, obj, attr_name, args, *, enactor=None):
        """run_object_script but with positional args bound as captures."""
        code = obj.db.get(attr_name) or obj.db.get(str(attr_name).upper())
        if not isinstance(code, str) or not code.strip():
            return
        match = TriggerMatch(trigger=None, captures=[str(a) for a in args],
                             full_match=attr_name, obj=obj, action=code)
        await self._execute_trigger(match, enactor or obj, location=obj.location)

    async def run_code(
        self,
        executor: GameObject,
        code: str,
        *,
        enactor: GameObject | None = None,
    ) -> tuple:
        """
        Execute arbitrary softcode AS ``executor`` (the @eval / think<<>>
        primitive). Returns (result, error_or_None). Side-effect commands
        (pemit/say/move/force...) and queued world ops are delivered like
        any script. Depth- and halt-guarded.
        """
        from realm.scripting.sandbox import ScriptContext

        if executor.has_tag('halt') or self._depth >= self.MAX_SCRIPT_DEPTH:
            return None, "halted or too deep"

        script_ctx = ScriptContext(
            enactor=enactor or executor,
            executor=executor,
            location=executor.location,
        )
        functions = ScriptFunctions(
            enactor=enactor or executor,
            executor=executor,
            location=executor.location,
            persistence=self._persistence,
        )
        self._depth += 1
        try:
            try:
                result, output = await self.sandbox.execute_async(
                    code, script_ctx, functions=functions.to_dict())
            except ScriptError as e:
                return None, str(e)
            for line in output:
                line = line.strip()
                if line:
                    await self._run_script_command(executor, line)
            await self._deliver_queued(functions)
            return result, None
        finally:
            self._depth -= 1

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
            # Zone masters witness events in their member rooms.
            from realm.core.zones import zone_masters
            for master in zone_masters(room):
                add(master)
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

                # Deliveries and world ops queued during execution
                await self._deliver_queued(functions)
        finally:
            self._depth -= 1

    # --- Script command emission (via propagation) ---

    async def _run_script_command(self, executor: GameObject, command: str) -> None:
        """
        Run a command produced by a script, acting as the scripted object.

        Communication commands are emitted through the propagation engine as
        real actions — players hear them, behaviors react, other scripts'
        listen triggers can fire (depth-guarded). ``move`` routes through
        move_through_exit, so locks, guards, and closed doors apply to
        scripted movement exactly as they do to players. ``trigger`` runs
        a named script attribute (self or a room neighbor). Anything else
        is logged and dropped until scripted objects can drive the full
        dispatcher.
        """
        command = command.strip()
        if not command:
            return
        lower = command.lower()

        if lower.startswith('say '):
            await self._emit_speech(executor, command[4:])

        elif lower.startswith('move ') or lower.startswith('go '):
            direction = command.split(None, 1)[1] if len(command.split(None, 1)) > 1 else ""
            await self._scripted_move(executor, direction.strip())

        elif lower.startswith('trigger ') or lower.startswith('@tr '):
            spec = command.split(None, 1)[1] if len(command.split(None, 1)) > 1 else ""
            await self._scripted_trigger(executor, spec.strip())

        elif lower.startswith(('get ', 'take ', 'drop ', 'open ', 'close ', 'give ')):
            verb, args = command.split(None, 1)
            await self._scripted_verb(executor, verb.lower(), args.strip())

        elif lower.startswith('wait '):
            # wait <seconds> <command> — one-shot, fired from the heartbeat.
            parts = command.split(None, 2)
            if len(parts) == 3:
                try:
                    seconds = float(parts[1])
                except ValueError:
                    return
                self.schedule_wait(executor, seconds, parts[2])

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

    async def _scripted_move(self, executor: GameObject, direction: str) -> None:
        """
        Scripted movement through a named exit in the executor's room.

        Full movement pathway — exit locks, closed doors, guard behaviors,
        and on_leave/on_enter propagation all apply. A blocked move is a
        silent no-op for the script (the world already delivered the
        block to whoever should see it).
        """
        if not direction or executor.location is None:
            return

        from realm.core.movement import move_through_exit, resolve_exit_destination
        from realm.core.search import AmbiguousMatchError, match_one

        exits = [obj for obj in executor.location.contents if obj.has_tag('exit')]
        try:
            exit_obj = match_one(direction, exits)
        except AmbiguousMatchError:
            exit_obj = None
        if exit_obj is None:
            logger.warning(
                f"Script on {executor.name} tried to move through "
                f"unknown exit {direction!r}"
            )
            return

        destination = resolve_exit_destination(exit_obj)
        if destination is None:
            return
        await move_through_exit(executor, destination, exit_obj=exit_obj)

    async def _scripted_verb(self, executor: GameObject, verb: str, args: str) -> None:
        """
        Manipulation verbs for scripted objects — the same cores player
        commands use (realm.core.verbs), so locks and behavior gates
        apply identically.
        """
        from realm.core.search import AmbiguousMatchError, match_one
        from realm.core.verbs import do_close, do_drop, do_get, do_give, do_open

        def find_in(candidates: list[GameObject], spec: str) -> GameObject | None:
            try:
                return match_one(spec, candidates)
            except AmbiguousMatchError:
                return None

        room_contents = list(executor.location.contents) if executor.location else []

        if verb in ('get', 'take'):
            target = find_in([o for o in room_contents if o is not executor], args)
            if target is not None:
                await do_get(executor, target)
        elif verb == 'drop':
            target = find_in(list(executor.contents), args)
            if target is not None:
                await do_drop(executor, target)
        elif verb == 'give':
            # give <item> = <target>  or  give <item> to <target>
            if '=' in args:
                item_spec, target_spec = args.split('=', 1)
            elif ' to ' in args.lower():
                idx = args.lower().index(' to ')
                item_spec, target_spec = args[:idx], args[idx + 4:]
            else:
                return
            item = find_in(list(executor.contents), item_spec.strip())
            target = find_in([o for o in room_contents if o is not executor],
                             target_spec.strip())
            if item is not None and target is not None:
                await do_give(executor, item, target)
        elif verb in ('open', 'close'):
            target = find_in([o for o in room_contents if o is not executor], args)
            if target is not None:
                if verb == 'open':
                    await do_open(executor, target)
                else:
                    await do_close(executor, target)

    # --- One-shot waits (fired from the server heartbeat) ---

    def schedule_wait(self, executor: GameObject, seconds: float, command: str) -> None:
        """Queue a script command to run ~seconds from now (in-memory)."""
        import time as _time
        seconds = max(0.0, min(float(seconds), 3600.0))
        self._waits.append((_time.monotonic() + seconds, executor, str(command)))

    async def tick_waits(self) -> None:
        """Fire due one-shot waits. Called each pulse by the game server."""
        if not self._waits:
            return
        import time as _time
        now = _time.monotonic()
        due = [w for w in self._waits if w[0] <= now]
        if not due:
            return
        self._waits = [w for w in self._waits if w[0] > now]
        for _at, executor, command in due:
            if executor.has_tag('halt'):
                continue
            await self._run_script_command(executor, command)

    async def _scripted_trigger(self, executor: GameObject, spec: str) -> None:
        """
        ``trigger <attr>`` runs the executor's own attribute;
        ``trigger <obj>/<attr>`` runs a room neighbor's (or its own).
        Depth-guarded by run_object_script → _execute_trigger.
        """
        if not spec:
            return

        target = executor
        attr_name = spec
        if '/' in spec:
            obj_spec, attr_name = spec.split('/', 1)
            obj_spec = obj_spec.strip()
            attr_name = attr_name.strip()
            if obj_spec.lower() not in ('me', 'self', ''):
                from realm.core.search import AmbiguousMatchError, match_one

                candidates: list[GameObject] = []
                if executor.location is not None:
                    candidates.extend(executor.location.contents)
                candidates.extend(executor.contents)
                try:
                    found = match_one(obj_spec, candidates)
                except AmbiguousMatchError:
                    found = None
                if found is None:
                    logger.warning(
                        f"Script on {executor.name} tried to trigger "
                        f"unknown object {obj_spec!r}"
                    )
                    return
                target = found

        if not attr_name:
            return

        # Cross-object triggering is control-level power (or an explicit
        # command lock grant) — same rule as the @tr command.
        if target is not executor:
            from realm.permissions.locks import may_trigger
            if not may_trigger(executor, target):
                logger.warning(
                    f"Script on {executor.name} denied trigger on "
                    f"{target.name} (no control / command lock)"
                )
                return

        await self.run_object_script(target, attr_name, enactor=executor)

    async def _emit_speech(self, speaker: GameObject, message: str) -> None:
        """Scripted say — same pathway as cmd_say."""
        from realm.core.verbs import do_say
        await do_say(speaker, message, scripted=True)

    async def _emit_pose(self, poser: GameObject, pose_text: str) -> None:
        """Scripted pose — same pathway as cmd_pose."""
        from realm.core.verbs import do_pose
        await do_pose(poser, pose_text, scripted=True)

    async def _emit_raw(self, executor: GameObject, message: str) -> None:
        """Scripted @emit — same pathway as cmd_emit."""
        from realm.core.verbs import do_emit
        await do_emit(executor, message, scripted=True)

    async def _emit_whisper(
        self,
        speaker: GameObject,
        target_spec: str,
        message: str,
    ) -> None:
        """Scripted whisper — same pathway as cmd_whisper. Target is
        resolved perception-aware against the speaker's room, like every
        other name lookup in the engine (no more exact-match divergence)."""
        if speaker.location is None:
            return
        from realm.core.perception import can_see
        from realm.core.search import AmbiguousMatchError, match_one
        try:
            target = match_one(
                target_spec,
                [o for o in speaker.location.contents
                 if o is not speaker and can_see(speaker, o)],
            )
        except AmbiguousMatchError:
            return  # a script whisper to an ambiguous name is a no-op
        if target is None:
            return
        from realm.core.verbs import do_whisper
        await do_whisper(speaker, target, message, scripted=True)

    async def _deliver_queued(self, functions: ScriptFunctions) -> None:
        """
        Drain the queue scripts fill during (worker-thread) execution:
        messages (pemit/remit/oemit) and world ops that need the event
        loop (save/destroy). Saves are deduped — a script hammering
        set_attr costs one persistence write.
        """
        saved: set[str] = set()
        for kind, obj, message in functions.command_queue:
            if kind == 'pemit':
                obj.msg(message)
            elif kind == 'remit':
                obj.msg_contents(message)
            elif kind == 'oemit':
                room = functions.executor.location if functions.executor else None
                if room is not None:
                    room.msg_contents(message, exclude=[obj])
            elif kind == 'oob':
                package, data = message
                obj.msg_oob(package, data)
            elif kind == 'save':
                if self._persistence is not None and obj.id not in saved:
                    saved.add(obj.id)
                    await self._persistence.save(obj)
            elif kind == 'destroy':
                # Evacuation guard: never orphan a player by destroying the
                # room they stand in — relocate them along the
                # home → start_room ladder first. (Instance reaping does its
                # own return_room-aware evacuation in destroy_instance; this
                # is the general safety net.)
                if any(c.has_tag('player') for c in obj.contents):
                    from realm.core.instances import evacuation_room
                    for occupant in list(obj.contents):
                        if occupant.has_tag('player'):
                            occupant.location = evacuation_room(
                                self._persistence, occupant)
                obj.location = None
                if self._persistence is not None:
                    await self._persistence.delete(obj)
            elif kind == 'death_check':
                # message slot carries the killer (the scripted object).
                if int(obj.db.get('hp') or 0) <= 0:
                    from realm.combat.manager import get_combat_manager
                    manager = get_combat_manager()
                    if manager is not None:
                        killer = message if message is not None else None
                        await manager.handle_death(obj, killer=killer)
            elif kind == 'combat':
                # message slot carries the combat target.
                from realm.combat.manager import get_combat_manager
                manager = get_combat_manager()
                if manager is not None:
                    await manager.initiate(obj, message)
            elif kind == 'wait':
                seconds, command = message
                self.schedule_wait(obj, seconds, command)
            elif kind == 'prompt':
                text, callback, executor_id, persistent = message
                self._install_softcode_prompt(
                    obj, text, callback, executor_id, persistent)
            elif kind == 'force':
                if self.dispatcher is not None:
                    from realm.server.puppet import force_command
                    await force_command(self.dispatcher, obj, message)
            elif kind == 'act':
                msg, targeting, action_type = message
                await self._propagate_act(
                    functions.executor, obj, msg, targeting, action_type)
            elif kind == 'enter_instance':
                if self._persistence is not None:
                    from realm.core import instances
                    template, mode, return_room_id, ttl = message
                    return_room = (self._persistence.get_cached(return_room_id)
                                   if return_room_id else None)
                    kwargs: dict[str, Any] = {
                        'mode': mode, 'return_room': return_room}
                    if ttl is not None:
                        kwargs['idle_ttl'] = ttl
                    await instances.enter(
                        template, obj, self._persistence, **kwargs)
        functions.command_queue.clear()

    async def _propagate_act(self, actor, target, message, targeting,
                             action_type):
        """Drive a softcode act() through propagation with a targeting
        vocabulary — the multiroom surface (scry, remote cast, zone alarm).
        Every leg (origin room + each destination) gets the two-pass, so
        wards can veto anywhere. Reaching a destination is authority-gated
        by its REACH lock (default-open, like teleport), so a room or zone
        can lock out remote actions — the permission gate, not a hoped-for
        ward."""
        from realm.core.propagation import _room_of, propagate, remote_chain
        from realm.permissions.locks import LockType, check_lock
        if actor is None:
            return

        # Destination rooms this targeting reaches, before the auth gate.
        if targeting == 'zone':
            from realm.core.zones import zone_rooms, zone_tags
            origin = _room_of(target)
            candidates: dict[str, GameObject] = {}
            for zone in (zone_tags(origin) if origin else []):
                for room in zone_rooms(zone):
                    candidates[room.id] = room
            dest_rooms = list(candidates.values())
        elif targeting == 'remote':
            room = _room_of(target)
            dest_rooms = [room] if room is not None else []
        else:  # 'room' — local, no remote leg
            dest_rooms = []

        if targeting in ('remote', 'zone'):
            # Permission gate (#4/#5): a destination may lock out remote
            # reach; denied rooms are dropped entirely (no veto needed).
            allowed = [r for r in dest_rooms
                       if check_lock(r, LockType.REACH, actor)]
            action = Action(
                actor=actor, target=target, action_type=action_type,
                chain=remote_chain(lambda a: a.extra.get('remote_rooms') or []),
                tags={'scripted'},
                extra={'message': message, 'remote_rooms': allowed},
            )
            action.add_message('remote', message, success_only=True)
        else:  # 'room' — local, but propagated (wards apply)
            action = Action(
                actor=actor, target=target, action_type=action_type,
                tags={'scripted'}, extra={'message': message},
            )
            action.add_message('room', message, success_only=True)

        await propagate(action)
