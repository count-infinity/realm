"""
Magic items: potions, scrolls, wands and staves (MUD_PLAN 3.4).

An item names its spells in ``spells`` (a list of spell_def names) and the
power they come out at in ``spell_level``. Using it invokes each spell
through ``invoke_ability`` at that level, free and with no class check
(a warrior may zap a mage's wand), then uses the item up: a potion or
scroll is gone, a wand or staff loses one of its ``charges`` and fizzles
at none.

| Command | Item tag | Aimed at |
|---|---|---|
| ``quaff <potion>`` | ``potion`` | the drinker |
| ``recite <scroll> [target]`` | ``scroll`` | the target, else the spell's default |
| ``zap <wand> [target]`` | ``wand`` | the target, else the spell's default |
| ``brandish <staff>`` | ``staff`` | the room: a harmful spell everyone else, a kind one everyone |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.commands.base import find_object
from realm.core.world import get_world
from realm.std.abilities.abilities import _effects_of, _is_offensive, invoke_ability
from realm.std.abilities.spells import find_spell_def

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject

#: verb -> (the item tag it takes, whether using it uses it up)
MAGIC_VERBS: dict[str, tuple[str, bool]] = {
    "quaff": ("potion", True),
    "recite": ("scroll", True),
    "zap": ("wand", False),
    "brandish": ("staff", False),
}


def _spells(item: GameObject) -> list[GameObject]:
    names = item.db.get("spells") or []
    if isinstance(names, str):
        names = [names]
    found = (find_spell_def(str(name)) for name in names)
    return [spell for spell in found if spell is not None]


def _characters(room: GameObject | None) -> list[GameObject]:
    return [o for o in (room.contents if room is not None else ())
            if o.is_player or o.is_npc]


async def _use_up(item: GameObject, consumed: bool) -> None:
    if not consumed:
        item.db.charges = int(item.db.get("charges") or 0) - 1
        return
    store = get_world().store
    item.location = None
    if store is not None:
        await store.delete(item)


async def cmd_use_magic(ctx: CommandContext) -> None:
    """
    Use a magic item: quaff a potion, recite a scroll, zap a wand, or
    brandish a staff.

    Usage: quaff <potion>
           recite <scroll> [target]
           zap <wand> [target]
           brandish <staff>
    """
    # ``brandish`` is an alias of ``zap``, so the word typed decides.
    typed = (ctx.raw_input.split(maxsplit=1) or [""])[0].lower()
    verb = next((v for v in MAGIC_VERBS if typed and v.startswith(typed)),
                ctx.command_name if ctx.command_name in MAGIC_VERBS else "zap")
    tag, consumed = MAGIC_VERBS[verb]
    words = (ctx.args or "").split(maxsplit=1)
    player = ctx.player
    item = find_object(ctx, words[0], search_room=False, search_inventory=True) \
        if words else None
    if item is None or not item.has_tag(tag):
        # A world's own $quaff or $zap verb comes before the refusal (as cast).
        engine = get_world().scripts
        if engine is not None and await engine.handle_unknown_command(ctx):
            return
        if not words:
            await ctx.session.send(f"{verb.capitalize()} what?")
        elif item is None:
            await ctx.session.send(f"You aren't carrying '{words[0]}'.")
        else:
            await ctx.session.send(f"You can't {verb} {item.name}.")
        return
    if not consumed and int(item.db.get("charges") or 0) <= 0:
        await ctx.session.send(f"You {verb} {item.name}, but it fizzles.")
        return

    target = None
    if verb in ("recite", "zap") and len(words) > 1:
        target = find_object(ctx, words[1], search_room=True, search_inventory=False)
        if target is None:
            await ctx.session.send(f"You don't see '{words[1]}' here.")
            return

    player.msg(f"You {verb} {item.name}.")
    if player.location is not None:
        player.location.msg_contents(f"{player.get_display_name(None)} {verb}s "
                                     f"{item.name}.", exclude=[player])
    spells = _spells(item)
    if not spells:
        player.msg("Nothing happens.")
    level = int(item.db.get("spell_level") or 1)
    for spell in spells:
        if verb == "quaff":
            aims = [player]
        elif verb == "brandish":
            harmful = _is_offensive(spell, _effects_of(spell))
            aims = [o for o in _characters(player.location)
                    if not (harmful and o is player)]
        else:
            aims = [target]
        for aim in aims:
            await invoke_ability(player, spell, aim, verb="cast", domain="spell",
                                 free=True, level=level)
    await _use_up(item, consumed)


__all__ = ["MAGIC_VERBS", "cmd_use_magic"]
