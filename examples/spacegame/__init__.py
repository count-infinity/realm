"""
REALM Space Game — a reference game project.

A GURPS-flavored space station, built the way REALM wants games built:

- **World** — the area file ``data/areas/station.json`` (imported at first
  boot; regenerate it with ``scripts/build_spacegame_area.py``).
- **Classes, skills, gear** — the built-in ``gurps-scifi`` content pack
  (``realm/packs/gurps-scifi``), imported like any ``@pack``.
- **Ships** — ``ships.py``, the one subsystem kept in Python because its
  layered shields/armor/hull damage model does not map onto the character
  ``hp`` track (see that file's note).

``realm init --template spacegame`` scaffolds a game from this directory.
"""

from examples.spacegame.ships import Spaceship

__all__ = ['Spaceship']
