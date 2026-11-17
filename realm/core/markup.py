"""
Color as inline markup in plain strings, rendered once at the edge.

There is deliberately NO string class here (the Evennia ANSIString
lesson): color lives as ``|``-markup inside ordinary ``str`` — the
whole pipeline (actions, per-looker formatting, softcode, queues) is
markup-blind, and each protocol renders exactly once at write time.

Syntax (one character after the pipe):

    |r |g |y |b |m |c |w |x    dark foreground (x = black/grey)
    |R |G |Y |B |M |C |W |X    bright foreground
    |[r ... |[R                background (dark / bright)
    |h  |u  |i  |v             bold, underline, italic, reverse video
    |n                         reset everything
    |/                         a newline (usable in @set one-liners)
    ||                         a literal pipe

Unknown codes render literally (typos stay visible). The parser reads
one char after ``|`` (two for ``|[x``), so extensions like ``|#F00``
truecolor can slot in later without breaking this syntax.

Only fixed-width UI code (tables, bars) ever cares about raw-vs-visible
length — those four helpers live here (visible_len/strip/pad/truncate)
instead of being smeared across a string subclass.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from realm.core.world import setting

_FG = {c: 30 + i for i, c in enumerate('xrgybmcw')}


def marker() -> str:
    """The markup marker: the MARKUP_MARKER setting, '|' by default, '~'
    or similar for worlds that want literal pipes in their prose (ASCII
    tables). Any length ('%%', '@@@'); a doubled marker is a literal.
    Every scanner/emitter here reads it at call time; engine code emits
    through wrap() so a changed marker never leaks stale literals."""
    return setting("MARKUP_MARKER")


def wrap(codes: str, text: str) -> str:
    """Color ``text`` with markup ``codes``, closing with a reset —
    the one way engine code should emit markup, so it always uses the
    configured marker: ``wrap('c', name)`` == ``|c<name>|n``."""
    mk = marker()
    return f"{mk}{codes}{text}{mk}n"


@dataclass(frozen=True)
class Style:
    """One text style state. ``fg``/``bg`` are code letters or None."""

    fg: str | None = None       # 'r'..'w'/'x', uppercase = bright
    bg: str | None = None
    bold: bool = False
    underline: bool = False
    italic: bool = False
    reverse: bool = False

    def is_default(self) -> bool:
        return self == DEFAULT_STYLE

    def key(self) -> str:
        """Compact, stable id for protocol payloads (e.g. 'R[b;hu')."""
        parts = []
        if self.fg:
            parts.append(self.fg)
        if self.bg:
            parts.append('[' + self.bg)
        flags = ('h' if self.bold else '') + \
                ('u' if self.underline else '') + \
                ('i' if self.italic else '') + \
                ('v' if self.reverse else '')
        if flags:
            parts.append(';' + flags)
        return ''.join(parts)


DEFAULT_STYLE = Style()


def parse(text: str) -> list[tuple[Style, str]]:
    """
    Parse markup into ``[(Style, text), ...]`` segments.

    Splitting a marked-up string anywhere and parsing the halves is
    always safe: a dangling ``|`` at end-of-string renders literally,
    and styles simply restart at default in the second half.
    """
    mk = marker()
    segments: list[tuple[Style, str]] = []
    style = DEFAULT_STYLE
    buf: list[str] = []
    i, n = 0, len(text)

    def flush() -> None:
        if buf:
            segments.append((style, ''.join(buf)))
            buf.clear()

    # The marker may be any length (a game setting); offsets are all
    # relative to it. mk_len == 1 with the default '|'.
    mk_len = len(mk)
    while i < n:
        if not text.startswith(mk, i):
            buf.append(text[i])
            i += 1
            continue
        if i + mk_len >= n:     # dangling marker: literal
            buf.append(mk)
            break
        if text.startswith(mk, i + mk_len):   # doubled marker: escape
            buf.append(mk)
            i += 2 * mk_len
            continue
        code = text[i + mk_len]
        if code == 'n':
            flush()
            style = DEFAULT_STYLE
            i += mk_len + 1
            continue
        if code == '/':
            buf.append('\n')
            i += mk_len + 1
            continue
        if (code == '[' and i + mk_len + 1 < n
                and text[i + mk_len + 1].lower() in _FG):
            flush()
            style = replace(style, bg=text[i + mk_len + 1])
            i += mk_len + 2
            continue
        if code.lower() in _FG:
            flush()
            style = replace(style, fg=code)
            i += mk_len + 1
            continue
        if code in 'huiv':
            flush()
            style = replace(style,
                            bold=style.bold or code == 'h',
                            underline=style.underline or code == 'u',
                            italic=style.italic or code == 'i',
                            reverse=style.reverse or code == 'v')
            i += mk_len + 1
            continue
        # Unknown code: literal, typo stays visible.
        buf.append(mk)
        buf.append(code)
        i += mk_len + 1
    flush()
    return segments


def capitalize(text: str) -> str:
    """``text`` with its first visible character upper-cased, as ROM's
    ``act()`` capitalizes the line it sends ("the cityguard arrives." ->
    "The cityguard arrives."). Leading style codes are stepped over (never
    themselves capitalized); only the very first character of the text
    changes, not each line, and only when it is a letter."""
    mk = marker()
    mk_len = len(mk)
    i, n = 0, len(text)
    while text.startswith(mk, i):
        if i + mk_len >= n or text.startswith(mk, i + mk_len):
            return text                     # a dangling or a literal marker
        code = text[i + mk_len]
        if code == '[' and i + mk_len + 1 < n and text[i + mk_len + 1].lower() in _FG:
            i += mk_len + 2
        elif code == 'n' or code.lower() in _FG or code in 'huiv':
            i += mk_len + 1
        else:
            return text                     # |/ (a newline) or an unknown code
    if i < n and text[i].islower():
        return text[:i] + text[i].upper() + text[i + 1:]
    return text


def strip(text: str) -> str:
    """The text with all markup removed."""
    mk = marker()
    if mk not in text:
        return text
    return ''.join(seg for _style, seg in parse(text))


def visible_len(text: str) -> int:
    return len(strip(text))


def pad(text: str, width: int, align: str = 'left', fill: str = ' ') -> str:
    """Pad to a VISIBLE width (markup costs nothing)."""
    gap = width - visible_len(text)
    if gap <= 0:
        return text
    if align == 'right':
        return fill * gap + text
    if align == 'center':
        left = gap // 2
        return fill * left + text + fill * (gap - left)
    return text + fill * gap


def truncate(text: str, width: int) -> str:
    """Cut to a visible width without splitting a marker; styles reset."""
    if visible_len(text) <= width:
        return text
    out: list[str] = []
    used = 0
    for style, seg in parse(text):
        take = seg[:max(0, width - used)]
        if take:
            out.append(render_markup(style) + take)
            used += len(take)
        if used >= width:
            break
    out.append('|n')
    return ''.join(out)


def render_markup(style: Style) -> str:
    """The markup string that reproduces a Style (used by truncate)."""
    mk = marker()
    if style.is_default():
        return ''
    parts = []
    if style.fg:
        parts.append(mk + style.fg)
    if style.bg:
        parts.append(mk + '[' + style.bg)
    for flag, code in ((style.bold, 'h'), (style.underline, 'u'),
                       (style.italic, 'i'), (style.reverse, 'v')):
        if flag:
            parts.append(mk + code)
    return ''.join(parts)


def escape(text: str) -> str:
    """Escape player-provided text so pipes render literally."""
    mk = marker()
    return text.replace(mk, mk + mk)



# --- Terminal (SGR) encoding ---------------------------------------------------

def _sgr_params(style: Style) -> str:
    params = []
    if style.bold:
        params.append('1')
    if style.italic:
        params.append('3')
    if style.underline:
        params.append('4')
    if style.reverse:
        params.append('7')
    if style.fg:
        base = _FG[style.fg.lower()]
        params.append(str(base + 60 if style.fg.isupper() else base))
    if style.bg:
        base = _FG[style.bg.lower()] + 10
        params.append(str(base + 60 if style.bg.isupper() else base))
    return ';'.join(params)


def _recolor(code: str | None, palette: dict[str, str]) -> str | None:
    """A color letter through a player's palette; brightness (case) kept."""
    if code is None:
        return None
    swapped = palette.get(code.lower())
    if swapped is None:
        return code
    return swapped.upper() if code.isupper() else swapped.lower()


def recolor(style: Style, palette: dict[str, str] | None) -> Style:
    """``style`` through one reader's ``palette`` (``{'r': 'm'}``: red shows
    as magenta, bright red as bright magenta), foreground and background."""
    if not palette:
        return style
    return replace(style, fg=_recolor(style.fg, palette), bg=_recolor(style.bg, palette))


def to_ansi(text: str, palette: dict[str, str] | None = None) -> str:
    """
    Render markup as terminal escape codes — MINIMALLY: adjacent
    same-style text emits no codes, each style change emits one
    combined sequence, and a single reset trails the message iff any
    styling was used (no color bleed into the next prompt).

    ``palette`` swaps colors for one reader (a player's ``palette``
    option, ``{'r': 'm'}``: red shows as magenta, bright red as bright
    magenta), foreground and background alike.
    """
    mk = marker()
    if mk not in text:
        return text
    out: list[str] = []
    previous = DEFAULT_STYLE
    styled = False
    for style, seg in parse(text):
        style = recolor(style, palette)
        if style != previous:
            if style.is_default():
                out.append('\x1b[0m')
            else:
                out.append(f'\x1b[0;{_sgr_params(style)}m')
                styled = True
            previous = style
        out.append(seg)
    if styled and not previous.is_default():
        out.append('\x1b[0m')
    return ''.join(out)


#: Characters a line made only for looks is drawn with (rules, table borders).
DECORATION = frozenset("-=_*~+#|.:")


def undecorate(text: str) -> str:
    """``text`` without its decoration lines (``=====``, ``+---+---+``):
    lines of three or more characters drawn only from ``DECORATION``, which a
    screen reader would read out symbol by symbol (a player's
    ``screenreader`` option). Markup is ignored when judging a line."""
    kept = []
    for line in text.split("\n"):
        visible = strip(line).replace(" ", "")
        if len(visible) >= 3 and set(visible) <= DECORATION:
            continue
        kept.append(line)
    return "\n".join(kept)


#: The color letters a palette may swap.
COLOR_LETTERS = "xrgybmcw"


__all__ = ["Style", "DEFAULT_STYLE", "parse", "strip", "visible_len",
           "pad", "truncate", "escape", "render_markup", "recolor", "to_ansi", "undecorate",
           "DECORATION", "COLOR_LETTERS"]
