"""
Aliases (MUD_PLAN 10.3): a player's own short words for command lines.

``alias kk = kick $1`` makes ``kk fido`` run ``kick fido``. In the line,
``$1`` .. ``$9`` are the words typed after the alias and ``$*`` all of
them; a line with none of these gets the words appended. Aliases live on
the character (``aliases``, a word -> line mapping), are expanded once
(an alias inside an expansion is not expanded again), and a word that
begins with ``@`` is never one, so a builder command cannot be shadowed.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from realm.commands.base import save_object
from realm.core.world import get_world

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject
    from realm.core.world import World
    from realm.gateway.session import Session

ALIAS_ATTR = "aliases"
#: An alias is one word of letters, digits and ``_``.
WORD = re.compile(r"^\w{1,20}$")
#: Words that cannot be aliased: the commands that manage aliases.
RESERVED = frozenset({"alias", "unalias"})
_PLACEHOLDER = re.compile(r"\$([1-9*])")


def aliases_of(player: GameObject) -> dict[str, str]:
    return dict(player.db.get(ALIAS_ATTR) or {})


def expand(line: str, template: str) -> str:
    """``template`` with the words after the alias in ``line`` put in."""
    args = line.split()[1:]

    def fill(match: re.Match) -> str:
        key = match[1]
        if key == "*":
            return " ".join(args)
        index = int(key) - 1
        return args[index] if index < len(args) else ""

    if _PLACEHOLDER.search(template) is None:
        return " ".join([template, *args])
    return " ".join(_PLACEHOLDER.sub(fill, template).split())


async def alias_interceptor(world: World, session: Session, line: str) -> str | bool:
    """``feature.input_interceptor``: the line with its alias expanded."""
    player = session.player
    if player is None:
        return False
    words = line.split(None, 1)
    if not words or words[0].startswith("@"):
        return False
    template = aliases_of(player).get(words[0].lower())
    if template is None:
        return False
    return expand(line, template)


async def cmd_alias(ctx: CommandContext) -> None:
    """
    Make a short word stand for a command line.

    Usage: alias                       list yours
           alias <word>                show one
           alias <word> = <command>    make one

    In the command, $1 to $9 are the words you type after the alias and
    $* all of them; with none of these, what you type is added at the end.
    An alias is not expanded inside another, and never begins with @.

    Example:
        alias kk = kick $1
        alias ts = tell Sam $*
        alias gc = get all corpse
    """
    player = ctx.player
    mine = aliases_of(player)
    raw = ctx.args or ""
    word = (ctx.left_args if "=" in raw else raw).strip().lower()
    if not word:
        if not mine:
            await ctx.session.send("You have no aliases. Usage: alias <word> = <command>")
            return
        lines = ["Your aliases:"]
        lines.extend(f"  {name:12} {mine[name]}" for name in sorted(mine))
        ctx.session.send_paged("\n".join(lines))
        return
    if "=" not in raw:
        if word in mine:
            await ctx.session.send(f"{word} = {mine[word]}")
        else:
            await ctx.session.send(f"You have no alias '{word}'.")
        return
    line = ctx.right_args.strip()
    if word.startswith("@"):
        await ctx.session.send("An alias may not begin with @.")
        return
    if not WORD.match(word):
        await ctx.session.send("An alias is one word of letters, digits and _, "
                               "at most 20 long.")
        return
    if word in RESERVED:
        await ctx.session.send(f"'{word}' cannot be an alias.")
        return
    if not line:
        await ctx.session.send(f"Alias {word} to what? (unalias {word} removes it.)")
        return
    limit = int(get_world().setting("ALIAS_LIMIT"))
    if word not in mine and len(mine) >= limit:
        await ctx.session.send(f"You have {limit} aliases, the most you may keep. "
                               f"Unalias one first.")
        return
    mine[word] = line
    player.db.set(ALIAS_ATTR, mine)
    await save_object(ctx, player)
    await ctx.session.send(f"Alias set: {word} = {line}")


async def cmd_unalias(ctx: CommandContext) -> None:
    """
    Remove one of your aliases.

    Usage: unalias <word>
    """
    player = ctx.player
    word = (ctx.args or "").strip().lower()
    mine = aliases_of(player)
    if not word:
        await ctx.session.send("Usage: unalias <word>")
        return
    if word not in mine:
        await ctx.session.send(f"You have no alias '{word}'.")
        return
    del mine[word]
    if mine:
        player.db.set(ALIAS_ATTR, mine)
    else:
        player.db.delete(ALIAS_ATTR)
    await save_object(ctx, player)
    await ctx.session.send(f"Alias {word} removed.")


__all__ = ["ALIAS_ATTR", "RESERVED", "aliases_of", "expand", "alias_interceptor",
           "cmd_alias", "cmd_unalias"]
