"""Renders live rates into tray icons.

Tray icons are tiny (16 px Windows/macOS, 22 px on many Linux panels), so
the label is compact with the unit suffix dropped (the tooltip carries the
full formatted rate). Text is stroked with a contrasting outline so it
stays legible on light and dark panels alike.

Two layouts (user-selectable in settings):

* ``stacked`` — two lines in a square icon: ``↓12.3`` over ``↑4.5``.
  Safe on every panel; glyphs share the height (~45% each).
* ``wide`` — one side-by-side line ``↓12.3 ↑4.5``. The pixmap width is
  derived from the measured text (intrinsic sizing, capped at 6:1), so the
  glyphs can own the full slot height. Panels that preserve icon aspect
  ratio show it as-is; panels that force it square scale it down, in which
  case ``stacked`` is the better choice.

``text_scale`` (0.6-2.0) multiplies the base font size; the fit loop
shrinks only when the text would overflow the pixmap. The physical
ceiling is the panel's tray-slot height - text cannot get larger than
the slot the desktop environment allots (that is what the floating
widget is for).
"""

from __future__ import annotations

import sys

from PySide6 import QtCore, QtGui

from ..core.units import compact_rate

if sys.platform in ("win32", "darwin"):
    BASE_LOGICAL_SIZE = 16
else:  # Linux panels commonly prefer 22 px StatusNotifier icons
    BASE_LOGICAL_SIZE = 22

LAYOUTS = ("stacked", "wide")

_TRAY_ARROWS = ("↓", "↑")
_BASE_FONT_RATIO = 0.45  # per line, stacked (two lines share the height)
_WIDE_FONT_RATIO = 0.72  # wide: single line owns the full slot height
_MAX_WIDE_ASPECT = 6.0  # safety cap for absurdly long text (defensive)


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
    layout: str = "stacked",
    text_scale: float = 1.0,
    size: int = BASE_LOGICAL_SIZE,
    device_pixel_ratio: float = 1.0,
) -> QtGui.QIcon:
    """Icon showing down/up rates; caller must invoke on the GUI thread."""
    down, up = compact_pair(down_bps, up_bps, use_bits=use_bits, binary_units=binary_units)
    if layout == "wide":
        lines = [f"{_TRAY_ARROWS[0]}{down} {_TRAY_ARROWS[1]}{up}"]
        layout_kind = "wide"
    else:
        lines = [f"{_TRAY_ARROWS[0]}{down}", f"{_TRAY_ARROWS[1]}{up}"]
        layout_kind = "stacked"
    return _render_text_icon(
        lines,
        theme=theme,
        size=size,
        ratio=device_pixel_ratio,
        layout=layout_kind,
        text_scale=text_scale,
    )


def render_placeholder_icon(
    theme: str = "auto", size: int = BASE_LOGICAL_SIZE, device_pixel_ratio: float = 1.0
) -> QtGui.QIcon:
    """Neutral icon shown before the first valid measurement."""
    return _render_text_icon(["~"], theme=theme, size=size, ratio=device_pixel_ratio)


def _render_text_icon(
    lines: list[str],
    *,
    theme: str,
    size: int,
    ratio: float,
    layout: str = "stacked",
    text_scale: float = 1.0,
) -> QtGui.QIcon:
    ratio = max(1.0, float(ratio))
    physical_h = max(8, round(size * ratio))
    scale = max(0.5, float(text_scale))
    font_ratio = _WIDE_FONT_RATIO if layout == "wide" else _BASE_FONT_RATIO

    font = QtGui.QFont()
    font.setBold(True)
    font.setPixelSize(max(5, round(physical_h * font_ratio * scale)))
    painter = None

    metrics = QtGui.QFontMetrics(font)
    margin_h = physical_h * 0.04
    if layout == "wide":
        # Height-fit only: width follows the measured text (intrinsic).
        while metrics.height() > physical_h - 2 * margin_h and font.pixelSize() > 5:
            font.setPixelSize(font.pixelSize() - 1)
            metrics = QtGui.QFontMetrics(font)
        text_w = max(metrics.horizontalAdvance(line) for line in lines)
        max_w = round(physical_h * _MAX_WIDE_ASPECT)
        while text_w > max_w and font.pixelSize() > 5:
            font.setPixelSize(font.pixelSize() - 1)
            metrics = QtGui.QFontMetrics(font)
            text_w = max(metrics.horizontalAdvance(line) for line in lines)
        physical_w = min(max_w, round(text_w + physical_h * 0.10))
    else:
        # Square icon: fit both axes (two lines share the height).
        physical_w = physical_h
        margin_w = physical_w * 0.04
        metrics = QtGui.QFontMetrics(font)
        for _ in range(24):
            widest = max(metrics.horizontalAdvance(line) for line in lines)
            fits_h = metrics.height() * len(lines) <= physical_h - 2 * margin_h
            fits_w = widest <= physical_w - 2 * margin_w
            if (fits_w and fits_h) or font.pixelSize() <= 5:
                break
            font.setPixelSize(font.pixelSize() - 1)
            metrics = QtGui.QFontMetrics(font)

    pixmap = QtGui.QPixmap(max(8, physical_w), max(8, physical_h))
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pixmap)
    try:
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setFont(font)
        text_color, outline_color = _colors(theme)
        line_height = metrics.height()
        top = (physical_h - line_height * len(lines)) / 2
        path = QtGui.QPainterPath()
        for index, line in enumerate(lines):
            baseline = top + line_height * index + metrics.ascent()
            width = metrics.horizontalAdvance(line)
            path.addText((physical_w - width) / 2, baseline, font, line)

        stroke = QtGui.QPen(outline_color)
        stroke.setWidthF(max(1.0, physical_h * 0.055))
        stroke.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
        painter.strokePath(path, stroke)
        painter.fillPath(path, text_color)
    finally:
        painter.end()

    pixmap.setDevicePixelRatio(ratio)
    return QtGui.QIcon(pixmap)
