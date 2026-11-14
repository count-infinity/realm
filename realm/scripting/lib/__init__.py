"""
The kernel's softcode functions, one module per area. A feature's own
functions live in its package (``realm/std/combat/softcode.py``) and its
``feature.py`` declares them.

Importing this package registers every function in
``realm.scripting.registry``. ``realm.scripting.functions`` imports it, so
any code that builds a softcode namespace sees them.
"""

from realm.scripting.lib import (  # noqa: F401  (imported to register)
    attrs,
    behaviors,
    dice,
    lists,
    locks,
    mathx,
    messaging,
    objects,
    pools,
    scheduling,
    tags,
    text,
    travel,
)
