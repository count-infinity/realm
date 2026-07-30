"""
CasterBehavior: an NPC that casts spells in combat.

The Diku ``spec_cast_mage`` / ``spec_breath_*`` family, as one
parameterized behavior instead of per-proc C code. On its tick, while in
an encounter, it picks a spell from its list and casts **through the same
``cast_spell`` pipeline players use** — so NPC spells are ward-able,
save-able, and resistance-checked identically, and a hostile cast shows
up on the event bus like any other action.

    mage.add_behavior(CasterBehavior(
        spells=["chill touch", "fireball"], chance=0.5))

The ROM importer attaches this automatically to ``rom_spec:spec_cast_*``
and ``spec_breath_*`` mobs (see scripts/rom_import.py).
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from realm.core.behaviors import Behavior, BehaviorRegistry

if TYPE_CHECKING:
    from realm.core.objects import GameObject


@BehaviorRegistry.register
class CasterBehavior(Behavior):
    """Casts a random spell from its list each tick while fighting."""

    behavior_id = "caster"
    blurb = "Casts spells from a list while in combat (Diku spec_cast_*)."
    param_spec = {
        'spells': ([], 'spell_def names this caster may cast'),
        'chance': (0.5, 'probability per tick of attempting a cast'),
    }

    @property
    def should_tick(self) -> bool:
        return True

    async def tick(self, obj: GameObject, delta: float) -> None:
        from realm.combat.manager import get_combat_manager
        from realm.systems.spells import cast_spell, find_spell_def

        manager = get_combat_manager()
        if manager is None or obj.location is None:
            return
        encounter = manager.encounter_in(obj.location)
        if encounter is None or encounter.get(obj.id) is None:
            return
        if random.random() > float(self.get_param('chance', 0.5)):
            return
        names = [str(n) for n in (self.get_param('spells') or [])]
        random.shuffle(names)
        for name in names:
            spell = find_spell_def(name)
            if spell is None:
                continue                      # not defined in this world
            target = self._opponent(encounter, obj)
            # cast_spell self-targets defensive spells and resolves the
            # combat opponent for offensive ones; either way it enforces
            # payment and runs the full check pass.
            await cast_spell(obj, spell, target)
            return

    def _opponent(self, encounter, obj: GameObject) -> GameObject | None:
        me = encounter.get(obj.id)
        if me is not None and me.target_id:
            other = encounter.get(me.target_id)
            if other is not None:
                return other.obj
        for participant in encounter.participants.values():
            if participant.obj is not obj and participant.combatant.is_alive:
                return participant.obj
        return None
