"""Frameless, always-on-top floating rates display.

For desktops where the tray slot is simply too small: a draggable,
resizable on-desktop readout with large green/blue arrows, the same
theme colours as the app icon. Geometry is persisted to the user's
config so it reopens where they left it.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6 import QtCore, QtGui, QtWidgets

from ..core.config import Settings
from ..core.units import format_rate

log = logging.getLogger(__name__)

DOWN_COLOR = "#34d399"
UP_COLOR = "#60a5fa"


class FloatingWidget(QtWidgets.QWidget):
    """Draggable, resizable, always-on-top rates display."""

    def __init__(
        self,
        settings: Settings,
        on_geometry_changed: Callable[[], None] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(
            parent,
            QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint,
        )
        self._settings = settings
        self._on_geometry_changed = on_geometry_changed
        self._drag_offset: QtCore.QPoint | None = None

        self.setWindowTitle("SpeedPulse")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)

        self._label = QtWidgets.QLabel(self)
        self._label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        grip = QtWidgets.QSizeGrip(self)
        grip.setFixedSize(16, 16)

        inner = QtWidgets.QVBoxLayout()
        inner.setContentsMargins(8, 8, 8, 2)
        inner.addWidget(self._label, stretch=1)
        corner = QtWidgets.QHBoxLayout()
        corner.addStretch(1)
        corner.addWidget(grip, 0, QtCore.Qt.AlignmentFlag.AlignBottom)
        inner.addLayout(corner)
        self.setLayout(inner)

        self.setStyleSheet(
            "FloatingWidget { background: rgba(27, 36, 50, 230);"
            " border-radius: 10px; }"
            "QLabel { background: transparent; }"
        )
        self.sync_from_config()

    # ------------------------------------------------------------- display
    def sync_from_config(self) -> None:
        config = self._settings.widget
        font = QtGui.QFont()
        font.setBold(True)
        font.setPointSize(config.font_pt)
        self._label.setFont(font)
        geometry = QtCore.QRect(
            config.x, config.y, max(self.minimumSizeHint().width(), config.width), config.height
        )
        self.setGeometry(geometry)

    def update_rates(
        self, down_bps: float, up_bps: float, *, use_bits: bool, binary_units: bool
    ) -> None:
        down = format_rate(down_bps, use_bits=use_bits, binary_units=binary_units)
        up = format_rate(up_bps, use_bits=use_bits, binary_units=binary_units)
        self._label.setText(
            f'<div style="color:{DOWN_COLOR};">↓ {down}</div>'
            f'<div style="color:{UP_COLOR};">↑ {up}</div>'
        )

    # ------------------------------------------------------------ dragging
    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self._drag_offset is not None:
            self._drag_offset = None
            self.persist_geometry()
        super().mouseReleaseEvent(event)

    def persist_geometry(self) -> None:
        """Write current geometry into the config (caller decides when to save)."""
        geometry = self.geometry()
        widget_config = self._settings.widget
        widget_config.x = geometry.x()
        widget_config.y = geometry.y()
        widget_config.width = geometry.width()
        widget_config.height = geometry.height()
        if self._on_geometry_changed is not None:
            self._on_geometry_changed()
