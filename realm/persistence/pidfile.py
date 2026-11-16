"""
The running server's pid file, next to its database (``game.db.pid``).

The server writes it at start and removes it at stop; ``realm restore``
and ``realm migrate`` refuse while it names a live process. A pid file
left by a crash names a dead process and is ignored.
"""

from __future__ import annotations

import os
from pathlib import Path


class ServerRunningError(RuntimeError):
    """The database is in use by a running server."""


def pid_file(db_path: str | Path) -> Path:
    db = Path(db_path)
    return db.with_name(db.name + ".pid")


def running_pid(db_path: str | Path) -> int | None:
    """The pid of the live server using ``db_path``, else None."""
    path = pid_file(db_path)
    try:
        pid = int(path.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    except PermissionError:
        return pid                    # alive, someone else's
    return pid


def refuse_if_running(db_path: str | Path, doing: str) -> None:
    pid = running_pid(db_path)
    if pid is not None:
        raise ServerRunningError(f"The server is running (pid {pid}) on {db_path}: "
                            f"stop it before you {doing}.")


def write_pid_file(db_path: str | Path) -> Path:
    path = pid_file(db_path)
    path.write_text(str(os.getpid()))
    return path


def remove_pid_file(db_path: str | Path) -> None:
    path = pid_file(db_path)
    try:
        if int(path.read_text().strip()) == os.getpid():
            path.unlink()
    except (FileNotFoundError, ValueError):
        pass


__all__ = ["ServerRunningError", "pid_file", "running_pid", "refuse_if_running",
           "write_pid_file", "remove_pid_file"]
