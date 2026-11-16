# Protocol Overview

REALM supports multiple connection protocols through a clean abstraction layer.

## Supported Protocols

| Protocol | Port | Status | Use Case |
|----------|------|--------|----------|
| Telnet | 4000 | Stable | Traditional MUD clients |
| WebSocket | 4001 | Stable | Web clients, modern apps |
| Browser client | 4001 | Stable | Playing from a browser, served beside WebSocket |
| Custom | - | Guide | Godot, Unity, etc. |

## Protocol Architecture

All protocols follow the same pattern:

```
Client ──► Protocol Handler ──► SessionManager ──► Game Logic
                │                      │
                │                      ▼
                │               Session Object
                │                      │
                └──── writer ──────────┘
```

1. Protocol receives connection
2. Protocol creates a **writer function**
3. Protocol calls `session_manager.create_session(writer=...)`
4. SessionManager creates session, runs callbacks, auto-flushes
5. Protocol handles input loop, calling `on_command()`
6. On disconnect, protocol calls `destroy_session()`

## Key Principle: Writer First

The writer function must be passed to `create_session()` before callbacks run:

```python
# Correct: writer passed to create_session
session = await session_manager.create_session(
    protocol="myprotocol",
    writer=my_writer,  # <-- Available for welcome screen flush
)

# Incorrect: writer set after
session = await session_manager.create_session(protocol="myprotocol")
session.set_writer(my_writer)  # <-- Too late! Welcome screen lost
```

## Protocol Files

```
realm/gateway/
├── session.py    # Session and SessionManager (protocol-agnostic)
├── telnet.py     # Telnet protocol implementation
└── websocket.py  # WebSocket protocol implementation
realm/web/
└── index.html    # The browser client (HTML, CSS and JavaScript in one page)
```

## Next Steps

- [Adding a Protocol](adding-protocol.md) - Step-by-step guide
- [Session Lifecycle](../architecture/sessions.md) - How sessions work

## Structured data (GMCP / OOB)

Protocols may install an out-of-band writer
(`session.set_oob_writer`) to carry structured data alongside text.
Telnet negotiates **GMCP** (room info, character vitals, and anything
softcode sends via `oob()`); WebSocket delivers the same packages as
JSON envelopes. A protocol without an OOB writer simply never
receives structured sends — games never need to check.

`Char.Vitals` is sent with the prompt whenever one of the player's pools
changed since the last one sent: every declared pool, plus the damage and
vital pools, as `name` and `max_name` (`{"hp": 9, "max_hp": 12, "mana": 3,
"max_mana": 5}`). A combat round adds its own (`{hp, max_hp, round}`).

## The browser client

REALM ships a browser client: one page of HTML, CSS and plain JavaScript
(`realm/web/index.html`, no build step and nothing fetched from elsewhere),
served by the WebSocket server. Someone with only a browser can play.

Turn it on in `config.py`:

```python
ENABLE_WEBSOCKET = True     # the WebSocket server (needs aiohttp)
WEB_CLIENT = True           # serve the client at / on the same port
WEBSOCKET_PORT = 4001
```

The WebSocket server needs aiohttp: `pip install 'realm[websocket]'`.
Start the game and open `http://<host>:4001/`. The page connects to `/ws`
beside it, so it keeps working behind a reverse proxy that serves the
game under a path (`https://example.org/mud/` connects to
`wss://example.org/mud/ws`). With `WEB_CLIENT` set and `ENABLE_WEBSOCKET`
off, the server logs a WARNING at start that says to turn the WebSocket
server on.

| Setting | Default | What it does |
|---|---|---|
| `ENABLE_WEBSOCKET` | `False` | Run the WebSocket server. |
| `WEB_CLIENT` | `False` | Serve the browser client at `/` (needs `ENABLE_WEBSOCKET`). |
| `WEBSOCKET_HOST` | `"0.0.0.0"` | The address both listen on. |
| `WEBSOCKET_PORT` | `4001` | The port both listen on. |
| `GAME_NAME` | `"REALM"` | The page's title and heading. |

What the page does:

- Shows the game's output with its colors, in a scrollback that follows
  new output unless you have scrolled back to read.
- Keeps the prompt in a fixed line above the input, and draws
  `Char.Vitals` as bars (one for each `name` with a `max_name`). The
  header shows the room you are in (`Room.Info`).
- Remembers what you typed: up and down arrows walk the history, Escape
  clears the line, Page Up and Page Down scroll the output. Lines that
  carry a password (`connect`, `create`, `password`) are echoed masked and
  not remembered.
- Sends a blank line when you press enter on an empty input, which turns
  the pager's page. It reports the output area's size in characters
  (`resize`), so the pager holds long output to what fits on your screen;
  `config pagelength 0` turns paging off.
- Works at phone width and on a desktop, and follows the system's light or
  dark theme.
- Is built for screen readers: the input has a label and keeps the focus
  (clicking the output or typing anywhere returns to it), and the output
  is a live region (`role="log"`, `aria-live="polite"`); your own commands
  are not read back.

The player's display options apply to the browser client as they do to
telnet, before the text leaves the server: `config color off` sends plain
text, `config screenreader on` sends plain text without the lines drawn
only for looks, and `config palette r=m` swaps the colors in the styled
segments.

### The frames

The WebSocket protocol the page speaks, for anyone writing their own
client. From the server:

| Frame | Meaning |
|---|---|
| a plain string | text to show |
| `{"type": "text", "text": ..., "segments": [[style, text], ...]}` | styled text; `text` is the same without styles |
| `{"type": "text", "text": ...}` | text that starts with `{` (only JSON frames do) |
| `{"type": "prompt", "text": ...[, "segments": ...]}` | the prompt |
| `{"type": "oob", "package": ..., "data": {...}}` | out-of-band data (GMCP's packages) |
| `{"type": "pong"}` | the answer to a ping |

A style is a short key: a color letter (`r`, or `R` for bright), `[` and
a background letter, then `;` and the flags `h` (bold), `u` (underline),
`i` (italic), `v` (reverse): `R[b;hu` is bold, underlined bright red on
blue; an empty key is the default style.

To the server: a line of input as a plain string (or `{"type": "command",
"command": ...}`); `{"type": "resize", "width": ..., "height": ...}` in
characters; `{"type": "oob", "package": ..., "data": ...}` (remembered in
`session.oob_supports`, like inbound GMCP); `{"type": "ping"}`.

