"""
The built-in softcode functions, one module per owner.

Importing this package registers every function in
``realm.scripting.registry``. ``realm.scripting.functions`` imports it, so
any code that builds a softcode namespace sees them.
"""

from realm.scripting.lib import (  # noqa: F401  (imported to register)
    abilities,
    attrs,
    behaviors,
    checks,
    combat,
    economy,
    effects,
    lists,
    locks,
    mathx,
    messaging,
    objects,
    scheduling,
    social,
    tags,
    text,
    travel,
)
