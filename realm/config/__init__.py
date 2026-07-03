"""
REALM configuration system.

Provides defaults and loading of user configuration from config.py.
"""

from realm.config.defaults import DEFAULT_SETTINGS
from realm.config.loader import Settings, load_config

__all__ = ['DEFAULT_SETTINGS', 'load_config', 'Settings']
