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

MARKER = '|'
_FG = {c: 30 + i for i, c in enumerate('xrgybmcw')}


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
    segments: list[tuple[Style, str]] = []
    style = DEFAULT_STYLE
    buf: list[str] = []
    i, n = 0, len(text)

    def flush() -> None:
        if buf:
            segments.append((style, ''.join(buf)))
            buf.clear()

    while i < n:
        ch = text[i]
        if ch != MARKER:
            buf.append(ch)
            i += 1
            continue
        if i + 1 >= n:          # dangling pipe: literal
            buf.append(MARKER)
            break
        code = text[i + 1]
        if code == MARKER:      # || escape
            buf.append(MARKER)
            i += 2
            continue
        if code == 'n':
            flush()
            style = DEFAULT_STYLE
            i += 2
            continue
        if code == '/':
            buf.append('\n')
            i += 2
            continue
        if code == '[' and i + 2 < n and text[i + 2].lower() in _FG:
            flush()
            style = replace(style, bg=text[i + 2])
            i += 3
            continue
        if code.lower() in _FG:
            flush()
            style = replace(style, fg=code)
            i += 2
            continue
        if code in 'huiv':
            flush()
            style = replace(style,
                            bold=style.bold or code == 'h',
                            underline=style.underline or code == 'u',
                            italic=style.italic or code == 'i',
                            reverse=style.reverse or code == 'v')
            i += 2
            continue
        # Unknown code: literal, typo stays visible.
        buf.append(MARKER)
        buf.append(code)
        i += 2
    flush()
    return segments


def strip(text: str) -> str:
    """The text with all markup removed."""
    if MARKER not in text:
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
    if style.is_default():
        return ''
    parts = []
    if style.fg:
        parts.append(MARKER + style.fg)
    if style.bg:
        parts.append(MARKER + '[' + style.bg)
    for flag, code in ((style.bold, 'h'), (style.underline, 'u'),
                       (style.italic, 'i'), (style.reverse, 'v')):
        if flag:
            parts.append(MARKER + code)
    return ''.join(parts)


def escape(text: str) -> str:
    """Escape player-provided text so pipes render literally."""
    return text.replace(MARKER, MARKER + MARKER)


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


def to_ansi(text: str) -> str:
    """
    Render markup as terminal escape codes — MINIMALLY: adjacent
    same-style text emits no codes, each style change emits one
    combined sequence, and a single reset trails the message iff any
    styling was used (no color bleed into the next prompt).
    """
    if MARKER not in text:
        return text
    out: list[str] = []
    previous = DEFAULT_STYLE
    styled = False
    for style, seg in parse(text):
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


__all__ = ["Style", "DEFAULT_STYLE", "parse", "strip", "visible_len",
           "pad", "truncate", "escape", "render_markup", "to_ansi"]
