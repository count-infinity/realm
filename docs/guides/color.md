# Color

Color is inline markup in ordinary strings — type it anywhere text
goes: descriptions, `say`, softcode, `@detail` lines. It renders at
the protocol edge (ANSI for telnet, structured segments for
WebSocket, stripped for `color off`), so the engine never juggles
escape codes internally.

## Markup

| Code | Meaning |
|---|---|
| `\|r \|g \|y \|b \|m \|c \|w \|x` | foreground (red, green, yellow, blue, magenta, cyan, white, black) |
| `\|R \|G ...` | bright foreground |
| `\|[r` / `\|[R` | background (dark / bright) |
| `\|h \|u \|i` | bold, underline, italic |
| `\|n` | reset |
| `\|\|` | a literal pipe |

```text
@desc here = The |csea|n stretches to a |Rburning|n horizon.
say My |gemerald|n ring!
```

Unknown codes render literally (typos stay visible). Players toggle
with `color on` / `color off`.

## From softcode

PennMUSH-style, if you prefer letters to pipes:

```python
ansi('rh', 'My thing')     # bright red — returns '|RMy thing|n'
ansi('gR', 'alert')        # green on red background
escape(player_input)       # make pipes in untrusted text literal
```

Both produce plain marked-up strings — mix freely with f-string logic
in `[[...]]` blocks.

## For engine/UI code

`realm.core.markup` owns the semantics: `strip`, `visible_len`,
`pad`/`truncate` (visible-width aware — the only place raw-vs-visible
matters), `to_ansi` (minimal SGR: codes only on style change, one
trailing reset). There is deliberately no ANSIString class — strings
stay `str` everywhere, and splitting marked-up text anywhere is safe.
