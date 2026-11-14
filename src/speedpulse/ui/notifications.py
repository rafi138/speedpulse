"""Desktop notifications with graceful degradation.

``QSystemTrayIcon.showMessage`` is the zero-dependency baseline; Qt
documents that balloon messages "may not appear at all" on some
platforms, so callers must treat notification failure as harmless.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6 import QtWidgets

if TYPE_CHECKING:
    from .tray import SpeedPulseTray


def show_notification(tray: SpeedPulseTray, title: str, message: str, *, msecs: int = 4000) -> None:
    if tray.supportsMessages():
        tray.showMessage(
            title,
            message,
            QtWidgets.QSystemTrayIcon.MessageIcon.Information,
            msecs,
        )
