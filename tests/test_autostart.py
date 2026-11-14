import plistlib
import sys

import pytest

from speedpulse.core import autostart as autostart_module
from speedpulse.core.autostart import (
    AutostartError,
    LinuxAutostart,
    MacOSAutostart,
    WindowsAutostart,
    _quote_exec,
    app_command,
    get_autostart,
)


class TestLinux:
    def test_desktop_file_roundtrip(self, tmp_path):
        mgr = LinuxAutostart(base_dir=tmp_path)
        assert mgr.is_enabled() is False
        mgr.enable()
        path = tmp_path / "autostart" / "speedpulse.desktop"
        text = path.read_text(encoding="utf-8")
        assert "[Desktop Entry]" in text
        assert "Exec=" in text
        assert "Terminal=false" in text
        assert mgr.is_enabled() is True
        mgr.enable()  # idempotent
        mgr.disable()
        assert mgr.is_enabled() is False

    def test_disable_without_enable_is_noop(self, tmp_path):
        LinuxAutostart(base_dir=tmp_path).disable()  # must not raise

    def test_stale_registration_reports_disabled(self, tmp_path):
        mgr = LinuxAutostart(base_dir=tmp_path)
        mgr.enable()
        # Registration now points at an install location that no longer exists.
        (tmp_path / "autostart" / "speedpulse.desktop").write_text(
            "[Desktop Entry]\nExec=/opt/old/install/speedpulse\n", encoding="utf-8"
        )
        assert mgr.is_enabled() is False


class TestMacOS:
    def test_plist_contents(self, tmp_path):
        mgr = MacOSAutostart(base_dir=tmp_path)
        mgr.enable()
        path = tmp_path / "LaunchAgents" / "org.speedpulse.app.plist"
        data = plistlib.loads(path.read_bytes())
        assert data["Label"] == "org.speedpulse.app"
        assert data["RunAtLoad"] is True
        assert data["KeepAlive"] is False
        assert data["ProgramArguments"] == app_command()
        assert mgr.is_enabled() is True
        mgr.disable()
        assert mgr.is_enabled() is False

    def test_translocation_is_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            autostart_module,
            "_resolved_app_path",
            lambda: __import__("pathlib").Path(
                "/private/var/folders/ab/AppTranslocation/SpeedPulse.app"
            ),
        )
        mgr = MacOSAutostart(base_dir=tmp_path)
        with pytest.raises(AutostartError):
            mgr.enable()
        assert mgr.is_enabled() is False

    def test_stale_plist_reports_disabled(self, tmp_path):
        mgr = MacOSAutostart(base_dir=tmp_path)
        path = tmp_path / "LaunchAgents" / "org.speedpulse.app.plist"
        path.parent.mkdir(parents=True)
        with path.open("wb") as fh:
            plistlib.dump({"Label": "org.speedpulse.app", "ProgramArguments": ["/opt/old/app"]}, fh)
        assert mgr.is_enabled() is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows registry")
class TestWindows:
    def test_run_key_roundtrip(self):
        mgr = WindowsAutostart()
        mgr.disable()
        assert mgr.is_enabled() is False
        mgr.enable()
        assert mgr.is_enabled() is True
        mgr.disable()
        assert mgr.is_enabled() is False


class TestCommon:
    def test_quote_exec(self):
        # Everything is quoted: quoting only when spaces misses '"' and '%'.
        assert _quote_exec(["plain"]) == '"plain"'
        assert _quote_exec(["a b", "c"]) == '"a b" "c"'
        assert _quote_exec(['a"b']) == '"a\\"b"'
        assert _quote_exec(["50%"]) == '"50%%"'  # % is a field code in Exec
        assert _quote_exec([r"c:\app"]) == r'"c:\\app"'

    def test_app_command_starts_with_executable(self):
        command = app_command()
        assert command[0] == sys.executable
        assert len(command) >= 1

    def test_factory_matches_platform(self):
        mgr = get_autostart()
        if sys.platform == "win32":
            assert isinstance(mgr, WindowsAutostart)
        elif sys.platform == "darwin":
            assert isinstance(mgr, MacOSAutostart)
        else:
            assert isinstance(mgr, LinuxAutostart)
