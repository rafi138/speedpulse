"""The system-tray application object: icon, menu, poll timer."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from .. import APP_NAME, __version__
from ..core.autostart import AutostartBase, AutostartError
from ..core.config import Settings
from ..core.sampler import Sampler, SamplerSnapshot
from ..core.units import format_rate
from .icon_renderer import (
    BASE_LOGICAL_SIZE,
    compact_pair,
    render_placeholder_icon,
    render_rate_icon,
)
from .notifications import show_notification
from .settings_dialog import SettingsDialog

log = logging.getLogger(__name__)

MIN_TIMER_MS = 250


class SpeedPulseTray(QtWidgets.QSystemTrayIcon):
    def __init__(
        self,
        *,
        settings: Settings,
        settings_path: Path,
        sampler: Sampler,
        autostart: AutostartBase,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._settings_path = settings_path
        self._sampler = sampler
        self._autostart = autostart
        self._paused = False
        self._last_key: tuple[str, str] | None = None
        self._dialog: SettingsDialog | None = None

        self._build_menu()
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.activated.connect(self._on_activated)

        self._apply_settings()
        # Never call show() without an icon: some platforms log or render
        # nothing until the first valid sample arrives.
        self.setIcon(
            render_placeholder_icon(
                theme=self._settings.display.theme,
                size=BASE_LOGICAL_SIZE,
                device_pixel_ratio=self._dpr(),
            )
        )
        self.show()
        self._timer.start()

    # ---------------------------------------------------------------- menu
    def _build_menu(self) -> None:
        # Parent every action to the menu: parentless QActions are owned by
        # Python and can be garbage-collected once this method returns,
        # silently emptying the tray menu mid-session.
        menu = QtWidgets.QMenu()
        self._pause_action = QtGui.QAction("&Pause updates", menu, checkable=True)
        self._pause_action.triggered.connect(self._toggle_pause)

        self._bits_action = QtGui.QAction("Show &bits per second (bps/Mbps)", menu, checkable=True)
        self._bits_action.triggered.connect(self._toggle_bits)

        self._autostart_action = QtGui.QAction("Launch at &startup", menu, checkable=True)
        self._autostart_action.triggered.connect(self._toggle_autostart)

        settings_action = QtGui.QAction("&Settings…", menu)
        settings_action.triggered.connect(self.open_settings)

        about_action = QtGui.QAction("&About SpeedPulse", menu)
        about_action.triggered.connect(self._show_about)

        quit_action = QtGui.QAction("&Quit", menu)
        quit_action.triggered.connect(self._quit)

        menu.addAction(self._pause_action)
        menu.addAction(self._bits_action)
        menu.addAction(self._autostart_action)
        menu.addSeparator()
        menu.addAction(settings_action)
        menu.addAction(about_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.setContextMenu(menu)

    # ------------------------------------------------------------- updates
    def _tick(self) -> None:
        try:
            snapshot = self._sampler.poll()
        except Exception:
            log.exception("Sampler poll failed")
            return
        self._render_snapshot(snapshot)

    def _render_snapshot(self, snapshot: SamplerSnapshot) -> None:
        if self._paused:
            return
        use_bits = self._settings.units.use_bits
        binary_units = self._settings.units.binary_units
        theme = self._settings.display.theme

        if not snapshot.has_rate:
            if self._last_key is not None:
                self._last_key = None
                self.setIcon(
                    render_placeholder_icon(
                        theme=theme,
                        size=BASE_LOGICAL_SIZE,
                        device_pixel_ratio=self._dpr(),
                    )
                )
                self.setToolTip(f"{APP_NAME} — measuring…")
            return

        total = snapshot.total
        key = compact_pair(
            total.down_bps, total.up_bps, use_bits=use_bits, binary_units=binary_units
        )
        if key != self._last_key:
            self.setIcon(
                render_rate_icon(
                    total.down_bps,
                    total.up_bps,
                    use_bits=use_bits,
                    binary_units=binary_units,
                    theme=theme,
                    size=BASE_LOGICAL_SIZE,
                    device_pixel_ratio=self._dpr(),
                )
            )
            self._last_key = key
        self.setToolTip(
            f"{APP_NAME}\n"
            f"↓ {format_rate(total.down_bps, use_bits=use_bits, binary_units=binary_units)}  "
            f"↑ {format_rate(total.up_bps, use_bits=use_bits, binary_units=binary_units)}"
        )

    @staticmethod
    def _dpr() -> float:
        screen = QtGui.QGuiApplication.primaryScreen()
        return screen.devicePixelRatio() if screen else 1.0

    # ------------------------------------------------------------ settings
    def _apply_settings(self) -> None:
        interval_ms = max(MIN_TIMER_MS, round(self._settings.sampler.interval_seconds * 1000))
        self._timer.setInterval(interval_ms)
        self._sampler.apply_config(self._settings.sampler)
        self._bits_action.setChecked(self._settings.units.use_bits)
        self._autostart_action.setChecked(self._settings.autostart and self._autostart.is_enabled())
        self._last_key = None  # force icon re-render with new units/theme

    def open_settings(self) -> None:
        if self._dialog is None:
            self._dialog = SettingsDialog(
                settings=self._settings,
                settings_path=self._settings_path,
                autostart=self._autostart,
                on_saved=self._apply_settings,
            )
        else:
            # The dialog is cached: refresh it from the live settings, or
            # saving would resurrect stale values and clobber tray-menu
            # changes (units, autostart) made since it was last open.
            self._dialog.reload()
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()

    def _toggle_pause(self, checked: bool) -> None:
        self._paused = checked
        if checked:
            self._timer.stop()
            self.setToolTip(f"{APP_NAME} — paused")
        else:
            self._last_key = None
            self._timer.start()
            self._tick()

    def _toggle_bits(self, checked: bool) -> None:
        self._settings.units.use_bits = checked
        self._save()

    def _toggle_autostart(self, checked: bool) -> None:
        try:
            if checked:
                self._autostart.enable()
            else:
                self._autostart.disable()
        except AutostartError as exc:
            QtWidgets.QMessageBox.warning(None, APP_NAME, str(exc))
            self._autostart_action.setChecked(not checked)
            return
        self._settings.autostart = checked
        self._save()

    def _save(self) -> None:
        from ..core.config import save as save_settings

        try:
            save_settings(self._settings_path, self._settings)
        except OSError as exc:
            log.warning("Could not save settings: %s", exc)
        self._apply_settings()

    # ---------------------------------------------------------------- misc
    def _on_activated(self, reason: QtWidgets.QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QtWidgets.QSystemTrayIcon.ActivationReason.Trigger,
            QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.open_settings()

    def _show_about(self) -> None:
        QtWidgets.QMessageBox.about(
            None,
            APP_NAME,
            f"<b>{APP_NAME} {__version__}</b><br><br>"
            "Internet speed monitor for your system tray.<br>"
            "Live throughput of your network interfaces; speed tests and "
            "history arrive in later releases.<br><br>"
            "MIT licensed.",
        )

    def welcome(self) -> None:
        show_notification(
            self,
            APP_NAME,
            "Monitoring your connection from the system tray. Right-click the icon for settings.",
        )

    def shutdown(self) -> None:
        self._timer.stop()
        self.hide()

    def _quit(self) -> None:
        self.shutdown()
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.quit()
