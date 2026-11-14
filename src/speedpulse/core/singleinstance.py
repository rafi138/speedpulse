"""Single-instance enforcement via an advisory OS file lock.

``flock`` (POSIX) and ``msvcrt.locking`` (Windows) both release
automatically when the process dies, so there are no stale locks to
clean up. The lock file itself is deliberately *not* deleted on release:
unlinking it creates the classic race where a waiting instance holds a
lock on an unlinked file while a new instance locks a fresh one. A
leftover empty file is harmless.
"""

from __future__ import annotations

import errno
import logging
import os
import sys
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)


def _contention_errnos() -> frozenset[int]:
    """Errnos that mean "someone else holds the lock" (platform-dependent)."""
    names = ("EACCES", "EAGAIN", "EWOULDBLOCK", "EDEADLK", "EDEADLOCK")
    return frozenset(getattr(errno, name) for name in names if hasattr(errno, name))


_CONTENTION_ERRNOS = _contention_errnos()


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
        """Return True if we may run (as the primary); False if another instance does.

        Failure policy: a *contention* error (someone holds the lock) means
        "another instance is running" -> return False. Any other failure
        (unwritable directory, missing parent, exotic fs) must not render
        the app unlaunchable, so we fail open and run without the guard.
        """
        if self._fd is not None:
            return True
        try:
            fd = os.open(self._path, os.O_CREAT | os.O_RDWR, 0o644)
        except OSError as exc:
            log.warning(
                "Cannot create single-instance lock %s (%s); continuing without it",
                self._path,
                exc,
            )
            return True
        try:
            if sys.platform == "win32":
                import msvcrt

                os.write(fd, b"0")
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(fd)
            if isinstance(exc, BlockingIOError) or exc.errno in _CONTENTION_ERRNOS:
                log.debug("Another SpeedPulse instance holds %s", self._path)
                return False
            log.warning("Single-instance lock failed (%s); continuing without it", exc)
            return True
        except ImportError:  # pragma: no cover - msvcrt/fcntl always present on their OS
            os.close(fd)
            return True
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
