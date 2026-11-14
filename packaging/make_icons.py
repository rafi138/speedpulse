"""Generate the SpeedPulse icon set from one vector drawing.

Outputs into packaging/icons/: PNGs at tray/installer sizes plus a
multi-resolution .ico (ICO writing needs Pillow; PNGs come from Qt).
Run from anywhere: ``python packaging/make_icons.py``
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402

OUT = Path(__file__).resolve().parent / "icons"
PNG_SIZES = [16, 22, 24, 32, 48, 64, 128, 256]
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]

BG = "#1b2432"
DOWN = "#34d399"  # green arrow, pointing down
UP = "#60a5fa"  # blue arrow, pointing up


def _arrow(
    painter: QtGui.QPainter,
    cx: float,
    *,
    direction: int,
    color: str,
    size: float,
) -> None:
    """Vertical arrow centred on ``cx``; direction +1 = down, -1 = up."""
    top = size * 0.26
    bottom = size * 0.74
    shaft_end = bottom if direction > 0 else top
    shaft_start = top if direction > 0 else bottom
    head = max(2.0, size * 0.14)

    pen = QtGui.QPen(QtGui.QColor(color))
    pen.setWidthF(max(1.0, size * 0.09))
    pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
    painter.drawLine(QtCore.QLineF(cx, shaft_start, cx, shaft_end))

    tip = bottom if direction > 0 else top
    tip_ext = tip + direction * size * 0.04
    path = QtGui.QPainterPath()
    path.moveTo(cx - head, tip_ext - direction * head)
    path.lineTo(cx, tip_ext)
    path.lineTo(cx + head, tip_ext - direction * head)
    pen2 = QtGui.QPen(pen)
    painter.setPen(pen2)
    painter.drawPath(path)


def draw_icon(size: int) -> QtGui.QPixmap:
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pixmap)
    try:
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        radius = size * 0.22
        background = QtGui.QPainterPath()
        background.addRoundedRect(
            QtCore.QRectF(0.0, 0.0, float(size), float(size)), radius, radius
        )
        painter.fillPath(background, QtGui.QColor(BG))
        _arrow(painter, size * 0.34, direction=+1, color=DOWN, size=size)
        _arrow(painter, size * 0.66, direction=-1, color=UP, size=size)
    finally:
        painter.end()
    return pixmap


def main() -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    OUT.mkdir(parents=True, exist_ok=True)
    for size in PNG_SIZES:
        target = OUT / f"speedpulse_{size}.png"
        if not draw_icon(size).save(str(target), "PNG"):
            print(f"failed to write {target}", file=sys.stderr)
            return 1
        print(f"wrote {target}")

    from PIL import Image

    base = Image.open(OUT / "speedpulse_256.png")
    ico_target = OUT / "speedpulse.ico"
    base.save(str(ico_target), format="ICO", sizes=[(s, s) for s in ICO_SIZES])
    print(f"wrote {ico_target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
