"""
Scripting system for REALM.

Provides sandboxed execution of user-defined scripts (softcode) with:
- Pattern triggers ($command and ^listen patterns)
- Restricted Python execution with resource limits
- Built-in functions for common operations
- Substitution codes (%n, %#, %0-%9, etc.)
"""

from realm.scripting.sandbox import ScriptSandbox, ScriptError, ScriptTimeout
from realm.scripting.triggers import (
    TriggerManager,
    CommandTrigger,
    ListenTrigger,
    EventTrigger,
    TriggerMatch,
)
from realm.scripting.functions import ScriptFunctions
from realm.scripting.engine import (
    ScriptEngine,
    get_engine,
    set_engine,
    softcode_fallback,
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
    # Engine
    "ScriptEngine",
    "get_engine",
    "set_engine",
    "softcode_fallback",
]
