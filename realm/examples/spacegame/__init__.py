"""
REALM Space Game — a reference game project.

A GURPS-flavored space station, built the way REALM wants games built:

- **World** — the area file ``data/areas/station.json`` (imported at first
  boot; regenerate it with ``scripts/build_spacegame_area.py``).
- **Classes, skills, gear** — the built-in ``gurps-scifi`` content pack
  (``realm/packs/gurps-scifi``), imported like any ``@pack``.
- **Ships** — ``ships.py``: ship templates and a wrapper; a ship's shields,
  armor and hull are pools, so stock damage reaches it (see that file's
  note).

``realm init --template spacegame`` scaffolds a game from this directory.
"""

from realm.examples.spacegame.ships import Spaceship

__all__ = ['Spaceship']
