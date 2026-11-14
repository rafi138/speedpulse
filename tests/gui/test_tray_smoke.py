"""Offscreen GUI smoke tests.

These construct real Qt objects with ``QT_QPA_PLATFORM=offscreen`` and only
assert on behaviour that is meaningful headless (no pixel comparisons, no
per-OS tray expectations). Strict behavioural coverage lives in the pure-core
tests; here we verify the UI layer wires up and reacts to snapshots.
"""

import pytest

# importorskip only catches ImportError; a PySide6 whose Qt shared libraries
# are missing (headless server, WSL, minimal container) raises OSError from
# dlopen — treat that as "not loadable" too instead of erroring the suite.
try:
    import PySide6.QtWidgets  # noqa: F401
except (ImportError, OSError):
    pytest.skip("PySide6 is not loadable in this environment", allow_module_level=True)

pytestmark = pytest.mark.gui


def test_rate_icon_renders_non_null(qapp):
    from speedpulse.ui.icon_renderer import render_placeholder_icon, render_rate_icon

    icon = render_rate_icon(12_345_678, 1_234_567, use_bits=True)
    assert not icon.isNull()
    assert not icon.pixmap(32, 32).isNull()
    assert not render_placeholder_icon().isNull()


def test_icons_render_in_both_unit_modes(qapp):
    from speedpulse.ui.icon_renderer import render_rate_icon

    for use_bits in (True, False):
        icon = render_rate_icon(8_000_000, 800_000, use_bits=use_bits)
        assert not icon.isNull()


def test_icons_render_in_both_layouts_and_scales(qapp):
    from speedpulse.ui.icon_renderer import render_rate_icon

    for layout in ("stacked", "wide"):
        for scale in (0.6, 1.0, 2.0):
            icon = render_rate_icon(
                8_000_000, 800_000, use_bits=True, layout=layout, text_scale=scale
            )
            assert not icon.isNull(), f"layout={layout} scale={scale}"
            # Wide layout must produce a 2:1 pixmap; stacked a square one.
            pixmap = icon.pixmap(64, 64)
            assert not pixmap.isNull()
            if layout == "wide":
                assert pixmap.width() >= pixmap.height()
            else:
                assert pixmap.width() == pixmap.height()


class TestTray:
    def test_constructs_with_menu(self, qtbot, tmp_path):
        from speedpulse.core.autostart import get_autostart
        from speedpulse.core.config import Settings
        from speedpulse.core.sampler import Sampler
        from speedpulse.ui.tray import SpeedPulseTray

        settings = Settings()
        tray = SpeedPulseTray(
            settings=settings,
            settings_path=tmp_path / "config.toml",
            sampler=Sampler(settings.sampler, reader=lambda: {}),
            autostart=get_autostart(),
        )
        assert tray.contextMenu() is not None
        assert len(tray.contextMenu().actions()) >= 5
        tray.shutdown()

    def test_renders_snapshots(self, qtbot, tmp_path):
        from speedpulse.core.autostart import get_autostart
        from speedpulse.core.config import Settings
        from speedpulse.core.rates import RateSample
        from speedpulse.core.sampler import Sampler, SamplerSnapshot
        from speedpulse.ui.tray import SpeedPulseTray

        settings = Settings()
        tray = SpeedPulseTray(
            settings=settings,
            settings_path=tmp_path / "config.toml",
            sampler=Sampler(settings.sampler, reader=lambda: {}),
            autostart=get_autostart(),
        )
        valid = SamplerSnapshot(timestamp=1.0, total=RateSample(12_345_678, 1_234_567, True))
        tray._render_snapshot(valid)
        assert tray._last_key is not None
        assert not tray.icon().isNull()

        measuring = SamplerSnapshot(timestamp=2.0, total=RateSample())
        tray._render_snapshot(measuring)
        assert tray._last_key is None
        tray.shutdown()

    def test_pause_stops_rendering(self, qtbot, tmp_path):
        from speedpulse.core.autostart import get_autostart
        from speedpulse.core.config import Settings
        from speedpulse.core.rates import RateSample
        from speedpulse.core.sampler import Sampler, SamplerSnapshot
        from speedpulse.ui.tray import SpeedPulseTray

        settings = Settings()
        tray = SpeedPulseTray(
            settings=settings,
            settings_path=tmp_path / "config.toml",
            sampler=Sampler(settings.sampler, reader=lambda: {}),
            autostart=get_autostart(),
        )
        tray._pause_action.setChecked(True)
        tray._toggle_pause(True)
        tray._render_snapshot(SamplerSnapshot(timestamp=1.0, total=RateSample(1e7, 1e6, True)))
        assert tray._last_key is None  # paused: nothing rendered
        tray.shutdown()

    def test_settings_dialog_roundtrip(self, qtbot, tmp_path):
        from speedpulse.core.autostart import get_autostart
        from speedpulse.core.config import Settings
        from speedpulse.ui.settings_dialog import SettingsDialog

        settings = Settings()
        dialog = SettingsDialog(
            settings=settings,
            settings_path=tmp_path / "config.toml",
            autostart=get_autostart(),
            interface_provider=lambda: ["eth0", "wlan0", "tun0"],
        )
        dialog._bits_radio.setChecked(True)
        dialog._interval_spin.setValue(2.5)
        saved = {}
        dialog._on_saved = lambda: saved.update(done=True)
        dialog._save_and_close()
        assert saved == {"done": True}
        assert settings.units.use_bits is True
        assert settings.sampler.interval_seconds == 2.5

    def test_floating_widget_toggle_and_update(self, qtbot, tmp_path):
        from speedpulse.core.autostart import get_autostart
        from speedpulse.core.config import Settings
        from speedpulse.core.rates import RateSample
        from speedpulse.core.sampler import Sampler, SamplerSnapshot
        from speedpulse.ui.tray import SpeedPulseTray

        settings = Settings()
        tray = SpeedPulseTray(
            settings=settings,
            settings_path=tmp_path / "config.toml",
            sampler=Sampler(settings.sampler, reader=lambda: {}),
            autostart=get_autostart(),
        )
        tray._widget_action.setChecked(True)
        tray._toggle_widget(True)
        assert tray._widget is not None and tray._widget.isVisible()

        tray._render_snapshot(
            SamplerSnapshot(timestamp=1.0, total=RateSample(12_345_678, 1_234_567, True))
        )
        label_text = tray._widget._label.text()
        # Default settings are bytes mode.
        assert "MB/s" in label_text and "KB/s" in label_text
        assert settings.widget.enabled is True

        tray._toggle_widget(False)
        assert tray._widget.isVisible() is False
        assert settings.widget.enabled is False
        tray.shutdown()
