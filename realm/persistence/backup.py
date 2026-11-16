"""
Backing up and restoring the database (MUD_PLAN step 9).

A backup is SQLite's online backup API: a consistent copy taken while the
server runs and writes, by default to ``data/backups/<name>-<timestamp>.db``
beside the database. A restore copies a backup over the database, and
refuses while the server is running.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from realm.persistence.pidfile import refuse_if_running


def backups_dir(db_path: str | Path) -> Path:
    return Path(db_path).parent / "backups"


def default_backup_path(db_path: str | Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    return backups_dir(db_path) / f"{Path(db_path).stem}-{stamp}.db"


def _copy(source: Path, target: Path) -> None:
    src = sqlite3.connect(source)
    try:
        dst = sqlite3.connect(target)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def backup_database(db_path: str | Path, target: str | Path | None = None) -> Path:
    """Copy the live database to ``target`` (default: a new timestamped
    file in ``backups/`` beside it). Safe while the server writes."""
    source = Path(db_path)
    if not source.is_file():
        raise FileNotFoundError(f"No database at {source}")
    dest = Path(target) if target is not None else default_backup_path(source)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise FileExistsError(f"{dest} already exists")
    _copy(source, dest)
    return dest


def prune_backups(db_path: str | Path, keep: int) -> list[Path]:
    """Delete all but the newest ``keep`` default-named backups of
    ``db_path``; returns the deleted files."""
    if keep < 1:
        raise ValueError("keep must be at least 1")
    stem = Path(db_path).stem
    found = sorted(backups_dir(db_path).glob(f"{stem}-*.db"))
    doomed = found[:-keep]
    for path in doomed:
        path.unlink()
    return doomed


def restore_database(backup: str | Path, db_path: str | Path) -> None:
    """Replace the database at ``db_path`` with ``backup``. Refuses while
    the server runs on it, and refuses a file that is not a sound REALM
    database."""
    source = Path(backup)
    if not source.is_file():
        raise FileNotFoundError(f"No backup at {source}")
    refuse_if_running(db_path, "restore")
    conn = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError(f"{source} is damaged (integrity check failed)")
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "objects" not in tables:
            raise ValueError(f"{source} is not a REALM database (no objects table)")
    finally:
        conn.close()
    target = Path(db_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    _copy(source, target)


__all__ = ["backups_dir", "default_backup_path", "backup_database", "prune_backups",
           "restore_database"]
