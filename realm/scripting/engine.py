"""
Script execution engine for REALM.

Ties together:
- TriggerManager: finding matching triggers
- ScriptSandbox: safe execution
- ScriptFrame: built-in functions injected into scripts
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

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from realm.core.action_tags import SCRIPTED
from realm.core.action_types import ActionType
from realm.core.propagation import Action
from realm.scripting.functions import ScriptFrame
from realm.scripting.sandbox import (
    ScriptContext,
    ScriptError,
    ScriptSandbox,
    expand_substitutions,
)
from realm.scripting.triggers import (
    TriggerManager,
    TriggerMatch,
    get_search_objects,
    unknown_verb,
)
from realm.scripting.verbs import installed as installed_verbs

if TYPE_CHECKING:
    from realm.commands.dispatcher import CommandContext
    from realm.core.objects import GameObject
    from realm.gateway.session import Session


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
    ActionType.SPEECH,
    ActionType.SHOUT,
    ActionType.OOC,
    ActionType.EMIT,
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
        # Feature-owned softcode-queued world ops: kind -> async
        # (engine, frame, obj, payload). Filled by FeatureSet.install_runtime.
        self.queue_kinds: dict[str, Any] = {}
        self.dispatcher = None  # set by GameServer; enables force()
        self._depth = 0
        # One-shot scheduled commands, keyed by a handle id so softcode can
        # cancel a pending wait (LDMud call_out/remove_call_out; MOO
        # fork/kill_task). Each wait is its OWN asyncio task sleeping the
        # exact duration — a wait(0.15, ...) fires at 0.15s, not quantized to
        # the heartbeat (see docs/design/time-and-beats.md, decision 2).
        # value = (fire_at_monotonic, executor, command, timer_task).
        # In-memory only — like MUSH @waits, pending waits don't survive a
        # reboot; shutdown_waits() cancels the tasks on stop/reboot.
        self._waits: dict[
            str, tuple[float, GameObject, str, asyncio.Task[None] | None]] = {}
        # Virtual-clock mode: when True (the Simulator sets it), waits do NOT
        # spawn real timers — they wait for an explicit tick_waits() pump, so
        # tests advance time deterministically. Production leaves it False and
        # each wait fires on its own exact asyncio timer.
        self.defer_waits: bool = False

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

            # Typing an object's $-command is deliberate interaction — the
            # enactor consents to what the object does to them (a portal's
            # "enter portal" may relocate them).
            await self._execute_trigger(match, ctx.player, session=ctx.session,
                                        enactor_consent=True)
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
                await self.handle_speech(action.actor, str(message), room,
                                         action=action)

        # ON_<EVENT> attribute triggers
        await self._fire_event_triggers(action, room)

    async def handle_speech(
        self,
        speaker: GameObject | None,
        speech: str,
        location: GameObject,
        *,
        action: Action | None = None,
    ) -> None:
        """
        Run ^listen triggers for speech heard at a location.

        Args:
            speaker: Who spoke (None for sourceless emits)
            speech: What was said
            location: Where it was heard
            action: The speech Action, when there is one — binds the event
                namespace (``target``, ``adata('message')``, ...) so a
                listener can tell a whisper's addressee from a bystander.
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
            await self._execute_trigger(match, speaker, location=location,
                                        action=action)

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
        if obj.is_halted:
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
        restricted READ-ONLY namespace (``ScriptFrame.readonly_dict`` —
        reads, dice, formatting) plus the check verbs, so it cannot mutate
        or queue world state. Reacting to an action belongs in ``on_react``
        / ``ON_<EVENT>`` triggers, which run after.

        No shared-depth guard here: a check hook has no way to propagate
        (its namespace has no act/emit/force/damage), so it can't recurse —
        and a ward must not silently *fail open* just because an unrelated
        script chain spent the depth budget. The sandbox's own call/time
        limits bound it.
        """
        if obj.is_halted:
            return
        code = obj.db.get('on_check')
        if not isinstance(code, str) or not code.strip():
            return
        await self.run_check_code(obj, action, code)

    async def run_check_code(self, obj: GameObject, action: Action,
                             code: str, *,
                             params: dict | None = None) -> None:
        """
        Run ``code`` as a decision-pass ward for ``obj`` — the execution
        half of :meth:`run_check_hook`, split out so a scripted behavior
        can run a ``behavior_def``'s ``on_check`` with the same restricted
        namespace and the same fail-closed reporting. ``params`` binds a
        ``param(key, default)`` reader for per-attachment configuration.
        """
        if obj.is_halted:
            return
        from realm.scripting.namespace import build_namespace
        from realm.scripting.sandbox import ScriptContext

        ctx = ScriptContext(enactor=action.actor, executor=obj,
                            location=obj.location)
        namespace, _frame = build_namespace(
            'check', executor=obj, enactor=action.actor, location=obj.location,
            store=self._persistence, action=action, params=params)
        try:
            await self.sandbox.execute_async(code, ctx, functions=namespace)
        except ScriptError as exc:
            self._ward_failed(obj, action, code, exc, set(namespace))

    async def run_behavior_script(self, obj: GameObject, code: str, *,
                                  action: Action | None = None,
                                  enactor: GameObject | None = None,
                                  params: dict | None = None) -> None:
        """
        Run ``code`` as ``obj`` with the FULL script namespace — the
        reaction/tick half of a scripted behavior. With an ``action``, the
        event namespace (``atype``/``adata``/``has_atag``/``target``) binds
        to it, so a ``behavior_def``'s ``on_react`` observes the action the
        way an ``ON_<EVENT>`` attribute does; without one (a tick), those
        names are bound but empty. ``params`` binds ``param(key, default)``.
        Depth-guarded and halt-honoring like every trigger path.
        """
        if obj.is_halted or not isinstance(code, str) or not code.strip():
            return
        extra = None
        if params is not None:
            bound = dict(params)
            extra = {'param':
                     lambda key, default=None: bound.get(str(key), default)}
        match = TriggerMatch(
            trigger=None,  # type: ignore[arg-type]
            captures=[],
            full_match='behavior',
            obj=obj,
            action=code,
        )
        if enactor is None and action is not None:
            enactor = action.actor
        await self._execute_trigger(match, enactor or obj,
                                    location=obj.location, action=action,
                                    extra_namespace=extra)

    @staticmethod
    def _not_readonly_hint(exc: Exception) -> str:
        """When a ward died calling a real function it may not use there,
        say why: ``on_check`` sees only read-only functions."""
        import re

        from realm.scripting.registry import registered
        match = re.search(r"name '(\w+)' is not defined", str(exc))
        if match is None:
            return ""
        entry = registered().get(match.group(1))
        if entry is None or entry.readonly:
            return ""
        return (f" ({entry.name}() exists but changes the world, so on_check "
                f"cannot call it; do that in an ON_<EVENT> reaction instead)")

    @staticmethod
    def _ward_can_deny(code: str, known: set[str]) -> bool:
        """Could this ward have said no — i.e. must its failure fail CLOSED?

        A ward that can deny must not fall open when it errors: "the ward
        errored" and "the ward allowed it" have to be different outcomes, or
        a typo silently unlocks the vault. A ward that only ``mod()``s or
        ``set_adata()``s cannot open a hole by failing — an armour
        calculation that raises must not veto the swing — so those stay open
        (loudly).

        A ward is treated as *provably advisory* only when it parses AND
        every function it calls is a name it could actually have (``known``
        = the check namespace + safe builtins) AND none of them is
        ``block``. Anything else guards, because:

        - ``block(...)``            -> denies outright.
        - ``blok(...)``             -> an UNKNOWN callable. This is the case
          that matters most: a misspelled ``block`` is the likeliest ward
          bug there is, and it is indistinguishable from any other typo. If
          we cannot name what it calls, we cannot claim it was advisory.
        - unparseable               -> cannot tell what it guards at all.
        """
        import ast
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return True
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                name = node.func.id
                if name == 'block' or name not in known:
                    return True
        return False

    def _ward_failed(
        self, obj: GameObject, action: Action, code: str, exc: Exception,
        namespace_names: set[str],
    ) -> None:
        """A ward raised. Never silent; fail CLOSED if it could have denied.

        This restores the invariant this method's own docstring states — a
        ward must not silently fail open. Before, any error (a typo'd name,
        a missing paren, a stray ZeroDivision) was logged at warning level
        and the action proceeded: every veto surface in the game — cursed
        items, landmines, clearance gates, escrow, the jail door — quietly
        stopped protecting, indistinguishably from having allowed it.
        """
        hint = self._not_readonly_hint(exc)
        logger.error("on_check FAILED on %s (%s): %s%s", obj.name, obj.id, exc, hint)
        # Loud: the builder who owns the broken ward hears about it.
        owner = obj.owner if obj.owner is not None else None
        if owner is not None:
            owner.msg(f"Ward error on {obj.name}: {exc}{hint}")
        from realm.scripting.sandbox import SAFE_BUILTINS
        known = namespace_names | set(SAFE_BUILTINS)
        if self._ward_can_deny(code, known):
            action.block(f"{obj.name} is warded, but the ward is malfunctioning.")

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

        if executor.is_halted or self._depth >= self.MAX_SCRIPT_DEPTH:
            return None, "halted or too deep"

        script_ctx = ScriptContext(
            enactor=enactor or executor,
            executor=executor,
            location=executor.location,
        )
        from realm.scripting.namespace import build_namespace

        namespace, functions = build_namespace(
            'script', executor=executor, enactor=enactor or executor,
            location=executor.location, store=self._persistence)
        self._depth += 1
        try:
            try:
                result, output = await self.sandbox.execute_async(
                    code, script_ctx, functions=namespace)
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
        from realm.core.eventdefs import installed as installed_events
        event_type = installed_events().hook_for(action.action_type)
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
            if obj.is_halted:
                continue
            # Consent: the actor deliberately walked into THIS exit, and its
            # ON_FAIL is now running — the one witnessed-event case where
            # relocating the enactor is consensual (the portal pattern).
            # Every other witness (a bystander's ON_ENTER, a room's ON_SAY)
            # gets no such grant.
            consent = (action.action_type == ActionType.ON_FAIL
                       and obj is action.extra.get("exit"))
            for trigger in self.trigger_manager.get_event_triggers(obj, event_type):
                match = TriggerMatch(
                    trigger=trigger,  # type: ignore[arg-type]
                    captures=[],
                    full_match=action.action_type,
                    obj=obj,
                    action=trigger.action,
                )
                await self._execute_trigger(match, action.actor, location=room,
                                            enactor_consent=consent,
                                            action=action)

        # The mover's own hook: ON_ARRIVE fires on the actor when it enters
        # somewhere new (plan.md: "this object arrives somewhere new").
        if event_type == 'ENTER' and action.actor is not None:
            actor = action.actor
            if not actor.is_halted:
                for trigger in self.trigger_manager.get_event_triggers(actor, 'ARRIVE'):
                    match = TriggerMatch(
                        trigger=trigger,  # type: ignore[arg-type]
                        captures=[],
                        full_match=action.action_type,
                        obj=actor,
                        action=trigger.action,
                    )
                    await self._execute_trigger(match, actor, location=room,
                                                action=action)

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
        if target.contents or target.is_room:
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
        enactor_consent: bool = False,
        action: Action | None = None,
        extra_namespace: dict | None = None,
    ) -> None:
        """Execute a matched trigger, depth-guarded.

        ``action`` is the propagated Action this trigger is observing, when
        there is one (``ON_<EVENT>``, ``^listen``). It binds the event
        namespace — ``target``, ``adata(...)``, ``atype``, ``has_atag`` —
        so the script can see *what happened*, not just who did it. A
        ``$``-command or ``@tr`` has no action behind it and passes None,
        leaving those names unbound.

        ``enactor_consent`` marks the two paths where the enactor
        deliberately invoked THIS object ($-command typed at it; the exit
        they traversed firing its ON_FAIL) — granting scripts the right to
        relocate the enactor. Passive paths (^listen, witnessed ON_<EVENT>)
        must leave it False; overhearing someone is not a capability to
        move them."""
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

            missing = unknown_verb(action_code)
            if missing is not None:
                logger.warning(f"Script on {match.obj.name}: {missing}")
            elif installed_verbs().is_command_line(action_code):
                # One command line: substitute %-codes and run it as a verb.
                expanded = expand_substitutions(action_code, script_ctx)
                await self._run_script_command(match.obj, expanded)
            else:
                # Full Python script execution with game functions injected.
                # Event names are always bound — empty when there is no
                # action (@tr, a $-command), so a hook reading adata() does
                # not die of NameError when a builder @tr's it.
                from realm.scripting.namespace import build_namespace
                namespace, functions = build_namespace(
                    'script', executor=match.obj, enactor=enactor,
                    location=location, store=self._persistence, action=action,
                    enactor_consent=enactor_consent, extra=extra_namespace)
                try:
                    _result, output = await self.sandbox.execute_async(
                        action_code,
                        script_ctx,
                        functions=namespace,
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
        """Run one script command line as the scripted object.

        The installed script verbs (``realm.scripting.verbs``) decide what a
        line means; each verb's handler goes through the same core the
        player command uses, so locks, closed doors and wards apply. A line
        that names no installed verb is logged and dropped.
        """
        from realm.scripting.verbs import installed
        verbs = installed()
        found = verbs.match(command)
        if found is None:
            if command.strip():
                logger.warning(
                    f"Script on {executor.name} produced {command.strip()!r}, which is "
                    f"not a script verb in this world. Known: {', '.join(verbs.names())}")
            return
        verb, rest = found
        await verb.handler(self, executor, rest)

    # --- One-shot waits (fired from the server heartbeat) ---

    def schedule_wait(self, executor: GameObject, seconds: float, command: str,
                      *, wait_id: str | None = None) -> str:
        """Schedule a script command to run *exactly* ``seconds`` from now.

        Each wait is its own asyncio task (LDMud ``call_out`` / MOO ``fork``),
        so precision is the event loop's, not the heartbeat's — a 0.15s fuse
        fires at 0.15s. Returns the handle id; pass ``wait_id`` to register
        under a caller-chosen id (so ``wait()`` can hand the id back before
        the op drains). In-memory only — pending waits don't survive a reboot.
        """
        import time as _time
        import uuid
        seconds = max(0.0, min(float(seconds), 3600.0))
        wait_id = wait_id or uuid.uuid4().hex
        task = (None if self.defer_waits
                else asyncio.ensure_future(self._wait_timer(wait_id, seconds)))
        self._waits[wait_id] = (_time.monotonic() + seconds, executor,
                                str(command), task)
        return wait_id

    def cancel_wait(self, wait_id: str, *, by: GameObject | None = None) -> bool:
        """Cancel a pending wait by its handle. When ``by`` is given, only a
        controller of the wait's executor may cancel it (the id alone is not
        authority — it may have been stored in a readable attr)."""
        entry = self._waits.get(wait_id)
        if entry is None:
            return False
        if by is not None:
            from realm.permissions.locks import controls
            if not controls(by, entry[1]):
                return False
        entry = self._waits.pop(wait_id, None)
        if entry is None:
            return False
        if entry[3] is not None:
            entry[3].cancel()
        return True

    async def _wait_timer(self, wait_id: str, seconds: float) -> None:
        """The per-wait timer: sleep the exact duration, then deliver."""
        try:
            if seconds > 0:
                await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            return
        await self._deliver_wait(wait_id)

    async def _deliver_wait(self, wait_id: str) -> None:
        """Run a wait's command once. Atomically claims the entry (pop), so a
        wait can't fire twice even if its timer and ``tick_waits`` race."""
        entry = self._waits.pop(wait_id, None)
        if entry is None:
            return
        _at, executor, command, _task = entry
        if executor.is_halted:
            return
        await self._run_script_command(executor, command)

    async def tick_waits(self) -> None:
        """Fire any waits already due *now*, synchronously.

        Production waits fire on their own exact timers; this is the
        deterministic drive for tests (and a belt-and-suspenders catch-up if a
        timer was starved). Only past-deadline waits fire — future ones wait
        for their timer.
        """
        if not self._waits:
            return
        import time as _time
        now = _time.monotonic()
        due = [wid for wid, entry in self._waits.items() if entry[0] <= now]
        for wid in due:
            entry = self._waits.get(wid)
            if entry is not None and entry[3] is not None:
                entry[3].cancel()      # stop its timer; we deliver now
            await self._deliver_wait(wid)

    def shutdown_waits(self) -> None:
        """Cancel every pending wait timer (stop/reboot — waits are in-memory
        and don't survive it). Idempotent."""
        for _at, _executor, _command, task in list(self._waits.values()):
            if task is not None:
                task.cancel()
        self._waits.clear()

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

    @staticmethod
    def _installed_queue_kind(kind: str):
        """A queue kind from the installed feature set: the live world's, or
        the CLASSIC default when an engine runs with no world (tests, tools)."""
        from realm.features import ensure_registries, installed
        ensure_registries()
        features = installed()
        if features is None:
            return None
        for feature in features.features:
            if kind in feature.queue_kinds:
                return feature.queue_kinds[kind]
        return None

    @property
    def store(self):
        """The world store this engine reads and saves through."""
        return self._persistence

    async def _deliver_queued(self, functions: ScriptFrame) -> None:
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
                # destroy_obj() already ran check_destroy; the object may
                # have changed since (tagged safe later in the same script).
                from realm.core import ops
                try:
                    await ops.destroy(functions.executor, obj, self._persistence)
                except ops.OpError as refused:
                    logger.info(f"Softcode destroy of {obj.name} ({obj.id}) refused: "
                                f"{refused.reason}")
            elif kind == 'wait':
                seconds, command, wait_id = message
                self.schedule_wait(obj, seconds, command, wait_id=wait_id)
            elif kind == 'cancel_wait':
                self.cancel_wait(str(message), by=functions.executor)
            elif kind == 'prompt':
                text, callback, executor_id, persistent = message
                self._install_softcode_prompt(
                    obj, text, callback, executor_id, persistent)
            elif kind == 'force':
                if self.dispatcher is not None:
                    from realm.server.puppet import force_command
                    await force_command(self.dispatcher, obj, message)
            elif kind == 'act':
                msg, targeting, action_type, payload, act_tags = message
                await self._propagate_act(
                    functions.executor, obj, msg, targeting, action_type,
                    payload, act_tags)
            elif kind == 'move_to':
                if self._persistence is not None:
                    from realm.core.movement import move_to
                    dest_id, extra_tags, force = message
                    dest = self._persistence.get_cached(dest_id)
                    if dest is not None:
                        # mover = the scripting object: if IT controls the
                        # destination, the dest locks yield (Penn dest_ok).
                        await move_to(obj, dest, extra_tags=extra_tags,
                                      force=force, mover=functions.executor)
                    else:
                        logger.warning(
                            f"Scripted move_to of {obj.name}: destination "
                            f"{dest_id} not in cache; move dropped")
            else:
                handler = self.queue_kinds.get(kind) or self._installed_queue_kind(kind)
                if handler is not None:
                    await handler(self, functions, obj, message)
                else:
                    logger.warning(
                        f"Softcode queued {kind!r} on {obj.name}, but no installed "
                        f"feature handles it; dropped")
        functions.command_queue.clear()

    async def _propagate_act(self, actor, target, message, targeting,
                             action_type, payload=None, act_tags=None):
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
                tags={SCRIPTED} | set(act_tags or ()),
                extra={**(payload or {}),
                       'message': message, 'remote_rooms': allowed},
            )
            action.add_message('remote', message, success_only=True)
        else:  # 'room' — local, but propagated (wards apply)
            action = Action(
                actor=actor, target=target, action_type=action_type,
                tags={SCRIPTED} | set(act_tags or ()),
                extra={**(payload or {}), 'message': message},
            )
            action.add_message('room', message, success_only=True)

        await propagate(action)
