"""
Scripting system for REALM.

Provides sandboxed execution of user-defined scripts (softcode) with:
- Pattern triggers ($command and ^listen patterns)
- Restricted Python execution with resource limits
- Built-in functions for common operations
- Substitution codes (%n, %#, %0-%9, etc.)
"""

from realm.scripting.bindings import (
    clear_bindings,
    registered_bindings,
    softcode_function,
)
from realm.scripting.engine import ScriptEngine
from realm.scripting.functions import ScriptFunctions
from realm.scripting.sandbox import ScriptError, ScriptSandbox, ScriptTimeout
from realm.scripting.triggers import (
    CommandTrigger,
    EventTrigger,
    ListenTrigger,
    TriggerManager,
    TriggerMatch,
)

__all__ = [
    # Sandbox
    "ScriptSandbox",
    "ScriptError",
    "ScriptTimeout",
    # Triggers
    "TriggerManager",
    "CommandTrigger",
    "ListenTrigger",
    "EventTrigger",
    "TriggerMatch",
    # Functions
    "ScriptFunctions",
    # Native bindings (the operator/pack-author escape hatch)
    "softcode_function",
    "registered_bindings",
    "clear_bindings",
    # Engine
    "ScriptEngine",
]
