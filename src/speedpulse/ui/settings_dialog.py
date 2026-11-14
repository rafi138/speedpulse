"""Settings dialog: units, interval, interfaces, theme, autostart."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6 import QtCore, QtWidgets

from ..core.autostart import AutostartBase, AutostartError
from ..core.config import (
    MAX_INTERVAL_SECONDS,
    MIN_INTERVAL_SECONDS,
    THEMES,
    Settings,
)
from ..core.config import (
    save as save_settings,
)
from ..core.interfaces import is_vpn, selectable_interfaces

log = logging.getLogger(__name__)

InterfaceProvider = Callable[[], list[str]]


def default_interface_provider() -> list[str]:
    import psutil

    try:
        names = list(psutil.net_io_counters(pernic=True, nowrap=True).keys())
    except OSError:
        log.warning("Could not enumerate network interfaces")
        return []
    return selectable_interfaces(names)


class SettingsDialog(QtWidgets.QDialog):
    def __init__(
        self,
        *,
        settings: Settings,
        settings_path: object,
        autostart: AutostartBase,
        on_saved: Callable[[], None] | None = None,
        interface_provider: InterfaceProvider | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        from pathlib import Path

        assert isinstance(settings_path, Path) or settings_path is None
        self._settings = settings
        self._settings_path: Path = settings_path  # type: ignore[assignment]
        self._autostart = autostart
        self._on_saved = on_saved
        self._interface_provider = interface_provider or default_interface_provider
        self._shown_names: list[str] = []

        self.setWindowTitle("SpeedPulse Settings")
        layout = QtWidgets.QVBoxLayout(self)

        # -- units -----------------------------------------------------
        units_box = QtWidgets.QGroupBox("Units")
        units_layout = QtWidgets.QVBoxLayout(units_box)
        self._bits_radio = QtWidgets.QRadioButton("Bits per second (bps, Kbps, Mbps)")
        self._bytes_radio = QtWidgets.QRadioButton("Bytes per second (B/s, KB/s, MB/s)")
        group = QtWidgets.QButtonGroup(self)
        group.addButton(self._bits_radio)
        group.addButton(self._bytes_radio)
        self._binary_check = QtWidgets.QCheckBox("Use 1024-based units (KiB/s, MiB/s)")
        units_layout.addWidget(self._bits_radio)
        units_layout.addWidget(self._bytes_radio)
        units_layout.addWidget(self._binary_check)
        layout.addWidget(units_box)

        # -- polling & appearance ---------------------------------------
        form = QtWidgets.QFormLayout()
        self._interval_spin = QtWidgets.QDoubleSpinBox()
        self._interval_spin.setRange(MIN_INTERVAL_SECONDS, MAX_INTERVAL_SECONDS)
        self._interval_spin.setSingleStep(0.25)
        self._interval_spin.setDecimals(2)
        self._interval_spin.setSuffix(" s")
        form.addRow("Update interval:", self._interval_spin)

        self._theme_combo = QtWidgets.QComboBox()
        self._theme_combo.addItems(list(THEMES))
        form.addRow("Tray text colour:", self._theme_combo)
        layout.addLayout(form)

        # -- interfaces --------------------------------------------------
        interfaces_box = QtWidgets.QGroupBox("Interfaces")
        interfaces_layout = QtWidgets.QVBoxLayout(interfaces_box)
        self._include_vpn_check = QtWidgets.QCheckBox(
            "Include VPN/tunnel interfaces (tun*, wg*, …)"
        )
        self._include_vpn_check.setToolTip(
            "VPN traffic also flows through the physical interface, so "
            "aggregating both double-counts it. Enable only if you want the "
            "tunnel counted on its own."
        )
        self._interface_list = QtWidgets.QListWidget()
        self._interface_list.setToolTip(
            "Checked interfaces contribute to the tray's aggregate rate."
        )
        interfaces_layout.addWidget(self._include_vpn_check)
        interfaces_layout.addWidget(self._interface_list)
        layout.addWidget(interfaces_box)

        # -- autostart ----------------------------------------------------
        self._autostart_check = QtWidgets.QCheckBox("Launch at startup")
        layout.addWidget(self._autostart_check)

        # -- buttons -------------------------------------------------------
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._load_values()

    # ------------------------------------------------------------- loading
    def _load_values(self) -> None:
        units = self._settings.units
        self._bits_radio.setChecked(units.use_bits)
        self._bytes_radio.setChecked(not units.use_bits)
        self._binary_check.setChecked(units.binary_units)
        self._binary_check.setEnabled(not units.use_bits)

        self._interval_spin.setValue(self._settings.sampler.interval_seconds)
        self._theme_combo.setCurrentText(self._settings.display.theme)
        self._include_vpn_check.setChecked(self._settings.sampler.include_vpn)
        self._autostart_check.setChecked(self._settings.autostart and self._autostart.is_enabled())
        self._populate_interfaces()
        self._apply_vpn_lock()

    def _populate_interfaces(self) -> None:
        self._shown_names = self._interface_provider()
        selected = set(self._shown_names) - set(self._settings.sampler.excluded_interfaces)
        self._interface_list.clear()
        for name in self._shown_names:
            item = QtWidgets.QListWidgetItem(name)
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                QtCore.Qt.CheckState.Checked if name in selected else QtCore.Qt.CheckState.Unchecked
            )
            item.setToolTip("VPN/tunnel interface" if is_vpn(name) else "Physical interface")
            self._interface_list.addItem(item)

    def _apply_vpn_lock(self) -> None:
        include = self._include_vpn_check.isChecked()
        for row in range(self._interface_list.count()):
            item = self._interface_list.item(row)
            if is_vpn(item.text()):
                if include:
                    item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsEnabled)
                else:
                    item.setCheckState(QtCore.Qt.CheckState.Unchecked)
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)

    # ------------------------------------------------------------- saving
    def _save_and_close(self) -> None:
        self._settings.units.use_bits = self._bits_radio.isChecked()
        self._settings.units.binary_units = self._binary_check.isChecked()
        self._settings.display.theme = self._theme_combo.currentText()
        self._settings.sampler.interval_seconds = self._interval_spin.value()
        self._settings.sampler.include_vpn = self._include_vpn_check.isChecked()

        checked = {
            self._interface_list.item(row).text()
            for row in range(self._interface_list.count())
            if self._interface_list.item(row).checkState() == QtCore.Qt.CheckState.Checked
        }
        self._settings.sampler.excluded_interfaces = sorted(set(self._shown_names) - checked)

        desired_autostart = self._autostart_check.isChecked()
        try:
            if desired_autostart:
                self._autostart.enable()
            else:
                self._autostart.disable()
        except AutostartError as exc:
            QtWidgets.QMessageBox.warning(self, "SpeedPulse", str(exc))
            return
        self._settings.autostart = desired_autostart

        try:
            save_settings(self._settings_path, self._settings)
        except OSError as exc:
            log.warning("Could not save settings: %s", exc)
        if self._on_saved is not None:
            self._on_saved()
        self.accept()
