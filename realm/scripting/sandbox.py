"""
Sandboxed script execution for REALM.

Provides safe execution of user-defined scripts with:
- Per-script resource limits (CPU time, function calls, output size)
- A process-wide recursion limit, set once at boot from config
  (see set_interpreter_recursion_limit — it is NOT per-script)
- Restricted built-ins (no file I/O, no imports, no exec/eval)
- Safe globals with game-specific functions

Security model:
- Scripts run in a restricted namespace with only safe functions
- AST validation prevents dangerous constructs
- Resource limits prevent DoS attacks
"""

from __future__ import annotations

import asyncio
import ast
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from realm.core.safe_eval import (
    SafeAstValidator,
    validate_code,
)

if TYPE_CHECKING:
    from realm.core.objects import GameObject


class ScriptError(Exception):
    """Base exception for script execution errors."""
    pass


class ScriptTimeout(ScriptError):
    """Script exceeded time limit."""
    pass


class ScriptRecursionError(ScriptError):
    """Script exceeded recursion limit."""
    pass


class ScriptFunctionLimitError(ScriptError):
    """Script exceeded function call limit."""
    pass


class ScriptSecurityError(ScriptError):
    """Script attempted forbidden operation."""
    pass


class _ScriptKill(BaseException):
    """A resource-limit kill that sandboxed code cannot catch.

    Derives from ``BaseException`` (not ``Exception``), so a script's
    ``except Exception`` can never swallow it — and the validator forbids
    the catch-all handlers (``except:`` / ``except BaseException``) that
    could. It is raised inside ``exec`` by the watchdog and the per-call
    budget, and translated back to its public ``ScriptError`` flavour at the
    ``execute()`` boundary, so trusted callers still catch a normal
    ``ScriptTimeout`` / ``ScriptFunctionLimitError``.

    Why it must be uncatchable: the watchdog is a ``sys.settrace`` tracer
    that raises, and CPython DISABLES a trace function that raises. So a
    script that catches the first kill (``try: while True: pass; except
    Exception: while True: pass``) runs the rest of its body with no
    watchdog at all — pinning an uninterruptible executor thread. Making the
    kill uncatchable closes that hole.
    """

    def __init__(self, public: ScriptError):
        super().__init__(str(public))
        self.public = public
    pass


# Validation rules live in realm.core.safe_eval — the one engine shared
# with locks and strategy conditions. Re-exported here for compatibility.
ASTValidator = SafeAstValidator

# Safe built-ins that scripts can use
SAFE_BUILTINS = {
    # Types
    'True': True,
    'False': False,
    'None': None,
    'int': int,
    'float': float,
    'str': str,
    'bool': bool,
    'list': list,
    'dict': dict,
    'set': set,
    'tuple': tuple,
    # Functions
    'len': len,
    'range': range,
    'enumerate': enumerate,
    'zip': zip,
    'map': map,
    'filter': filter,
    'sorted': sorted,
    'reversed': reversed,
    'sum': sum,
    'min': min,
    'max': max,
    'abs': abs,
    'round': round,
    'pow': pow,
    'divmod': divmod,
    'all': all,
    'any': any,
    'repr': repr,
    'format': format,
    'chr': chr,
    'ord': ord,
    'hex': hex,
    'bin': bin,
    'oct': oct,
    'slice': slice,
    'print': lambda *args, **kwargs: None,  # Silently ignore prints
}


#: Floor for the interpreter recursion limit. The engine's own main thread
#: (asyncio + dispatcher + propagation) runs far deeper than a script does;
#: anything below this bricks the server, not just softcode.
MIN_RECURSION_LIMIT = 100
#: Ceiling — CPython segfaults rather than raising if the limit outruns the
#: real C stack. Boot-time validation is the place to catch that.
MAX_RECURSION_LIMIT = 100_000

DEFAULT_RECURSION_LIMIT = 1000  # CPython's own default


def set_interpreter_recursion_limit(limit: int = DEFAULT_RECURSION_LIMIT) -> None:
    """Set the **process-wide** Python recursion limit (a game setting).

    This is NOT a per-script limit and must never be called per execution.
    ``sys.setrecursionlimit`` is interpreter-global: it applies to *every*
    thread. Scripts run on worker threads (``execute_async`` ->
    ``run_in_executor``), so lowering it around a single script also caps
    the main thread mid-flight — which raised RecursionError in unrelated
    engine code (see BACKLOG, 2026-07-17). Hence: set once, at boot, from
    config, alongside the other process-wide ambient settings.

    What still bounds a runaway script: this limit (a RecursionError inside
    ``exec`` is converted to ScriptRecursionError), plus the per-script
    call-count and time budgets in :class:`ScriptLimits`.

    Raises ValueError on a bad value — at boot, not mid-render.
    """
    import sys

    if not isinstance(limit, int) or isinstance(limit, bool):
        raise ValueError(f"recursion_limit must be an int, got {limit!r}")
    if not (MIN_RECURSION_LIMIT <= limit <= MAX_RECURSION_LIMIT):
        raise ValueError(
            f"recursion_limit must be between {MIN_RECURSION_LIMIT} and "
            f"{MAX_RECURSION_LIMIT} (got {limit}); it is process-wide and the "
            f"engine's own call stack lives under it."
        )
    sys.setrecursionlimit(limit)


@dataclass
class ScriptLimits:
    """Per-script resource limits.

    These are per-execution and thread-safe. ``max_recursion_depth`` is a
    per-script nesting ceiling counted by the watchdog's call/return trace
    events (so it needs the watchdog installed, which any looping or
    ``try``-containing script gets). It fires at a shallow depth where the
    tracer still has stack to run — unlike the process-wide
    :func:`set_interpreter_recursion_limit`, whose RecursionError a script
    can catch and re-trigger forever near the ceiling, where the tracer can
    no longer be called. Kept well below the process limit for that reason.
    """

    max_time_ms: int = 1500  # Maximum execution time
    max_function_calls: int = 25000  # Maximum function invocations
    max_output_chars: int = 10000  # Maximum output length
    max_recursion_depth: int = 200  # Per-script frame-nesting ceiling


@dataclass
class ScriptContext:
    """Context for script execution."""

    enactor: GameObject | None = None  # %# - who triggered
    executor: GameObject | None = None  # %! - the scripted object
    location: GameObject | None = None  # %l - where it happened
    captures: list[str] = field(default_factory=list)  # %0-%9 - pattern captures
    extra: dict[str, Any] = field(default_factory=dict)  # Additional context


class ScriptSandbox:
    """
    Sandboxed environment for executing user scripts.

    Provides:
    - AST validation to prevent dangerous constructs
    - Resource limits (time, recursion, function calls)
    - Safe globals with game-specific functions
    - Substitution code expansion (%n, %#, etc.)
    """

    def __init__(self, limits: ScriptLimits | None = None):
        self.limits = limits or ScriptLimits()
        self._call_count = 0
        self._start_time = 0.0
        self._output: list[str] = []

    def validate(self, code: str) -> list[str]:
        """
        Validate script code without executing it.

        Returns list of error messages (empty if valid).
        """
        return validate_code(code, mode='exec')

    def expand_substitutions(self, code: str, ctx: ScriptContext) -> str:
        """
        Expand substitution codes in the script.

        Substitutions (from plan.md):
        - %# - Enactor ID (who triggered)
        - %! - Executor ID (this object)
        - %n - Enactor's name
        - %l - Enactor's location ID
        - %0-%9 - Captured wildcard groups
        """
        replacements = {
            '%#': ctx.enactor.id if ctx.enactor else '',
            '%!': ctx.executor.id if ctx.executor else '',
            '%n': ctx.enactor.name if ctx.enactor else '',
            '%l': ctx.location.id if ctx.location else '',
        }

        # Add captures %0-%9
        for i in range(10):
            replacements[f'%{i}'] = ctx.captures[i] if i < len(ctx.captures) else ''

        # Perform replacements
        result = code
        for pattern, replacement in replacements.items():
            result = result.replace(pattern, str(replacement))

        return result

    def _make_safe_globals(self, ctx: ScriptContext) -> dict[str, Any]:
        """Create the safe globals namespace for script execution."""
        globals_dict = dict(SAFE_BUILTINS)

        # Add context variables
        globals_dict['enactor'] = ctx.enactor
        globals_dict['executor'] = ctx.executor
        globals_dict['location'] = ctx.location
        globals_dict['me'] = ctx.executor
        globals_dict['here'] = ctx.location

        # Add captures as numbered variables
        for i, capture in enumerate(ctx.captures):
            globals_dict[f'arg{i}'] = capture

        # Add any extra context
        globals_dict.update(ctx.extra)

        return globals_dict

    # Node types that can spin without ever calling a function: a bare
    # loop, or a comprehension/generator over a large/endless iterable.
    _LOOP_NODES = (ast.While, ast.For, ast.AsyncFor,
                   ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)

    @classmethod
    def _has_loop(cls, code: str) -> bool:
        """Could this script iterate without calling anything?

        The call/time budget is checked inside :meth:`_wrap_function`, so a
        script that spins in a call-free loop (``while True: pass``) is
        never checked and pins its thread. We install a line-level watchdog
        to catch that — but only for scripts that can actually loop, so the
        common case (a guard chain, an inline ``[[...]]`` read) pays
        nothing.
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return True  # let compile() report it; assume the worst meanwhile
        return any(isinstance(n, cls._LOOP_NODES) for n in ast.walk(tree))

    @classmethod
    def _needs_watchdog(cls, code: str) -> bool:
        """Install the watchdog for anything that can run unboundedly.

        A loop is the obvious case. A ``try`` is the subtle one: a script can
        catch its own ``RecursionError`` and re-recurse forever with no loop
        node at all, and post-``except`` code runs after the first (now
        uncatchable) kill would otherwise have fired. So watch any script that
        loops OR contains a ``try``. Straight-line, try-free scripts (the vast
        majority of one-line softcode) still pay nothing.
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return True
        return any(isinstance(n, (*cls._LOOP_NODES, ast.Try))
                   for n in ast.walk(tree))

    def _make_watchdog(self) -> Callable:
        """A line tracer that raises once the time budget is spent.

        Checked every 1024 line events (a cheap integer mask between
        ``time.time()`` calls), so a runaway loop dies in microseconds
        while a well-behaved loop barely notices. ``sys`` is not in the
        sandbox namespace, so a script cannot clear its own trace.
        """
        deadline = self._start_time + self.limits.max_time_ms / 1000.0
        limit_ms = self.limits.max_time_ms
        clock = time.time
        # Kill runaway nesting a safe margin below the process recursion
        # limit, so the tracer still has stack to fire (near the real limit
        # it cannot be called — which is how catch-and-re-recurse evades the
        # time check). ``d`` is live nesting depth; call/return balance even
        # under exception unwinding.
        max_depth = min(self.limits.max_recursion_depth,
                        sys.getrecursionlimit() - 50)
        state = {"n": 0, "d": 0}

        def _trace(frame, event, arg):
            if event == 'call':
                state["d"] += 1
                if state["d"] > max_depth:
                    raise _ScriptKill(ScriptRecursionError(
                        f"Script exceeded recursion depth ({max_depth})"))
            elif event == 'return':
                state["d"] -= 1
            state["n"] += 1
            if (state["n"] & 0x3FF) == 0 and clock() > deadline:
                raise _ScriptKill(ScriptTimeout(
                    f"Script exceeded time limit ({limit_ms}ms)"))
            return _trace

        return _trace

    def _wrap_function(self, func: Callable) -> Callable:
        """Wrap a function to track call count and check limits."""
        def wrapped(*args, **kwargs):
            self._call_count += 1
            if self._call_count > self.limits.max_function_calls:
                raise _ScriptKill(ScriptFunctionLimitError(
                    f"Exceeded function call limit ({self.limits.max_function_calls})"
                ))
            # Check time limit
            elapsed = (time.time() - self._start_time) * 1000
            if elapsed > self.limits.max_time_ms:
                raise _ScriptKill(ScriptTimeout(
                    f"Script exceeded time limit ({self.limits.max_time_ms}ms)"))
            return func(*args, **kwargs)
        return wrapped

    def execute(
        self,
        code: str,
        ctx: ScriptContext,
        *,
        validate: bool = True,
        functions: dict[str, Any] | None = None,
    ) -> tuple[Any, list[str]]:
        """
        Execute script code synchronously.

        Args:
            code: The script code to execute
            ctx: Script context with enactor, executor, etc.
            validate: Whether to validate the AST first
            functions: Extra names injected into the script namespace
                (typically ``ScriptFunctions.to_dict()``). Callables are
                wrapped so they count against the call/time limits.

        Returns:
            Tuple of (result, output_lines)

        Raises:
            ScriptError: On validation or execution failure
        """
        # Reset state
        self._call_count = 0
        self._start_time = time.time()
        self._output = []

        # Expand substitutions
        expanded_code = self.expand_substitutions(code, ctx)

        # Validate if requested
        if validate:
            errors = self.validate(expanded_code)
            if errors:
                raise ScriptSecurityError("Validation failed: " + "; ".join(errors))

        # Compile the code
        try:
            compiled = compile(expanded_code, '<script>', 'exec')
        except SyntaxError as e:
            raise ScriptError(f"Syntax error: {e.msg} at line {e.lineno}") from e

        # Create safe globals
        safe_globals = self._make_safe_globals(ctx)

        # Inject provided game functions, limit-wrapped
        if functions:
            for fn_name, fn_value in functions.items():
                if callable(fn_value):
                    safe_globals[fn_name] = self._wrap_function(fn_value)
                else:
                    safe_globals[fn_name] = fn_value

        # Custom output function
        def script_output(*args: Any, sep: str = ' ', end: str = '\n') -> None:
            text = sep.join(str(a) for a in args) + end
            total_len = sum(len(o) for o in self._output) + len(text)
            if total_len > self.limits.max_output_chars:
                raise ScriptError(f"Output exceeded limit ({self.limits.max_output_chars} chars)")
            self._output.append(text)

        safe_globals['output'] = script_output
        safe_globals['say'] = lambda msg: script_output(f"say {msg}")
        safe_globals['pose'] = lambda msg: script_output(f"pose {msg}")
        safe_globals['move'] = lambda direction: script_output(f"move {direction}")
        safe_globals['trigger'] = lambda spec: script_output(f"trigger {spec}")
        # Generic escape hatch: emit any script command line (get/drop/
        # give/open/close/wait/...) — same actuator set as simple scripts.
        safe_globals['cmd'] = lambda line: script_output(str(line))

        # A line-level watchdog catches call-free infinite loops, which the
        # per-call budget in _wrap_function cannot see. Installed only when
        # the script can actually loop, so loop-free scripts pay nothing.
        watchdog = self._needs_watchdog(expanded_code)
        old_trace = sys.gettrace() if watchdog else None
        if watchdog:
            sys.settrace(self._make_watchdog())

        try:
            # ONE namespace, not two. With separate globals/locals a script
            # runs like a *class body*: assignments land in locals, but every
            # nested scope (lambda, generator expression — and, before PEP 709,
            # comprehensions too) compiles its free names to LOAD_GLOBAL and so
            # cannot see them. That made `n = {...}; sorted(x, key=lambda k:
            # n[k])` raise NameError on a name defined one statement earlier,
            # and made list comprehensions behave differently on 3.11 vs 3.12+.
            # Sharing one dict makes a script behave like module scope: uniform
            # across versions, and lambdas/genexprs can finally read what the
            # script just computed.
            #
            # No recursion-limit fiddling here: it is process-wide state, set
            # once at boot (set_interpreter_recursion_limit). Doing it per
            # execution capped every other thread too. A runaway script still
            # trips the interpreter limit and surfaces as ScriptRecursionError.
            exec(compiled, safe_globals, safe_globals)

        except _ScriptKill as kill:
            # A resource-limit kill from inside the sandbox. Re-raise its
            # public flavour so callers' ``except ScriptError`` still works.
            raise kill.public from None
        except RecursionError as e:
            raise ScriptRecursionError(
                f"Exceeded recursion limit ({sys.getrecursionlimit()})"
            ) from e
        except ScriptError:
            raise
        except Exception as e:
            raise ScriptError(f"Execution error: {type(e).__name__}: {e}") from e
        finally:
            if watchdog:
                sys.settrace(old_trace)

        # Check time limit one final time
        elapsed = (time.time() - self._start_time) * 1000
        if elapsed > self.limits.max_time_ms:
            raise ScriptTimeout(f"Script exceeded time limit ({self.limits.max_time_ms}ms)")

        # Return result and output. `result` now lives in the shared namespace
        # (see the single-dict exec above); safe_globals is built fresh per
        # execution, so scripts cannot leak state into each other through it.
        result = safe_globals.get('result', None)
        return result, self._output

    async def execute_async(
        self,
        code: str,
        ctx: ScriptContext,
        *,
        validate: bool = True,
        functions: dict[str, Any] | None = None,
    ) -> tuple[Any, list[str]]:
        """
        Execute script code asynchronously.

        Runs the script in a thread pool to avoid blocking the event loop.
        Injected functions therefore run off-loop: they must only read game
        state or queue work (see ScriptFunctions.command_queue), never touch
        sessions or the loop directly.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.execute(code, ctx, validate=validate, functions=functions)
        )


class SimpleScriptRunner:
    """
    Simple script runner for basic action scripts.

    Handles the common case of scripts that are just commands to execute,
    like "say Hello, %n!" - no Python execution needed.
    """

    # A simple script is a single game command; anything else is Python.
    SIMPLE_COMMAND_PREFIXES = (
        'say ', 'pose ', 'whisper ', 'emit ', '@emit ',
        'move ', 'go ', 'trigger ', '@tr ',
        'get ', 'take ', 'drop ', 'give ', 'open ', 'close ', 'wait ',
    )
    SIMPLE_COMMAND_TOKENS = (':', ';', '\\')

    @classmethod
    def is_simple_script(cls, code: str) -> bool:
        """
        Check if this is a simple command script (no Python).

        Simple scripts are single lines starting with a script command
        (say/pose/whisper/emit or a token shortcut). Everything else runs
        through the sandbox — where say()/pose() exist as functions, so
        Python one-liners like ``say(f"...")`` still work.
        """
        lines = code.strip().split('\n')
        if len(lines) != 1:
            return False

        line = lines[0].strip()
        return (
            line.lower().startswith(cls.SIMPLE_COMMAND_PREFIXES)
            or line.startswith(cls.SIMPLE_COMMAND_TOKENS)
        )

    @staticmethod
    def expand_simple(code: str, ctx: ScriptContext) -> str:
        """Expand substitutions in a simple script."""
        result = code

        # Basic substitutions
        if ctx.enactor:
            result = result.replace('%#', ctx.enactor.id)
            result = result.replace('%n', ctx.enactor.name)

        if ctx.executor:
            result = result.replace('%!', ctx.executor.id)

        if ctx.location:
            result = result.replace('%l', ctx.location.id)

        # Captures
        for i, capture in enumerate(ctx.captures):
            result = result.replace(f'%{i}', capture)

        return result
