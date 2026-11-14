"""Rate and volume formatting.

One internal convention: rates are always *bits per second*; volumes are
always *bytes*. Conversion happens only at display time, exactly once.
"""

from __future__ import annotations

_BITS_UNITS = ("bps", "Kbps", "Mbps", "Gbps", "Tbps")
_BYTES_UNITS = ("B/s", "KB/s", "MB/s", "GB/s", "TB/s")
_DECIMAL = 1000.0
_BINARY = 1024.0


def _scale(value: float, base: float, units: tuple[str, ...]) -> tuple[float, str]:
    scaled = float(value)
    index = 0
    while scaled >= base and index < len(units) - 1:
        scaled /= base
        index += 1
    return scaled, units[index]


def scale_rate(
    bits_per_second: float, *, use_bits: bool, binary_units: bool = False
) -> tuple[float, str]:
    """Split a rate into ``(display_value, unit_suffix)``.

    Bits-per-second rates always use decimal SI scaling (1 Kbps = 1000 bps),
    the network-industry convention. Byte rates use decimal scaling by
    default; ``binary_units`` switches them to 1 KB/s = 1024 B/s.
    """
    if bits_per_second < 0:
        bits_per_second = 0.0
    if use_bits:
        return _scale(bits_per_second, _DECIMAL, _BITS_UNITS)
    base = _BINARY if binary_units else _DECIMAL
    bytes_per_second = bits_per_second / 8.0
    return _scale(bytes_per_second, base, _BYTES_UNITS)


def format_rate(bits_per_second: float, *, use_bits: bool, binary_units: bool = False) -> str:
    """Human-readable rate, e.g. ``"12.3 Mbps"`` or ``"1.4 MB/s"``."""
    value, unit = scale_rate(bits_per_second, use_bits=use_bits, binary_units=binary_units)
    return f"{value:.1f} {unit}"


def compact_rate(bits_per_second: float, *, use_bits: bool, binary_units: bool = False) -> str:
    """Very short rate for tiny tray icons, e.g. ``"12.3M"`` or ``"456"``.

    Drops the trailing unit suffix entirely; the arrow glyph and the
    tooltip carry the unit meaning.
    """
    value, _ = scale_rate(bits_per_second, use_bits=use_bits, binary_units=binary_units)
    if value < 10:
        return f"{value:.1f}"
    if value < 100:
        return f"{value:.0f}"
    return f"{value:.0f}"


def format_bytes(num_bytes: float) -> str:
    """Human-readable data volume, e.g. ``"1.4 GB"`` (decimal SI)."""
    if num_bytes < 0:
        num_bytes = 0.0
    value, unit = _scale(num_bytes, _DECIMAL, ("B", "KB", "MB", "GB", "TB"))
    return f"{value:.1f} {unit}"
