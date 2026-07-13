# Quick Start

The five-minute version.

```bash
git clone https://github.com/realm-mud/realm.git
python -m venv venv && source venv/bin/activate
pip install -e realm

realm init mygame && cd mygame
realm start
```

In another terminal:

```bash
telnet localhost 4000
```

```text
create Keeper secret123        # first character = superuser
look                           # The Void — your empty Limbo
@dig The Garden = north, south # your first room
north
@desc here = Roses climb a broken trellis.
look
```

You're building. For the guided version with explanations, start at
[Installation](installation.md); to build a full playable adventure,
jump to [the tutorial](../tutorial/index.md).
