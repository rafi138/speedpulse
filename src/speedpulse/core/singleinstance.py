"""Single-instance enforcement via an advisory OS file lock.

``flock`` (POSIX) and ``msvcrt.locking`` (Windows) both release
automatically when the process dies, so there are no stale locks to
clean up. The lock file itself is deliberately *not* deleted on release:
unlinking it creates the classic race where a waiting instance holds a
lock on an unlinked file while a new instance locks a fresh one. A
leftover empty file is harmless.
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)


def default_lock_path() -> Path:
    if sys.platform == "win32":
        base = Path(tempfile.gettempdir())
        return base / "speedpulse.lock"
    base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    uid = ""
    if hasattr(os, "getuid"):
        uid = f"-{os.getuid()}"
    return Path(base) / f"speedpulse{uid}.lock"


class SingleInstanceLock:
    """Try to become the single running instance."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or default_lock_path()
        self._fd: int | None = None

    @property
    def path(self) -> Path:
        return self._path

    def acquire(self) -> bool:
        """Return True if we now hold the lock; False if someone else does."""
        if self._fd is not None:
            return True
        fd = os.open(self._path, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            if sys.platform == "win32":
                import msvcrt

                os.write(fd, b"0")
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (ImportError, OSError):
            log.debug("Another SpeedPulse instance holds %s", self._path)
            os.close(fd)
            return False
        try:
            os.ftruncate(fd, 0)
            os.write(fd, str(os.getpid()).encode())
        except OSError:  # pragma: no cover - pid stamping is informational
            pass
        self._fd = fd
        return True

    def release(self) -> None:
        if self._fd is None:
            return
        try:
            if sys.platform == "win32":
                import msvcrt

                os.lseek(self._fd, 0, os.SEEK_SET)
                msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
        except (ImportError, OSError):  # pragma: no cover - best effort
            pass
        os.close(self._fd)
        self._fd = None

    def __enter__(self) -> SingleInstanceLock:
        acquired = self.acquire()
        if not acquired:
            raise RuntimeError(f"another instance holds {self._path}")
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()
