"""Settings: TOML on disk, dataclasses in memory.

Design rules:

* a missing, corrupt, or partial config file must never crash the app —
  load falls back to defaults and logs a warning;
* unknown keys are ignored (forward compatibility);
* values are clamped into sane ranges;
* the writer emits a tiny, known-good subset of TOML (stdlib ``tomllib``
  reads TOML but the stdlib cannot write it, and we avoid a dependency
  for our flat schema).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
MIN_INTERVAL_SECONDS = 0.25
MAX_INTERVAL_SECONDS = 10.0
THEMES = ("auto", "light", "dark")
TRAY_LAYOUTS = ("stacked", "wide")
MIN_TEXT_SCALE = 0.6
MAX_TEXT_SCALE = 2.0
MIN_WIDGET_FONT_PT = 8
MAX_WIDGET_FONT_PT = 96
MIN_WIDGET_W = 120
MAX_WIDGET_W = 1200
MIN_WIDGET_H = 50
MAX_WIDGET_H = 600


@dataclass
class UnitsConfig:
    use_bits: bool = False
    binary_units: bool = False


@dataclass
class DisplayConfig:
    theme: str = "auto"  # auto | light | dark
    layout: str = "stacked"  # stacked (two lines, square) | wide (side by side)
    text_scale: float = 1.0  # tray text size multiplier


@dataclass
class WidgetConfig:
    """Floating on-desktop rates display (for when the tray slot is too small)."""

    enabled: bool = False  # show at startup
    font_pt: int = 28
    x: int = 80
    y: int = 80
    width: int = 260
    height: int = 90


@dataclass
class SamplerConfig:
    interval_seconds: float = 1.0
    max_gap_seconds: float = 10.0
    include_vpn: bool = False
    excluded_interfaces: list[str] = field(default_factory=list)


@dataclass
class Settings:
    units: UnitsConfig = field(default_factory=UnitsConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    sampler: SamplerConfig = field(default_factory=SamplerConfig)
    widget: WidgetConfig = field(default_factory=WidgetConfig)
    autostart: bool = False


def config_dir() -> Path:
    """Per-user configuration directory, respecting platform conventions."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "SpeedPulse"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "SpeedPulse"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "speedpulse"


def config_path() -> Path:
    return config_dir() / "config.toml"


def load(path: Path) -> Settings:
    """Load settings, falling back to defaults for anything unusable."""
    settings = Settings()
    if not path.exists():
        return settings
    try:
        with path.open("rb") as fh:
            raw = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        log.warning("Could not read config %s (%s); using defaults", path, exc)
        return settings
    _apply(settings.units, raw.get("units"), _UNITS_KEYS)
    _apply(settings.display, raw.get("display"), _DISPLAY_KEYS)
    _apply(settings.sampler, raw.get("sampler"), _SAMPLER_KEYS)
    _apply(settings.widget, raw.get("widget"), _WIDGET_KEYS)
    settings.autostart = _as_bool(raw.get("autostart"), settings.autostart)
    return settings


_UNITS_KEYS = {"use_bits", "binary_units"}
_DISPLAY_KEYS = {"theme", "layout", "text_scale"}
_SAMPLER_KEYS = {"interval_seconds", "max_gap_seconds", "include_vpn", "excluded_interfaces"}
_WIDGET_KEYS = {"enabled", "font_pt", "x", "y", "width", "height"}


def _apply(target: object, section: object, known: set[str]) -> None:
    if not isinstance(section, dict):
        return
    unknown = set(section) - known
    if unknown:
        log.debug("Ignoring unknown config keys: %s", ", ".join(sorted(unknown)))
    for key in known & set(section):
        value = section[key]
        if key == "use_bits":
            target.use_bits = _as_bool(value, target.use_bits)  # type: ignore[attr-defined]
        elif key == "binary_units":
            target.binary_units = _as_bool(value, target.binary_units)  # type: ignore[attr-defined]
        elif key == "theme":
            target.theme = _as_theme(value, target.theme)  # type: ignore[attr-defined]
        elif key == "layout":
            target.layout = _as_layout(value, target.layout)  # type: ignore[attr-defined]
        elif key == "text_scale":
            target.text_scale = _as_text_scale(value, target.text_scale)  # type: ignore[attr-defined]
        elif key == "font_pt":
            setattr(
                target,
                key,
                _as_clamped_int(
                    value, getattr(target, key), MIN_WIDGET_FONT_PT, MAX_WIDGET_FONT_PT
                ),
            )
        elif key == "x" or key == "y":
            setattr(target, key, _as_int(value, getattr(target, key), -10000, 10000))
        elif key == "width":
            target.width = _as_clamped_int(value, target.width, MIN_WIDGET_W, MAX_WIDGET_W)  # type: ignore[attr-defined]
        elif key == "height":
            target.height = _as_clamped_int(value, target.height, MIN_WIDGET_H, MAX_WIDGET_H)  # type: ignore[attr-defined]
        elif key == "interval_seconds":
            target.interval_seconds = _as_interval(value, target.interval_seconds)  # type: ignore[attr-defined]
        elif key == "max_gap_seconds":
            target.max_gap_seconds = _as_positive_float(value, target.max_gap_seconds)  # type: ignore[attr-defined]
        elif key == "include_vpn":
            target.include_vpn = _as_bool(value, target.include_vpn)  # type: ignore[attr-defined]
        elif key == "excluded_interfaces":
            target.excluded_interfaces = _as_str_list(value, target.excluded_interfaces)  # type: ignore[attr-defined]
        elif key == "enabled":
            target.enabled = _as_bool(value, target.enabled)  # type: ignore[attr-defined]


def _as_bool(value: object, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _as_positive_float(value: object, default: float) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return float(value)
    log.debug("Ignoring invalid float value: %r", value)
    return default


def _as_interval(value: object, default: float) -> float:
    candidate = _as_positive_float(value, default)
    return min(max(candidate, MIN_INTERVAL_SECONDS), MAX_INTERVAL_SECONDS)


def _as_theme(value: object, default: str) -> str:
    return value if value in THEMES else default


def _as_layout(value: object, default: str) -> str:
    return value if value in TRAY_LAYOUTS else default


def _as_text_scale(value: object, default: float) -> float:
    candidate = _as_positive_float(value, default)
    return min(max(candidate, MIN_TEXT_SCALE), MAX_TEXT_SCALE)


def _as_int(value: object, default: int, low: int, high: int) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return min(max(value, low), high)
    log.debug("Ignoring invalid int value: %r", value)
    return default


_as_clamped_int = _as_int


def _as_str_list(value: object, default: list[str]) -> list[str]:
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    log.debug("Ignoring invalid string list: %r", value)
    return default


def save(path: Path, settings: Settings) -> None:
    """Write settings as TOML atomically (interrupted saves never corrupt).

    Writes to a sibling temp file, then ``os.replace`` — atomic on POSIX
    and Windows, so a crash mid-write can never destroy the old config.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(_dump_toml(settings), encoding="utf-8")
    os.replace(tmp, path)


def _dump_toml(settings: Settings) -> str:
    data = asdict(settings)
    # TOML: top-level keys must precede any [section] header, or they would
    # silently become keys of the last section.
    lines = [f"version = {SCHEMA_VERSION}"]
    sections: list[tuple[str, dict]] = []
    for section, values in data.items():
        if isinstance(values, dict):
            sections.append((section, values))
        else:
            lines.append(f"{section} = {_toml_value(values)}")
    lines.append("")
    for section, values in sections:
        lines.append(f"[{section}]")
        for key, value in values.items():
            lines.append(f"{key} = {_toml_value(value)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False) if value else "[]"
    # ensure_ascii=False: JSON's surrogate-pair escapes (𝄞) are
    # invalid in TOML, so emit non-ASCII characters literally instead (the
    # file is written UTF-8). Standard escapes like \n and \" stay valid.
    return json.dumps(str(value), ensure_ascii=False)
