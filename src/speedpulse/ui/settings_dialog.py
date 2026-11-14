"""Settings dialog: units, interval, interfaces, theme, autostart.

Save semantics: widget values are collected into a *draft copy* of the
settings; only after the (possibly failing) autostart validation succeeds
is the draft committed to the live Settings object. Cancel or a failed
save therefore never leaves half-applied state behind.
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Callable
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from ..core.autostart import AutostartBase, AutostartError
from ..core.config import (
    MAX_INTERVAL_SECONDS,
    MAX_TEXT_SCALE,
    MAX_WIDGET_FONT_PT,
    MIN_INTERVAL_SECONDS,
    MIN_TEXT_SCALE,
    MIN_WIDGET_FONT_PT,
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
        settings_path: Path,
        autostart: AutostartBase,
        on_saved: Callable[[], None] | None = None,
        interface_provider: InterfaceProvider | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._settings_path = settings_path
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

        self._layout_combo = QtWidgets.QComboBox()
        self._layout_combo.addItem("Two lines (square icon)", "stacked")
        self._layout_combo.addItem("Side by side (wide icon)", "wide")
        form.addRow("Tray layout:", self._layout_combo)

        self._text_scale_spin = QtWidgets.QDoubleSpinBox()
        self._text_scale_spin.setRange(MIN_TEXT_SCALE, MAX_TEXT_SCALE)
        self._text_scale_spin.setSingleStep(0.1)
        self._text_scale_spin.setDecimals(2)
        self._text_scale_spin.setSuffix("x")
        self._text_scale_spin.setToolTip("Adjust the tray text size (1.0x is the default).")
        form.addRow("Tray text size:", self._text_scale_spin)
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

        # -- floating widget ----------------------------------------------
        widget_box = QtWidgets.QGroupBox("Floating widget (large on-desktop display)")
        widget_layout = QtWidgets.QVBoxLayout(widget_box)
        self._widget_check = QtWidgets.QCheckBox("Show floating widget")
        self._widget_check.setToolTip(
            "A draggable, always-on-top display with large text - for when "
            "the tray slot is too small. Also available from the tray menu."
        )
        font_form = QtWidgets.QFormLayout()
        self._widget_font_spin = QtWidgets.QSpinBox()
        self._widget_font_spin.setRange(MIN_WIDGET_FONT_PT, MAX_WIDGET_FONT_PT)
        self._widget_font_spin.setSuffix(" pt")
        font_form.addRow("Font size:", self._widget_font_spin)
        widget_layout.addWidget(self._widget_check)
        widget_layout.addLayout(font_form)
        layout.addWidget(widget_box)

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

        self._include_vpn_check.toggled.connect(self._apply_vpn_lock)
        self.reload()

    # ------------------------------------------------------------- loading
    def reload(self) -> None:
        """Re-read widget values from the live settings.

        The tray keeps this dialog cached, so values must refresh every
        time it is shown; otherwise saving would resurrect stale values
        and clobber changes made from the tray menu.
        """
        units = self._settings.units
        self._bits_radio.setChecked(units.use_bits)
        self._bytes_radio.setChecked(not units.use_bits)
        self._binary_check.setChecked(units.binary_units)
        self._binary_check.setEnabled(not units.use_bits)

        self._interval_spin.setValue(self._settings.sampler.interval_seconds)
        self._theme_combo.setCurrentText(self._settings.display.theme)
        layout_index = self._layout_combo.findData(self._settings.display.layout)
        self._layout_combo.setCurrentIndex(max(0, layout_index))
        self._text_scale_spin.setValue(self._settings.display.text_scale)
        self._widget_check.setChecked(self._settings.widget.enabled)
        self._widget_font_spin.setValue(self._settings.widget.font_pt)
        self._include_vpn_check.setChecked(self._settings.sampler.include_vpn)
        self._autostart_check.setChecked(self._settings.autostart and self._autostart.is_enabled())
        self._populate_interfaces()
        self._apply_vpn_lock()

    # Kept as an alias because tests and subclasses may already call it.
    _load_values = reload

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
        draft = copy.deepcopy(self._settings)
        draft.units.use_bits = self._bits_radio.isChecked()
        draft.units.binary_units = self._binary_check.isChecked()
        draft.display.theme = self._theme_combo.currentText()
        draft.display.layout = self._layout_combo.currentData()
        draft.display.text_scale = self._text_scale_spin.value()
        draft.widget.enabled = self._widget_check.isChecked()
        draft.widget.font_pt = self._widget_font_spin.value()
        draft.sampler.interval_seconds = self._interval_spin.value()
        draft.sampler.include_vpn = self._include_vpn_check.isChecked()
        draft.sampler.excluded_interfaces = self._merged_exclusions()

        desired_autostart = self._autostart_check.isChecked()
        try:
            if desired_autostart:
                self._autostart.enable()
            else:
                self._autostart.disable()
        except AutostartError as exc:
            QtWidgets.QMessageBox.warning(self, "SpeedPulse", str(exc))
            return
        draft.autostart = desired_autostart

        # Validation succeeded: commit the draft to the live object in place
        # (the tray holds the same reference and reacts via on_saved).
        self._settings.units = draft.units
        self._settings.display = draft.display
        self._settings.sampler = draft.sampler
        self._settings.autostart = draft.autostart

        try:
            save_settings(self._settings_path, self._settings)
        except OSError as exc:
            log.warning("Could not save settings: %s", exc)
        if self._on_saved is not None:
            self._on_saved()
        self.accept()

    def _merged_exclusions(self) -> list[str]:
        """Compute exclusions without losing entries for absent interfaces.

        User-unchecked interfaces shown right now become excluded; stored
        exclusions for interfaces that are *not* currently visible (an
        unplugged USB NIC, a VPN that is down) are preserved untouched.
        VPN items only count while the include-VPN box is ticked.
        """
        checked = {
            self._interface_list.item(row).text()
            for row in range(self._interface_list.count())
            if self._interface_list.item(row).checkState() == QtCore.Qt.CheckState.Checked
        }
        existing = set(self._settings.sampler.excluded_interfaces)
        shown = set(self._shown_names)
        vpn_shown = {name for name in self._shown_names if is_vpn(name)}

        exclusions = existing - shown  # preserved: not visible right now
        exclusions |= (shown - vpn_shown) - checked
        if self._include_vpn_check.isChecked():
            exclusions |= vpn_shown - checked
        return sorted(exclusions)
