"""
The one safe-expression engine for REALM.

Every place the game evaluates builder- or player-authored Python —
lock expressions (@lock), combat strategy conditions, and the script
sandbox — validates against THIS module's rules. One validator, one
threat model, one place to fix a hole.

Two entry points:

- ``validate_code(code, mode)``: AST-validate a program (``'exec'``,
  used by the script sandbox) or a single expression (``'eval'``, used
  by locks and strategy conditions). Returns error strings, empty if OK.
- ``eval_expression(expression, namespace)``: validate + compile +
  evaluate an expression with no builtins beyond ``SAFE_EXPR_BUILTINS``
  and the provided namespace. ``eval_bool`` is the fail-closed variant
  every gate should use.

Compiled expressions are LRU-cached — locks and strategy rules are
evaluated every action/beat, but the expression strings rarely change.
"""

from __future__ import annotations

import ast
from functools import lru_cache
from typing import Any

# Forbidden AST node types (statements that escape the sandbox's grasp).
FORBIDDEN_NODES = {
    ast.Import,
    ast.ImportFrom,
    ast.Global,
    ast.Nonlocal,
}

# Forbidden names: builtins that break containment or reach the
# interpreter's plumbing.
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


class SafeAstValidator(ast.NodeVisitor):
    """Collects security violations in a parsed tree."""

    def __init__(self) -> None:
        self.errors: list[str] = []

    def visit(self, node: ast.AST) -> None:
        if type(node) in FORBIDDEN_NODES:
            self.errors.append(f"Forbidden construct: {type(node).__name__}")

        if isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES:
                self.errors.append(f"Forbidden name: {node.id}")
            if node.id.startswith('_'):
                self.errors.append(f"Private names not allowed: {node.id}")

        if isinstance(node, ast.Attribute) and node.attr.startswith('_'):
            self.errors.append(f"Private attribute access not allowed: {node.attr}")

        # A catch-all handler could swallow the sandbox's resource-limit kill
        # (a BaseException) and run on unwatched — the try/except DoS. Forbid
        # the two shapes that reach BaseException; ``except Exception`` and
        # named exceptions stay allowed for ordinary error handling.
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                self.errors.append(
                    "Bare 'except:' is not allowed; catch a specific "
                    "exception (e.g. 'except Exception')")
            else:
                caught = (node.type.elts if isinstance(node.type, ast.Tuple)
                          else [node.type])
                if any(isinstance(n, ast.Name) and n.id == 'BaseException'
                       for n in caught):
                    self.errors.append(
                        "'except BaseException' is not allowed; catch "
                        "'Exception' or a specific exception instead")

        self.generic_visit(node)


def validate_code(code: str, mode: str = 'exec') -> list[str]:
    """
    Validate code without executing it.

    Args:
        code: Source to check.
        mode: ``'exec'`` for programs, ``'eval'`` for single expressions.

    Returns:
        List of error messages; empty means the code passed.
    """
    try:
        tree = ast.parse(code, mode=mode)
    except SyntaxError as e:
        return [f"Syntax error: {e.msg} at line {e.lineno}"]

    validator = SafeAstValidator()
    validator.visit(tree)
    return validator.errors


# Builtins available inside evaluated EXPRESSIONS (locks, strategy
# conditions). Deliberately smaller than the script sandbox's set —
# expressions are gates, not programs.
SAFE_EXPR_BUILTINS: dict[str, Any] = {
    'True': True,
    'False': False,
    'None': None,
    'int': int,
    'float': float,
    'str': str,
    'bool': bool,
    'len': len,
    'abs': abs,
    'min': min,
    'max': max,
    'any': any,
    'all': all,
    'round': round,
    'sum': sum,
}


@lru_cache(maxsize=1024)
def _compile_expression(expression: str):
    """Validate + compile an expression. Raises ValueError if invalid."""
    errors = validate_code(expression, mode='eval')
    if errors:
        raise ValueError("; ".join(errors))
    return compile(expression, '<safe_expr>', 'eval')


def compile_expression(expression: str):
    """
    Compile a validated expression (cached).

    Raises:
        ValueError: on syntax errors or forbidden constructs.
    """
    return _compile_expression(expression.strip())


def eval_expression(expression: str, namespace: dict[str, Any]) -> Any:
    """
    Validate, compile, and evaluate an expression.

    The namespace is layered over SAFE_EXPR_BUILTINS; real builtins are
    stripped entirely.

    Raises:
        ValueError: if the expression fails validation.
        Exception: whatever the expression itself raises.
    """
    compiled = compile_expression(expression)
    full_namespace = dict(SAFE_EXPR_BUILTINS)
    full_namespace.update(namespace)
    return eval(compiled, {"__builtins__": {}}, full_namespace)


def eval_bool(expression: str, namespace: dict[str, Any]) -> bool:
    """
    Fail-closed boolean evaluation for gates (locks, strategy conditions).

    Invalid expressions and runtime errors both return False.
    """
    try:
        return bool(eval_expression(expression, namespace))
    except Exception:
        return False


__all__ = [
    "FORBIDDEN_NODES",
    "FORBIDDEN_NAMES",
    "SAFE_EXPR_BUILTINS",
    "SafeAstValidator",
    "validate_code",
    "compile_expression",
    "eval_expression",
    "eval_bool",
]
