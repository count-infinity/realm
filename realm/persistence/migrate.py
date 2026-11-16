"""
Schema migrations (``realm migrate``).

The database's schema version is ``PRAGMA user_version``.
``PersistenceManager.initialize`` refuses a database older than
``SCHEMA_VERSION`` and tells the operator to run ``realm migrate``, which
runs the steps below in order, each in its own transaction, stamping the
version after each. Changes to objects (6.2's accounts conversion) are
boot steps, not migrations: these change the tables.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from pathlib import Path

from realm.persistence.manager import PersistenceManager, effective_version
from realm.persistence.pidfile import refuse_if_running

logger = logging.getLogger(__name__)


def _parent_index(conn: sqlite3.Connection) -> None:
    """v2: index ``parent_id`` (children of a prototype are looked up by it)."""
    conn.execute("CREATE INDEX IF NOT EXISTS idx_objects_parent ON objects(parent_id)")


#: version -> the step that brings a database from the version before it.
MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {
    2: _parent_index,
}


def stored_version(conn: sqlite3.Connection) -> int:
    stamped = int(conn.execute("PRAGMA user_version").fetchone()[0])
    has_objects = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='objects'").fetchone()
    return effective_version(stamped, has_objects is not None)


def pending(version: int) -> list[int]:
    """The migration versions a database at ``version`` still needs."""
    return [v for v in sorted(MIGRATIONS) if v > version]


def migrate(db_path: str | Path) -> list[int]:
    """Bring the database at ``db_path`` up to ``SCHEMA_VERSION``; returns
    the versions applied (empty when it was current). Refuses while the
    server is running on it."""
    path = Path(db_path)
    if not path.is_file():
        raise FileNotFoundError(f"No database at {path}")
    refuse_if_running(path, "migrate")
    conn = sqlite3.connect(path, isolation_level=None)
    try:
        version = stored_version(conn)
        if version > PersistenceManager.SCHEMA_VERSION:
            raise RuntimeError(f"Database schema v{version} is newer than this REALM "
                               f"(v{PersistenceManager.SCHEMA_VERSION}): upgrade the engine.")
        done = []
        for target in pending(version):
            conn.execute("BEGIN")
            try:
                MIGRATIONS[target](conn)
                conn.execute(f"PRAGMA user_version = {target}")
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            logger.info(f"Migrated {path} to schema v{target}")
            done.append(target)
        return done
    finally:
        conn.close()


__all__ = ["MIGRATIONS", "stored_version", "pending", "migrate"]
