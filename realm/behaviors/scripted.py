"""
ScriptedBehavior: behavior logic defined in-world, as data.

The behavior counterpart of ``skill_def``/``class_def``. A **behavior_def**
is an ordinary object tagged ``behavior_def`` whose attributes are softcode
hook bodies:

    @create hazard_filter
    @tag hazard_filter = behavior_def
    @set hazard_filter/blurb = cuts hazard severity while its carrier is online
    @set hazard_filter/on_check = if has_atag('hazard'): set_adata('severity', param('cut_to', 2))

    @behavior carbon filter = hazard_filter, cut_to:2
    @behavior air vent = hazard_filter, cut_to:4

Attaching by the def's name works exactly like attaching a compiled
behavior: the registry, finding no Python class, falls back to this
module's factory and hands back a ``ScriptedBehavior`` bound to the def
*by name*. Hooks re-read the def at fire time, so softcode stays live —
edit the def's ``on_check`` and every attached instance changes on the
next action, no reload. A def that goes missing leaves its instances
inert rather than erroring.

Hook attributes a behavior_def may carry:

- ``on_check`` — decision pass, the same restricted veto/modify namespace
  as an object's own ``on_check`` ward (``block``/``mod``/``set_adata`` +
  reads). Because behaviors run for *bystanders* too, this is how an
  ordinary object in the room opts into interception — the attach step
  (builder-gated ``@behavior``) is the authority line.
- ``on_react`` — reaction pass, full script namespace with the event data
  (``atype``/``adata``/``has_atag``/``target``) bound. Runs for every
  action the object witnesses; filter on ``atype`` or ``has_atag`` first.
- ``on_tick`` — periodic, full namespace, paced by the ``interval``
  param in world beats (default 4), like ``script_ticker``.

Every hook runs with the **attached object** as executor (``me`` is the
filter, not the def), and ``param(key, default)`` reads the attachment's
own parameters, so one def serves many differently-tuned carriers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from realm.core.behaviors import Behavior, BehaviorRegistry

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.core.propagation import Action

DEF_TAG = "behavior_def"

#: Attributes on a behavior_def that hold hook code, in doc order.
HOOK_ATTRS = ("on_check", "on_react", "on_tick")


def find_behavior_def(name: str) -> GameObject | None:
    """The live ``behavior_def`` object of this name, or None."""
    from realm.persistence.manager import get_active_manager

    manager = get_active_manager()
    if manager is None or not name:
        return None
    for obj in manager.find_cached(name=name):
        if obj.has_tag(DEF_TAG):
            return obj
    return None


def list_behavior_defs() -> list[str]:
    """Names of every behavior_def object in the world, sorted."""
    from realm.persistence.manager import get_active_manager

    manager = get_active_manager()
    if manager is None:
        return []
    return sorted({o.name for o in manager.find_cached(tag=DEF_TAG)})


def describe_behavior_def(definition: GameObject) -> dict[str, Any]:
    """``Behavior.describe()``'s shape, for a behavior_def object.

    A def may optionally carry a ``blurb`` attribute and a ``param_spec``
    attribute — a dict of ``name: [default, about]`` (JSON, so lists
    rather than tuples) — mirroring the class metadata. ``hooks`` lists
    which hook attributes the def actually carries, so a palette can show
    at a glance whether this is an interceptor, a reactor, or a ticker.
    """
    params: dict[str, dict[str, Any]] = {}
    raw = definition.db.get('param_spec')
    if isinstance(raw, dict):
        for name, entry in raw.items():
            if isinstance(entry, (list, tuple)) and len(entry) == 2:
                default, about = entry
            else:
                default, about = entry, ''
            params[str(name)] = {
                'default': default,
                'about': str(about),
                'type': type(default).__name__ if default is not None else 'any',
            }
    hooks = [attr for attr in HOOK_ATTRS
             if isinstance(definition.db.get(attr), str)
             and definition.db.get(attr).strip()]
    return {
        'id': definition.name,
        'blurb': str(definition.db.get('blurb') or ''),
        'params': params,
        'hooks': hooks,
    }


class ScriptedBehavior(Behavior):
    """Runs hook softcode from a ``behavior_def`` object, resolved by name.

    Deliberately NOT in the registry under its own id: instances are minted
    only through the registry's scripted-factory fallback, and each reports
    its def's name as its ``behavior_id`` so listing, ``@behavior/remove``,
    and serialization all speak the builder's name for it.
    """

    __slots__ = ()

    param_spec = {
        'interval': (4, 'world beats between on_tick runs (defs with '
                        'on_tick only)'),
    }

    @property
    def behavior_id(self) -> str:  # type: ignore[override]
        return str(self._params.get('def_name', 'scripted'))

    def _definition(self) -> GameObject | None:
        return find_behavior_def(self.behavior_id)

    def _hook(self, attr: str) -> str | None:
        definition = self._definition()
        if definition is None:
            return None
        code = definition.db.get(attr)
        if isinstance(code, str) and code.strip():
            return code
        return None

    # --- Action propagation (two-pass) ---

    async def on_check(self, obj: GameObject, action: Action) -> None:
        code = self._hook('on_check')
        if code is None:
            return
        from realm.scripting.engine import get_script_engine

        engine = get_script_engine()
        if engine is not None:
            await engine.run_check_code(obj, action, code,
                                        params=self._params)

    async def on_react(self, obj: GameObject, action: Action) -> None:
        code = self._hook('on_react')
        if code is None:
            return
        from realm.scripting.engine import get_script_engine

        engine = get_script_engine()
        if engine is not None:
            await engine.run_behavior_script(obj, code, action=action,
                                             params=self._params)

    # --- Periodic updates ---

    @property
    def should_tick(self) -> bool:
        return self._hook('on_tick') is not None

    async def tick(self, obj: GameObject, delta: float) -> None:
        code = self._hook('on_tick')
        if code is None:
            return
        if not self.countdown(obj, f'sb_{self.behavior_id}_wait',
                              int(self.get_param('interval', 4))):
            return
        from realm.scripting.engine import get_script_engine

        engine = get_script_engine()
        if engine is not None:
            await engine.run_behavior_script(obj, code, params=self._params)


def _scripted_factory(behavior_id: str, params: dict[str, Any],
                      strict: bool) -> ScriptedBehavior | None:
    """The registry's fallback for ids with no Python class.

    ``strict`` (attach time) requires the def to exist so a typo errors at
    the prompt; the load path passes False, because a saved behavior must
    survive its def merely loading later in the same restore.
    """
    if strict and find_behavior_def(behavior_id) is None:
        return None
    merged = dict(params)
    merged.setdefault('def_name', behavior_id)
    return ScriptedBehavior(**merged)


BehaviorRegistry.set_scripted_factory(_scripted_factory)

__all__ = ["ScriptedBehavior", "find_behavior_def", "list_behavior_defs",
           "describe_behavior_def", "DEF_TAG", "HOOK_ATTRS"]
