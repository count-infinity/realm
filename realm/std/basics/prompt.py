"""
The default prompt (MUD_PLAN 3.3).

A template in the player's ``prompt`` attribute, else the ``PROMPT``
setting (default ``"<{hp}/{max_hp}hp> "``). Tokens in braces:

- every pool the player has, by name, and its ``max_<name>``;
- ``{name}``, ``{room}``;
- ``{combat}``: the condition of whoever the player is fighting
  (``excellent`` down to ``awful``), empty out of a fight;
- ``{level}`` and ``{xp}``, when the player has them.

A token the player does not have is left as typed. An empty template is
no prompt at all (``prompt off``).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from realm.core.pools import damage_pool, declared_pools, pool_get, pool_max, pool_percent
from realm.core.pools import vital_pool as vital_pool_of
from realm.core.world import get_world

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject

TOKEN = re.compile(r"\{(\w+)\}")

#: (lowest percent of the vital pool left, word), ROM's condition scale.
CONDITIONS: tuple[tuple[float, str], ...] = (
    (100, "excellent"), (90, "scratched"), (75, "bruised"), (50, "wounded"),
    (30, "nasty"), (15, "hurt"), (0, "awful"),
)


def condition_word(obj: GameObject) -> str:
    """How hurt ``obj`` looks: ``excellent`` ... ``awful``."""
    pool = vital_pool_of(obj)
    percent = pool_percent(obj, pool) if pool is not None else None
    if percent is None:
        return ""
    for floor, word in CONDITIONS:
        if percent >= floor:
            return word
    return CONDITIONS[-1][1]


def _opponent(player: GameObject) -> GameObject | None:
    combat = get_world().services.get("combat")
    encounter = combat.encounter_of(player) if combat is not None else None
    if encounter is None:
        return None
    me = encounter.get(player.id)
    them = encounter.get(me.target_id) if me is not None and me.target_id else None
    return them.obj if them is not None else None


def template_for(player: GameObject) -> str:
    """The player's template, else the game's ``PROMPT``."""
    own = player.db.get("prompt")
    return str(own) if own is not None else str(get_world().setting("PROMPT"))


def prompt_values(player: GameObject) -> dict[str, Any]:
    values: dict[str, Any] = {
        "name": player.name,
        "room": player.location.name if player.location is not None else "",
    }
    names = list(declared_pools(player))
    for name in (damage_pool(player), vital_pool_of(player)):
        if name is not None and name not in names:
            names.append(name)
    for name in names:
        values[name] = pool_get(player, name)
        maximum = pool_max(player, name)
        if maximum is not None:
            values[f"max_{name}"] = maximum
    for attr in ("level", "xp"):
        value = player.db.get(attr)
        if value is not None:
            values[attr] = value
    opponent = _opponent(player)
    values["combat"] = condition_word(opponent) if opponent is not None else ""
    return values


def render_prompt(player: GameObject) -> str | None:
    """The ``basics`` prompt renderer."""
    template = template_for(player)
    if not template:
        return None
    values = prompt_values(player)
    return TOKEN.sub(lambda m: str(values[m[1]]) if m[1] in values else m[0], template)


async def cmd_prompt(ctx: CommandContext) -> None:
    """
    Show or set your prompt, the line after each batch of output.

    Usage: prompt                 show yours
           prompt <template>      e.g. prompt <{hp}hp {mana}m {move}mv>
           prompt default         the game's own
           prompt off             none

    Tokens: any pool by name and max_<name> ({hp}, {max_hp}), {name},
    {room}, {combat} (your opponent's condition), {level}, {xp}.
    """
    player = ctx.player
    args = ctx.args or ""
    word = args.strip().lower()
    if not word:
        template = template_for(player)
        await ctx.session.send(f"Your prompt is: {template}" if template
                               else "Your prompt is off.")
        return
    if word == "default":
        player.db.delete("prompt")
        await ctx.session.send("Your prompt is the game's default again.")
        return
    if word == "off":
        player.db.prompt = ""
        await ctx.session.send("Prompt off.")
        return
    template = args.strip()
    player.db.prompt = template + " "               # a prompt ends with a space
    await ctx.session.send(f"Prompt set: {template}")


__all__ = ["CONDITIONS", "condition_word", "render_prompt", "template_for",
           "prompt_values", "cmd_prompt"]
