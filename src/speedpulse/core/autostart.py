"""Launch-at-login support, app-managed (no installer hooks).

Per-OS mechanism:

* Linux: XDG autostart ``~/.config/autostart/speedpulse.desktop``
* Windows: ``HKCU\\...\\CurrentVersion\\Run`` registry value
* macOS: LaunchAgent plist in ``~/Library/LaunchAgents``

macOS notes (researched): SMAppService would be the modern API but it is
unreliable for ad-hoc-signed PyInstaller bundles (``kSMErrorInvalidSignature``),
so a runtime-written plist is the robust default until Developer-ID signing
exists. We refuse to register from an App-Translocation path and strip the
quarantine xattr from the plist (macOS 27's launchd refuses quarantined
plists). App Translocation gives a randomised path, so registering from it
would break at next login anyway.
"""

from __future__ import annotations

import logging
import plistlib
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path

log = logging.getLogger(__name__)

APP_VALUE_NAME = "SpeedPulse"
MACOS_LABEL = "org.speedpulse.app"


class AutostartError(RuntimeError):
    """Raised when launch-at-login cannot be configured."""


def app_command() -> list[str]:
    """Command line that relaunches this app in the current install mode."""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    exe = Path(sys.executable)
    if sys.platform == "win32":
        pythonw = exe.with_name("pythonw.exe")
        if pythonw.exists():
            return [str(pythonw), "-m", "speedpulse"]
    return [sys.executable, "-m", "speedpulse"]


def _quote_exec_part(part: str) -> str:
    return f'"{part}"' if (" " in part or '"' in part) else part


def _quote_exec(command: list[str]) -> str:
    return " ".join(_quote_exec_part(part) for part in command)


class AutostartBase(ABC):
    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir

    @abstractmethod
    def enable(self) -> None:
        """Register launch-at-login; idempotent."""

    @abstractmethod
    def disable(self) -> None:
        """Unregister launch-at-login; idempotent, no error if absent."""

    @abstractmethod
    def is_enabled(self) -> bool:
        """Whether the OS currently has a registration for this app."""


class LinuxAutostart(AutostartBase):
    FILENAME = "speedpulse.desktop"

    _TEMPLATE = """[Desktop Entry]
Type=Application
Name=SpeedPulse
Comment=Internet speed monitor in your system tray
Exec={exec}
Terminal=false
Categories=Network;Monitor;
X-GNOME-Autostart-enabled=true
"""

    def _path(self) -> Path:
        base = self._base_dir or Path.home() / ".config"
        return base / "autostart" / self.FILENAME

    def enable(self) -> None:
        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._TEMPLATE.format(exec=_quote_exec(app_command())), encoding="utf-8")
        log.info("Autostart enabled via %s", path)

    def disable(self) -> None:
        self._path().unlink(missing_ok=True)

    def is_enabled(self) -> bool:
        return self._path().exists()


class WindowsAutostart(AutostartBase):
    RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

    def enable(self) -> None:
        import winreg

        value = subprocess.list2cmdline(app_command())
        with winreg.CreateKey(  # pyright: ignore[reportAttributeAccessIssue]
            winreg.HKEY_CURRENT_USER,  # pyright: ignore[reportAttributeAccessIssue]
            self.RUN_KEY,
        ) as key:
            winreg.SetValueEx(key, APP_VALUE_NAME, 0, winreg.REG_SZ, value)  # pyright: ignore[reportAttributeAccessIssue]
        log.info("Autostart enabled via HKCU Run key")

    def disable(self) -> None:
        import winreg

        try:
            with winreg.OpenKey(  # pyright: ignore[reportAttributeAccessIssue]
                winreg.HKEY_CURRENT_USER,  # pyright: ignore[reportAttributeAccessIssue]
                self.RUN_KEY,
                0,
                winreg.KEY_SET_VALUE,  # pyright: ignore[reportAttributeAccessIssue]
            ) as key:
                winreg.DeleteValue(key, APP_VALUE_NAME)  # pyright: ignore[reportAttributeAccessIssue]
        except FileNotFoundError:
            pass
        except OSError as exc:
            log.warning("Could not remove autostart value: %s", exc)

    def is_enabled(self) -> bool:
        import winreg

        try:
            with winreg.OpenKey(  # pyright: ignore[reportAttributeAccessIssue]
                winreg.HKEY_CURRENT_USER,  # pyright: ignore[reportAttributeAccessIssue]
                self.RUN_KEY,
                0,
                winreg.KEY_QUERY_VALUE,  # pyright: ignore[reportAttributeAccessIssue]
            ) as key:
                winreg.QueryValueEx(key, APP_VALUE_NAME)  # pyright: ignore[reportAttributeAccessIssue]
        except OSError:
            return False
        return True


class MacOSAutostart(AutostartBase):
    def _path(self) -> Path:
        base = self._base_dir or Path.home() / "Library"
        return base / "LaunchAgents" / f"{MACOS_LABEL}.plist"

    def enable(self) -> None:
        _reject_translocation()
        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        plist = {
            "Label": MACOS_LABEL,
            "ProgramArguments": app_command(),
            "RunAtLoad": True,
            "KeepAlive": False,
        }
        with path.open("wb") as fh:
            plistlib.dump(plist, fh)
        _strip_quarantine(path)
        log.info("Autostart enabled via %s", path)

    def disable(self) -> None:
        self._path().unlink(missing_ok=True)

    def is_enabled(self) -> bool:
        return self._path().exists()


def _resolved_app_path() -> Path:
    exe = Path(sys.executable).resolve()
    if getattr(sys, "frozen", False):
        # <Bundle>.app/Contents/MacOS/binary -> <Bundle>.app
        for parent in exe.parents:
            if parent.suffix == ".app":
                return parent
        return exe
    return exe


def _reject_translocation() -> None:
    resolved = str(_resolved_app_path())
    if "AppTranslocation" in resolved:
        raise AutostartError(
            "The app is running from a translocated path. Move it to /Applications "
            "first, then enable launch-at-login."
        )


def _strip_quarantine(path: Path) -> None:
    """Best-effort: macOS 27's launchd refuses quarantined plists.

    Plists we write ourselves never get the xattr, but be defensive for
    any path that might have picked it up (e.g. restored from archives).
    """
    if sys.platform != "darwin":
        return
    subprocess.run(
        ["xattr", "-d", "com.apple.quarantine", str(path)],
        capture_output=True,
        check=False,
    )


def get_autostart() -> AutostartBase:
    if sys.platform == "win32":
        return WindowsAutostart()
    if sys.platform == "darwin":
        return MacOSAutostart()
    return LinuxAutostart()
