"""Renders live rates into tray icons.

Tray icons are tiny (16 px Windows/macOS, 22 px on many Linux panels), so
the label is compact: two lines — ``↓<down>`` / ``↑<up>`` — with the unit
suffix dropped (the tooltip carries the full formatted rate). Text is
stroked with a contrasting outline so it stays legible on light and dark
panels alike.
"""

from __future__ import annotations

import sys

from PySide6 import QtCore, QtGui

from ..core.units import compact_rate

if sys.platform in ("win32", "darwin"):
    BASE_LOGICAL_SIZE = 16
else:  # Linux panels commonly prefer 22 px StatusNotifier icons
    BASE_LOGICAL_SIZE = 22

_TRAY_ARROWS = ("↓", "↑")


def _colors(theme: str) -> tuple[QtGui.QColor, QtGui.QColor]:
    if theme == "light":  # light panel → dark text with light outline
        return QtGui.QColor("#1a1a1a"), QtGui.QColor(255, 255, 255, 230)
    # "auto" and "dark": white text with dark outline works everywhere.
    return QtGui.QColor("#ffffff"), QtGui.QColor(0, 0, 0, 210)


def compact_pair(
    down_bps: float, up_bps: float, *, use_bits: bool, binary_units: bool
) -> tuple[str, str]:
    return (
        compact_rate(down_bps, use_bits=use_bits, binary_units=binary_units),
        compact_rate(up_bps, use_bits=use_bits, binary_units=binary_units),
    )


def render_rate_icon(
    down_bps: float,
    up_bps: float,
    *,
    use_bits: bool,
    binary_units: bool = False,
    theme: str = "auto",
    size: int = BASE_LOGICAL_SIZE,
    device_pixel_ratio: float = 1.0,
) -> QtGui.QIcon:
    """Icon showing down/up rates; caller must invoke on the GUI thread."""
    down, up = compact_pair(down_bps, up_bps, use_bits=use_bits, binary_units=binary_units)
    lines = [f"{_TRAY_ARROWS[0]}{down}", f"{_TRAY_ARROWS[1]}{up}"]
    return _render_text_icon(lines, theme=theme, size=size, ratio=device_pixel_ratio)


def render_placeholder_icon(
    theme: str = "auto", size: int = BASE_LOGICAL_SIZE, device_pixel_ratio: float = 1.0
) -> QtGui.QIcon:
    """Neutral icon shown before the first valid measurement."""
    return _render_text_icon(["~"], theme=theme, size=size, ratio=device_pixel_ratio)


def _render_text_icon(lines: list[str], *, theme: str, size: int, ratio: float) -> QtGui.QIcon:
    ratio = max(1.0, float(ratio))
    physical = max(8, round(size * ratio))
    pixmap = QtGui.QPixmap(physical, physical)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)

    painter = QtGui.QPainter(pixmap)
    try:
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        font = QtGui.QFont()
        font.setBold(True)
        font.setPixelSize(max(5, round(physical * 0.36)))
        painter.setFont(font)

        # Shrink until both lines fit with a small margin.
        metrics = QtGui.QFontMetrics(font)
        margin = physical * 0.04
        for _ in range(6):
            widest = max(metrics.horizontalAdvance(line) for line in lines)
            if widest <= physical - 2 * margin or font.pixelSize() <= 5:
                break
            font.setPixelSize(font.pixelSize() - 1)
            painter.setFont(font)
            metrics = QtGui.QFontMetrics(font)

        text_color, outline_color = _colors(theme)
        line_height = metrics.height()
        top = (physical - line_height * len(lines)) / 2
        path = QtGui.QPainterPath()
        for index, line in enumerate(lines):
            baseline = top + line_height * index + metrics.ascent()
            width = metrics.horizontalAdvance(line)
            path.addText((physical - width) / 2, baseline, font, line)

        stroke = QtGui.QPen(outline_color)
        stroke.setWidthF(max(1.0, physical * 0.055))
        stroke.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
        painter.strokePath(path, stroke)
        painter.fillPath(path, text_color)
    finally:
        painter.end()

    pixmap.setDevicePixelRatio(ratio)
    return QtGui.QIcon(pixmap)
