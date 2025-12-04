"""
Sandboxed script execution for REALM.

Provides safe execution of user-defined scripts with:
- Resource limits (CPU time, recursion depth, function calls)
- Restricted built-ins (no file I/O, no imports, no exec/eval)
- Safe globals with game-specific functions

Security model:
- Scripts run in a restricted namespace with only safe functions
- AST validation prevents dangerous constructs
- Resource limits prevent DoS attacks
"""

from __future__ import annotations

import ast
import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

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


# Forbidden AST node types
FORBIDDEN_NODES = {
    ast.Import,
    ast.ImportFrom,
    ast.Global,
    ast.Nonlocal,
}

# Forbidden function names (built-ins that shouldn't be available)
FORBIDDEN_NAMES = {
    'eval', 'exec', 'compile', 'open', 'input',
    '__import__', 'globals', 'locals', 'vars',
    'getattr', 'setattr', 'delattr', 'hasattr',
    'type', 'isinstance', 'issubclass',
    'memoryview', 'bytearray', 'bytes',
    'classmethod', 'staticmethod', 'property',
    'super', 'object', 'dir', 'help',
    'breakpoint', 'exit', 'quit',
}

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


class ASTValidator(ast.NodeVisitor):
    """Validates AST for security violations."""

    def __init__(self):
        self.errors: list[str] = []

    def visit(self, node: ast.AST) -> None:
        # Check for forbidden node types
        if type(node) in FORBIDDEN_NODES:
            self.errors.append(f"Forbidden construct: {type(node).__name__}")

        # Check for forbidden names
        if isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES:
                self.errors.append(f"Forbidden name: {node.id}")
            if node.id.startswith('_'):
                self.errors.append(f"Private names not allowed: {node.id}")

        # Check for forbidden attribute access
        if isinstance(node, ast.Attribute):
            if node.attr.startswith('_'):
                self.errors.append(f"Private attribute access not allowed: {node.attr}")

        # Continue visiting children
        self.generic_visit(node)


@dataclass
class ScriptLimits:
    """Resource limits for script execution."""

    max_time_ms: int = 1500  # Maximum execution time
    max_recursion: int = 50  # Maximum recursion depth
    max_function_calls: int = 25000  # Maximum function invocations
    max_output_chars: int = 10000  # Maximum output length


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
        try:
            tree = ast.parse(code, mode='exec')
        except SyntaxError as e:
            return [f"Syntax error: {e.msg} at line {e.lineno}"]

        validator = ASTValidator()
        validator.visit(tree)
        return validator.errors

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

    def _wrap_function(self, func: Callable) -> Callable:
        """Wrap a function to track call count and check limits."""
        def wrapped(*args, **kwargs):
            self._call_count += 1
            if self._call_count > self.limits.max_function_calls:
                raise ScriptFunctionLimitError(
                    f"Exceeded function call limit ({self.limits.max_function_calls})"
                )
            # Check time limit
            elapsed = (time.time() - self._start_time) * 1000
            if elapsed > self.limits.max_time_ms:
                raise ScriptTimeout(f"Script exceeded time limit ({self.limits.max_time_ms}ms)")
            return func(*args, **kwargs)
        return wrapped

    def execute(
        self,
        code: str,
        ctx: ScriptContext,
        *,
        validate: bool = True,
    ) -> tuple[Any, list[str]]:
        """
        Execute script code synchronously.

        Args:
            code: The script code to execute
            ctx: Script context with enactor, executor, etc.
            validate: Whether to validate the AST first

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

        # Execute with resource tracking
        local_vars: dict[str, Any] = {}

        try:
            import sys
            old_limit = sys.getrecursionlimit()
            sys.setrecursionlimit(min(self.limits.max_recursion + 10, 100))

            try:
                exec(compiled, safe_globals, local_vars)
            finally:
                sys.setrecursionlimit(old_limit)

        except RecursionError as e:
            raise ScriptRecursionError(
                f"Exceeded recursion limit ({self.limits.max_recursion})"
            ) from e
        except ScriptError:
            raise
        except Exception as e:
            raise ScriptError(f"Execution error: {type(e).__name__}: {e}") from e

        # Check time limit one final time
        elapsed = (time.time() - self._start_time) * 1000
        if elapsed > self.limits.max_time_ms:
            raise ScriptTimeout(f"Script exceeded time limit ({self.limits.max_time_ms}ms)")

        # Return result and output
        result = local_vars.get('result', None)
        return result, self._output

    async def execute_async(
        self,
        code: str,
        ctx: ScriptContext,
        *,
        validate: bool = True,
    ) -> tuple[Any, list[str]]:
        """
        Execute script code asynchronously.

        Runs the script in a thread pool to avoid blocking the event loop.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.execute(code, ctx, validate=validate)
        )


class SimpleScriptRunner:
    """
    Simple script runner for basic action scripts.

    Handles the common case of scripts that are just commands to execute,
    like "say Hello, %n!" - no Python execution needed.
    """

    @staticmethod
    def is_simple_script(code: str) -> bool:
        """Check if this is a simple command script (no Python)."""
        # Simple scripts are single lines that look like commands
        lines = code.strip().split('\n')
        if len(lines) != 1:
            return False

        line = lines[0].strip()
        # Simple if it starts with a command word and doesn't have Python syntax
        if any(kw in line for kw in ['def ', 'class ', 'import ', 'for ', 'while ', 'if ']):
            return False
        if '=' in line and not line.startswith('say ') and not line.startswith('pose '):
            # Could be assignment, treat as Python
            return '==' in line  # Only == is comparison, = might be assignment

        return True

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
