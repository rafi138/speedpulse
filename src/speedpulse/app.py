"""Composition root: parse args, wire core + UI, run the Qt event loop."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from . import APP_NAME, __version__
from .core.autostart import get_autostart
from .core.config import config_path, load
from .core.sampler import Sampler
from .core.singleinstance import SingleInstanceLock
from .ui.tray import SpeedPulseTray

log = logging.getLogger(APP_NAME.lower())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="speedpulse",
        description="Internet speed monitor for your system tray.",
    )
    parser.add_argument("--config", type=Path, default=None, help="path to config.toml")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    lock = SingleInstanceLock()
    if not lock.acquire():
        log.info("%s is already running; exiting.", APP_NAME)
        return 0

    settings_path = args.config or config_path()
    settings = load(settings_path)
    log.info("Starting %s %s (config: %s)", APP_NAME, __version__, settings_path)

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setApplicationDisplayName(APP_NAME)
    # The tray icon *is* the app; closing the settings window must not quit.
    app.setQuitOnLastWindowClosed(False)

    sampler = Sampler(settings.sampler)
    tray = SpeedPulseTray(
        settings=settings,
        settings_path=settings_path,
        sampler=sampler,
        autostart=get_autostart(),
    )
    tray.welcome()

    _install_signal_handlers(app)

    try:
        code = app.exec()
    finally:
        tray.shutdown()
        lock.release()
    return code


def _install_signal_handlers(app: QtWidgets.QApplication) -> None:
    """Route SIGINT/SIGTERM into Qt's quit path.

    During ``app.exec()`` the interpreter only gets control back when a
    Python callback runs, so a short no-op timer keeps signal handlers
    alive; otherwise Ctrl+C would appear dead until the next event.
    """

    def _quit(*_args: object) -> None:
        app.quit()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _quit)
        except (OSError, ValueError):  # pragma: no cover - platform-dependent
            log.debug("Could not install handler for %s", sig)
    keepalive = QtCore.QTimer()
    keepalive.timeout.connect(lambda: None)
    keepalive.start(250)
    # Keep a reference for the app's lifetime (QTimer with no parent would
    # otherwise be garbage-collected, silently breaking Ctrl+C).
    app._speedpulse_keepalive = keepalive  # type: ignore[attr-defined]


if __name__ == "__main__":
    sys.exit(main())
