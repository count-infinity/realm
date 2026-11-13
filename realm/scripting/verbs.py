"""
Script verbs: the one softcode command-line dialect.

A softcode attribute is either one command line (``say Hello, %n!``) or
Python that emits command lines (``say("hi")``, ``cmd("drop key")``). Both
end in ``ScriptEngine._run_script_command``, and this registry decides which
lines exist, for every consumer at once:

- the classifier (``is_command_line``): is this attribute a command line?
- the executor: ``match(line)`` finds the verb and the rest of the line;
- the validator (``triggers.validate_script``): a line naming an unknown
  verb is reported at ``@set`` time;
- the Python sugar: verbs registered with ``sugar=True`` become functions
  in a script (``say(text)``), and ``cmd(line)`` refuses an unknown verb.

Verbs come from features (``feature.script_verb``); ``wait`` and
``trigger`` belong to the kernel. The installed set is the live world's
(``FeatureSet.install_registries``); with no world it is ``CLASSIC``.

A handler is ``async (engine, executor, rest_of_line) -> None``.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)

ScriptVerbHandler = Callable[[Any, "GameObject", str], Awaitable[None]]


@dataclass(frozen=True)
class ScriptVerb:
    """One script command."""

    name: str                       # "say"
    handler: ScriptVerbHandler      # (engine, executor, rest_of_line)
    aliases: tuple[str, ...] = ()   # ("take",) for get
    token: str | None = None        # one leading character: ":" for pose
    sugar: bool = False             # also expose name(text) inside Python scripts
    owner: str = "kernel"
    doc: str = ""


class ScriptVerbs:
    """A table of script verbs, keyed by name, alias and token."""

    def __init__(self) -> None:
        self._by_word: dict[str, ScriptVerb] = {}
        self._by_token: dict[str, ScriptVerb] = {}
        self._verbs: dict[str, ScriptVerb] = {}

    def register(self, verb: ScriptVerb, *, replace: bool = False) -> None:
        """Add ``verb``. A name, alias or token already taken by another verb
        raises FeatureError unless ``replace``."""
        from realm.features import FeatureError
        words = [verb.name.lower(), *(a.lower() for a in verb.aliases)]
        for word in words:
            held = self._by_word.get(word)
            if held is not None and held is not verb and not replace:
                raise FeatureError(
                    f"script verb {word!r} is declared by both {held.owner!r} and "
                    f"{verb.owner!r}. Rename one, or pass replace=True.")
        if verb.token is not None:
            held = self._by_token.get(verb.token)
            if held is not None and held is not verb and not replace:
                raise FeatureError(
                    f"script verb token {verb.token!r} is declared by both "
                    f"{held.owner!r} and {verb.owner!r}.")
            self._by_token[verb.token] = verb
        for word in words:
            self._by_word[word] = verb
        self._verbs[verb.name.lower()] = verb

    def match(self, line: str) -> tuple[ScriptVerb, str] | None:
        """The verb a line invokes and the rest of the line, or None.

        The first word is compared (case-insensitively) with names and
        aliases, then the first character with tokens. A verb that takes
        no arguments matches its bare word."""
        line = line.strip()
        if not line:
            return None
        parts = line.split(None, 1)
        verb = self._by_word.get(parts[0].lower())
        if verb is not None:
            return verb, parts[1] if len(parts) > 1 else ""
        verb = self._by_token.get(line[0])
        if verb is not None:
            return verb, line[1:]
        return None

    def is_command_line(self, code: str) -> bool:
        """A single non-empty line that ``match`` accepts."""
        lines = code.strip().split('\n')
        return len(lines) == 1 and self.match(lines[0]) is not None

    def names(self) -> list[str]:
        return sorted(self._verbs)

    def verbs(self) -> list[ScriptVerb]:
        return [self._verbs[n] for n in self.names()]

    def sugar(self) -> list[ScriptVerb]:
        return [v for v in self.verbs() if v.sugar]


_installed: ScriptVerbs | None = None


def installed() -> ScriptVerbs:
    """The live world's verbs (the CLASSIC set when no world is live)."""
    if _installed is None:
        from realm.features import ensure_registries
        ensure_registries()
    return _installed if _installed is not None else ScriptVerbs()


def install(verbs: list[tuple[ScriptVerb, bool]]) -> None:
    """Replace the installed table with the kernel verbs plus ``(verb,
    replace)`` declarations (``FeatureSet.install_registries``)."""
    global _installed
    table = ScriptVerbs()
    for verb in kernel_verbs():
        table.register(verb)
    for verb, replace in verbs:
        table.register(verb, replace=replace)
    _installed = table


# --- kernel verbs ------------------------------------------------------------

async def _wait(engine, executor: GameObject, rest: str) -> None:
    """``wait <seconds> <command>``: a one-shot, fired after the delay."""
    parts = rest.split(None, 1)
    if len(parts) != 2:
        return
    try:
        seconds = float(parts[0])
    except ValueError:
        return
    engine.schedule_wait(executor, seconds, parts[1])


async def _trigger(engine, executor: GameObject, rest: str) -> None:
    """``trigger [obj/]attr``: run a script attribute (self or a neighbor)."""
    await engine._scripted_trigger(executor, rest.strip())


def kernel_verbs() -> list[ScriptVerb]:
    return [
        ScriptVerb("wait", _wait, doc="wait <seconds> <command>: run a command later"),
        ScriptVerb("trigger", _trigger, aliases=("@tr",), sugar=True,
                   doc="trigger [object/]attribute: run a script attribute"),
    ]


__all__ = ["ScriptVerb", "ScriptVerbs", "ScriptVerbHandler", "installed", "install",
           "kernel_verbs"]
