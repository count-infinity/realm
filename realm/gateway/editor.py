"""
The line editor (MUD_PLAN 10.2): long text edited a line at a time.

``open_editor(session, text, title=..., on_save=...)`` makes the editor the
session's input handler. Every line typed is added to the text, kept as
typed (blank lines and indentation included), except the dot commands:

    .l            list the text with line numbers
    .d N          delete line N
    .i N text     insert a line before line N
    .r N text     replace line N
    .s            save
    .q            quit without saving
    .h            this help

``on_save(text)`` is the caller's: it writes the text where it belongs (an
attribute, a description, a letter) and says what happened: True, saved
(the editor closes); False, saved but kept open (a softcode attribute that
will not run, to be fixed); None, not saved (refused, or a letter with no
body). ``@edit``, ``@desc`` and ``mail`` open it.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.gateway.session import Session

#: The most lines one text may hold.
MAX_LINES = 1000

HELP = """Editor commands (any other line is added to the text):
  .l            list the text with line numbers
  .d N          delete line N
  .i N text     insert a line before line N
  .r N text     replace line N
  .s            save
  .q            quit without saving
  .h            this help"""

_NUMBERED = re.compile(r"^\.([dir])\s+(\d+)(?: (.*))?$", re.DOTALL)


class LineEditor:
    """The editor's state and its input handler (``__call__``)."""

    def __init__(self, session: Session, text: str, *, title: str,
                 on_save: Callable[[str], Awaitable[bool | None]]) -> None:
        self.session = session
        self.lines: list[str] = text.split("\n") if text else []
        self.title = title
        self.on_save = on_save
        #: whether the text on screen is the text last saved
        self.saved = True

    async def __call__(self, _session: Session, line: str) -> bool:
        command = line.strip()
        if not command.startswith("."):
            self._append(line)
            return True
        if command == ".l":
            self._list()
        elif command == ".s":
            await self._save()
        elif command == ".q":
            self.close()
            self.session.send_nowait(
                "Editor closed; nothing saved." if not self.saved
                else "Editor closed.")
        elif command == ".h":
            self.session.send_nowait(HELP)
        else:
            self._numbered(line.lstrip())
        return True

    def _append(self, line: str) -> None:
        if len(self.lines) >= MAX_LINES:
            self.session.send_nowait(f"The text is full ({MAX_LINES} lines).")
            return
        self.lines.append(line)
        self.saved = False

    def _list(self) -> None:
        if not self.lines:
            self.session.send_nowait(f"{self.title} is empty.")
            return
        width = len(str(len(self.lines)))
        self.session.send_paged("\n".join(
            f"{n:>{width}}: {text}" for n, text in enumerate(self.lines, start=1)))

    def _numbered(self, line: str) -> None:
        match = _NUMBERED.match(line)
        if match is None:
            self.session.send_nowait(
                f"Unknown editor command '{line.split()[0]}'. Type .h for help.")
            return
        op, number, text = match[1], int(match[2]), match[3] or ""
        last = len(self.lines) + (1 if op == "i" else 0)
        if not 1 <= number <= last:
            self.session.send_nowait(
                f"There is no line {number}; the text has {len(self.lines)}.")
            return
        if op == "d":
            del self.lines[number - 1]
            self.session.send_nowait(f"Deleted line {number}.")
        elif op == "i":
            if len(self.lines) >= MAX_LINES:
                self.session.send_nowait(f"The text is full ({MAX_LINES} lines).")
                return
            self.lines.insert(number - 1, text)
            self.session.send_nowait(f"Inserted line {number}.")
        else:
            self.lines[number - 1] = text
            self.session.send_nowait(f"Replaced line {number}.")
        self.saved = False

    async def _save(self) -> None:
        outcome = await self.on_save("\n".join(self.lines))
        if outcome is True:
            self.close()
        elif outcome is False:
            self.saved = True

    def close(self) -> None:
        """Give the session's input back to commands."""
        if self.session.input_handler is self:
            self.session.input_handler = None
            self.session.raw_lines = False


def open_editor(session: Session, text: str, *, title: str,
                on_save: Callable[[str], Awaitable[bool | None]]) -> LineEditor | None:
    """Edit ``text`` on ``session``; None (with a notice) when the session is
    already answering a prompt or editing something else."""
    if session.input_handler is not None:
        session.send_nowait("Finish what you are doing first.")
        return None
    editor = LineEditor(session, text, title=title, on_save=on_save)
    session.input_handler = editor
    session.raw_lines = True
    count = len(editor.lines)
    session.send_nowait(
        f"Editing {title} ({count} line{'s' if count != 1 else ''}). Type lines to add "
        f"them; .l lists, .s saves, .q quits, .h helps.")
    return editor


__all__ = ["LineEditor", "open_editor", "MAX_LINES", "HELP"]
