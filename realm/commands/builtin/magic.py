"""
Spellcasting commands: ``cast`` and ``spells``.

Thin by design — a spell is data (a ``spell_def`` object) and casting is
one propagated ``spell:<name>`` action; the whole pipeline lives in
``realm.systems.spells``. This module only parses, gates *knowledge*
(class/level — payment is enforced inside the propagation's apply step,
after wards have had their say), and fires.

    cast fireball priest
    cast 'magic missile' beggar     (Diku-style quoting for multiword names)
    cast heal                       (defensive spells default to yourself)
"""

from __future__ import annotations

from realm.commands import CommandContext, CommandDispatcher
from realm.commands.base import find_object
from realm.systems.spells import (
    cast_spell,
    find_spell_def,
    knows_spell,
    list_spell_defs,
)


def _parse(args: str) -> tuple[str, str]:
    """Split ``args`` into (spell name, target words). A quoted leading
    token is the name; otherwise the longest leading word-run naming a
    known spell wins, so ``cast magic missile beggar`` parses too."""
    args = args.strip()
    if args.startswith("'"):
        end = args.find("'", 1)
        if end > 0:
            return args[1:end].strip(), args[end + 1:].strip()
        return args[1:].strip(), ""
    words = args.split()
    for i in range(len(words), 0, -1):
        name = " ".join(words[:i])
        if find_spell_def(name) is not None:
            return name, " ".join(words[i:])
    return args, ""


async def cmd_cast(ctx: CommandContext) -> None:
    """
    Cast a spell you know at a target (or yourself).

    Usage: cast <spell> [target]

    Example:
        cast 'magic missile' beggar
    """
    if not ctx.player or not ctx.args or not ctx.args.strip():
        await ctx.session.send("Cast what?")
        return
    name, target_words = _parse(ctx.args)
    spell = find_spell_def(name)
    if spell is None:
        # No such spell — but a softcode $cast verb may own this phrasing
        # ("cast line" on a fishing pond). Builtin registration must not
        # shadow world verbs, so offer the line to the script engine first.
        from realm.scripting.engine import get_script_engine
        engine = get_script_engine()
        if engine is not None and await engine.handle_unknown_command(ctx):
            return
        await ctx.session.send(f"You know no spell called '{name}'.")
        return
    if not knows_spell(ctx.player, spell):
        await ctx.session.send(f"You don't know how to cast {spell.name}.")
        return
    target = None
    if target_words:
        target = find_object(ctx, target_words,
                             search_room=True, search_inventory=False)
        if target is None:
            await ctx.session.send(f"You don't see '{target_words}' here.")
            return
    await cast_spell(ctx.player, spell, target)


async def cmd_spells(ctx: CommandContext) -> None:
    """
    List the spells you can cast right now (class and level permitting).

    Usage: spells
    """
    if not ctx.player:
        return
    known = [s for s in list_spell_defs() if knows_spell(ctx.player, s)]
    if not known:
        await ctx.session.send("You know no spells.")
        return
    lines = ["Spells you can cast:"]
    for s in sorted(known, key=lambda o: (int(o.db.get('level') or 1), o.name)):
        mana = int(s.db.get('mana') or 0)
        lines.append(f"  {s.name:<20} level {int(s.db.get('level') or 1):>2}"
                     f"  mana {mana:>3}")
    await ctx.session.send("\n".join(lines))


def register_magic_commands(dispatcher: CommandDispatcher) -> None:
    """Register spellcasting commands with the dispatcher."""
    from functools import partial
    register = partial(dispatcher.register, category="combat")
    register("cast", cmd_cast,
             help_text="Cast a spell", usage="cast <spell> [target]")
    register("spells", cmd_spells,
             help_text="List spells you can cast", usage="spells")
