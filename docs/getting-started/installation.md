# Installation

REALM needs Python 3.11 or newer. That's the whole requirements list —
the engine is asyncio + SQLite, no external database, no message
broker.

## From git (for now)

```bash
git clone https://github.com/realm-mud/realm.git
cd realm
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -e .
```

`pip install -e .` gives you the `realm` command and lets you pull
engine updates with a plain `git pull`.

!!! note "Later: pip"
    Once REALM is published this whole page becomes
    `pip install realm`. Everything after this point already works
    exactly as it will then.

## Check it worked

```bash
realm --help
```

You should see the `init` / `start` subcommands. If `realm` isn't
found, your virtualenv isn't active.

## For contributors (optional)

Tests, linting, and this documentation site:

```bash
pip install -e ".[dev]"
pytest                # ~800 tests, a couple of seconds
mkdocs serve          # these docs at http://127.0.0.1:8000
```

Docs are plain Markdown in `docs/` — readable on GitHub as-is;
`mkdocs build` produces a static HTML site you can host anywhere.

Next: [Your First Game](first-game.md).
