"""
REALM configuration system.

``Settings`` declares every config key and its default; ``load_config`` reads
a game's config.py into one.
"""

from realm.config.loader import Settings, load_config

__all__ = ['load_config', 'Settings']
