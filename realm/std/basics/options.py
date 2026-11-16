"""
Player settings (MUD_PLAN 10.4, capability audit G7): the ``config``
command and ``world.services["options"]``, the options it knows.

An option is an attribute kept by ``realm.core.options`` (on the account
when there is one, else on the character). ``basics`` declares ``color``,
``pagelength``, ``prompt``, ``screenreader`` and ``palette``; another
feature adds its own at install (``combat``: ``autoloot``, ``autogold``,
``autosplit``; ``look``: ``autoexit``, ``brief``)::

    options = world.services.get("options")
    if options is not None:
        options.toggle("autoloot", "Take everything from the corpses of what you kill.",
                       False)

Characters made before options lived on accounts carry theirs on the
character; the ``accounts`` feature moves them to the account when the
character next enters play (``carry_over_options``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from realm.commands.base import save_object
from realm.core.markup import COLOR_LETTERS
from realm.core.options import clear_option, get_option, set_option
from realm.core.world import find_world, get_world

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject

ON_WORDS = ("on", "yes", "true", "1")
OFF_WORDS = ("off", "no", "false", "0")


@dataclass(frozen=True)
class Option:
    """One player setting.

    ``parse(text)`` turns what the player typed into the stored value, or
    raises ValueError with the sentence to show; ``show(value)`` is how a
    stored value reads; ``default(player)`` is what applies when the
    player has set nothing."""

    name: str
    doc: str
    parse: Callable[[str], Any]
    show: Callable[[Any], str]
    default: Callable[[GameObject], str]

    @classmethod
    def toggle(cls, name: str, doc: str, default: bool) -> Option:
        """An on/off option."""
        return cls(name, doc, _parse_toggle, lambda v: "on" if v else "off",
                   lambda _p: "on" if default else "off")

    @classmethod
    def number(cls, name: str, doc: str, default: Callable[[GameObject], str]) -> Option:
        """A whole number, 0 or more."""
        return cls(name, doc, _parse_number, str, default)


def _parse_toggle(text: str) -> bool:
    word = text.strip().lower()
    if word in ON_WORDS:
        return True
    if word in OFF_WORDS:
        return False
    raise ValueError("Say on or off.")


def _parse_number(text: str) -> int:
    word = text.strip()
    if not word.isdigit():
        raise ValueError("Give a whole number, 0 or more.")
    return int(word)


class OptionsService:
    """``world.services["options"]``: the options ``config`` lists, by name."""

    def __init__(self) -> None:
        self.options: dict[str, Option] = {}

    def add(self, option: Option) -> None:
        """Declare an option. A second option of the same name raises."""
        name = option.name.lower()
        if name in self.options:
            raise ValueError(f"The option '{name}' is already declared; pick another name.")
        self.options[name] = option

    def toggle(self, name: str, doc: str, default: bool = False) -> None:
        """Declare an on/off option (a feature need not import ``Option``)."""
        self.add(Option.toggle(name, doc, default))

    def number(self, name: str, doc: str, default: int) -> None:
        """Declare a whole-number option."""
        self.add(Option.number(name, doc, lambda _player: str(default)))

    def get(self, name: str) -> Option | None:
        return self.options.get(name.lower())


# --- the basics options ----------------------------------------------------------------------


def _parse_prompt(text: str) -> str:
    template = text.strip()
    if template.lower() == "off":
        return ""
    return template + " "                   # a prompt ends with a space


def _show_prompt(value: Any) -> str:
    return str(value).rstrip() if value else "off"


def _parse_palette(text: str) -> dict[str, str]:
    """``r=m b=c``: red shows as magenta, blue as cyan."""
    palette: dict[str, str] = {}
    for pair in text.replace(",", " ").split():
        old, _, new = pair.lower().partition("=")
        if len(old) != 1 or len(new) != 1 or old not in COLOR_LETTERS \
                or new not in COLOR_LETTERS:
            raise ValueError(f"Write swaps as letter=letter, from {COLOR_LETTERS} "
                             f"(x black, r red, g green, y yellow, b blue, m magenta, "
                             f"c cyan, w white): config palette r=m b=c")
        palette[old] = new
    if not palette:
        raise ValueError("Write at least one swap: config palette r=m")
    return palette


def _show_palette(value: Any) -> str:
    return " ".join(f"{old}={new}" for old, new in sorted(dict(value).items())) or "none"


def _default_pagelength(player: GameObject) -> str:
    world = get_world()
    sessions = world.sessions
    session = sessions.get_session_by_player(player) if sessions is not None else None
    height = session.get_data("terminal_height") if session is not None else None
    if height:
        return f"{height} (your client's height)"
    return str(world.setting("PAGE_LENGTH"))


def _default_prompt(_player: GameObject) -> str:
    return _show_prompt(get_world().setting("PROMPT"))


BASIC_OPTIONS = (
    Option.toggle("color", "Color in what you are sent.", True),
    Option.number("pagelength", "Lines on one screen of long output; 0 never holds output.",
                  _default_pagelength),
    Option("prompt", "The line after each batch of output (see: help prompt); off for none.",
           _parse_prompt, _show_prompt, _default_prompt),
    Option.toggle("screenreader", "Plain text for a screen reader: no color and no "
                  "lines drawn only for looks.", False),
    Option("palette", "Swap colors you find hard to read: r=m b=c (x r g y b m c w).",
           _parse_palette, _show_palette, lambda _p: "none"),
)


def offer_options(world) -> None:
    """``on_install``: ``world.services["options"]`` with the basics options."""
    service = OptionsService()
    for option in BASIC_OPTIONS:
        service.add(option)
    world.services["options"] = service


def _service() -> OptionsService | None:
    world = find_world()
    return world.services.get("options") if world is not None else None


def _line(player: GameObject, option: Option) -> str:
    value = get_option(player, option.name)
    shown = option.show(value) if value is not None else f"{option.default(player)} (default)"
    return f"  {option.name:14} {shown}"


async def cmd_config(ctx: CommandContext) -> None:
    """
    Show or change your settings. They belong to your account, so every
    character of yours shares them.

    Usage: config                    list them
           config <option>           show one
           config <option> <value>   change one
           config <option> default   back to the game's own

    Example:
        config pagelength 40
        config color off
        config palette r=m
    """
    service = _service()
    player = ctx.player
    words = (ctx.args or "").strip().split(None, 1)
    if service is None or not service.options:
        await ctx.session.send("This game has no settings.")
        return
    if not words:
        lines = ["Your settings (config <option> <value> changes one):"]
        for name in sorted(service.options):
            lines.append(_line(player, service.options[name]))
        ctx.session.send_paged("\n".join(lines))
        return
    option = service.get(words[0])
    if option is None:
        await ctx.session.send(f"There is no setting '{words[0]}'. Type config to list them.")
        return
    if len(words) == 1:
        await ctx.session.send(f"{_line(player, option).strip()}\n  {option.doc}")
        return
    text = words[1]
    if text.strip().lower() == "default":
        holder = clear_option(player, option.name)
    else:
        try:
            value = option.parse(text)
        except ValueError as err:
            await ctx.session.send(str(err))
            return
        holder = set_option(player, option.name, value)
    await save_object(ctx, holder)
    await ctx.session.send(_line(player, option).strip())


__all__ = ["Option", "OptionsService", "BASIC_OPTIONS", "offer_options", "cmd_config"]
