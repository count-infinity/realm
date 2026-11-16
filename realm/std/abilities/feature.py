"""
The ``abilities`` feature.

Abilities and spells as data (ability_def / spell_def).
"""

from __future__ import annotations

from realm.features import Feature
from realm.std.abilities import softcode
from realm.std.abilities.actions import AbilityAction
from realm.std.abilities.caster import CasterBehavior
from realm.std.abilities.commands import cmd_cast, cmd_spells
from realm.std.abilities.magic_items import cmd_use_magic
from realm.std.abilities.verbs import ability_fallback, cmd_abilities

feature = Feature(
    'abilities',
    requires=['rules', 'combat'],
    doc='Abilities and spells as data (ability_def / spell_def).',
)

feature.command(
    'cast',
    cmd_cast,
    category='combat',
    help_text='Cast a spell',
    usage='cast <spell> [target]',
)
feature.command(
    'spells',
    cmd_spells,
    aliases=['sp'],          # step 11's `split` made the prefix ambiguous
    category='combat',
    help_text='List spells you can cast',
    usage='spells',
)

feature.command(
    'quaff',
    cmd_use_magic,
    category='items',
    help_text='Drink a potion',
    usage='quaff <potion>',
)
feature.command(
    'recite',
    cmd_use_magic,
    category='items',
    help_text='Read a scroll aloud',
    usage='recite <scroll> [target]',
)
feature.command(
    'zap',
    cmd_use_magic,
    aliases=['brandish'],
    category='items',
    help_text='Zap a wand, or brandish a staff at the room',
    usage='zap <wand> [target] | brandish <staff>',
)

feature.command(
    'abilities',
    cmd_abilities,
    aliases=['ab'],
    category='combat',
    help_text='List the abilities you can use',
)
# A typed ability name runs it: `kick fido`.
feature.fallback(ability_fallback)

feature.behavior(CasterBehavior)


async def _use_ability(engine, frame, obj, payload) -> None:
    """Queued by softcode use_ability(): run the definition on the loop."""
    from realm.std.abilities.abilities import SPELL_DEF_TAG, invoke_ability
    adef, target = payload
    if adef.has_tag(SPELL_DEF_TAG):
        await invoke_ability(obj, adef, target, verb="cast", domain="spell")
    else:
        await invoke_ability(obj, adef, target)


async def _cast(engine, frame, obj, payload) -> None:
    """Queued by softcode cast(): fire event:on_cast at the target.

    Remote reach is gated by the target room's REACH lock, like
    act(targeting='remote'); a co-located cast is ward-defended and open.
    No kernel-forced category: the caster supplies the tags."""
    from realm.core.events import fire_event
    from realm.core.propagation import _room_of
    from realm.permissions.locks import LockType, check_lock
    ability, extra_tags = payload
    caster = frame.executor
    target_room = _room_of(obj)
    reach_ok = caster is not None and _room_of(caster) is target_room
    if not reach_ok and caster is not None and target_room is not None:
        reach_ok = check_lock(target_room, LockType.REACH, caster)
    if reach_ok:
        await fire_event(caster, obj, AbilityAction.ON_CAST, tags=set(extra_tags),
                         extra={"ability": ability, "caster": caster}, gated=True)


feature.queue_kind("ability", _use_ability)
feature.queue_kind("cast", _cast)



feature.event(AbilityAction.ON_CAST, hook="CAST",
              doc="an ability is directed at this object (resist via on_check)",
              payload={"ability": "the ability's name", "caster": "who directed it"})

# Abilities and spells are data: ability_def / spell_def objects.
feature.def_kind("ability", "ability_def")
feature.def_kind("spell", "spell_def")


# --- softcode ------------------------------------------------------------------

feature.softfn(softcode.cast, group='Combat & effects')
feature.softfn(softcode.use_ability, group='Combat & effects', harm=True)
