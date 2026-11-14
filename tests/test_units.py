from speedpulse.core.units import (
    compact_rate,
    format_bytes,
    format_rate,
    scale_rate,
)


class TestScaleRate:
    def test_bits_decimal_thresholds(self):
        assert scale_rate(0, use_bits=True) == (0.0, "bps")
        assert scale_rate(999, use_bits=True) == (999.0, "bps")
        assert scale_rate(1000, use_bits=True) == (1.0, "Kbps")
        assert scale_rate(999_940, use_bits=True) == (999.94, "Kbps")
        assert scale_rate(1_000_000, use_bits=True) == (1.0, "Mbps")
        assert scale_rate(12_345_678, use_bits=True) == (12.345678, "Mbps")
        assert scale_rate(1.5e9, use_bits=True) == (1.5, "Gbps")

    def test_boundary_display_precision_promotes(self):
        # 999.999 Kbps would render as "1000.0 Kbps" (an impossible value);
        # it must promote to the next unit instead.
        assert scale_rate(999_999, use_bits=True) == (1.0, "Mbps")
        assert format_rate(999_999_999, use_bits=True) == "1.0 Gbps"

    def test_bits_negative_clamps_to_zero(self):
        assert scale_rate(-5, use_bits=True) == (0.0, "bps")

    def test_bytes_decimal_default(self):
        # 12,345,678 bps = 1,543,209.75 B/s -> 1.54320975 MB/s
        assert scale_rate(12_345_678, use_bits=False)[0] == 1.54320975
        assert scale_rate(12_345_678, use_bits=False)[1] == "MB/s"

    def test_bytes_binary_mode(self):
        assert scale_rate(8000, use_bits=False, binary_units=True) == (
            1000.0,
            "B/s",
        )
        assert scale_rate(8192, use_bits=False, binary_units=True) == (
            1.0,
            "KB/s",
        )


class TestFormatRate:
    def test_bits(self):
        assert format_rate(12_345_678, use_bits=True) == "12.3 Mbps"
        assert format_rate(0, use_bits=True) == "0.0 bps"

    def test_bytes(self):
        assert format_rate(8000, use_bits=False) == "1.0 KB/s"

    def test_very_large_is_not_infinite(self):
        formatted = format_rate(1e15, use_bits=True)
        assert formatted == "1000.0 Tbps"


class TestCompactRate:
    def test_small_shows_decimal(self):
        assert compact_rate(5000, use_bits=True) == "5.0"
        assert compact_rate(1_000_000, use_bits=True) == "1.0"

    def test_medium_drops_decimal(self):
        assert compact_rate(50_000_000, use_bits=True) == "50"

    def test_negative_clamps(self):
        assert compact_rate(-1, use_bits=True) == "0.0"


class TestFormatBytes:
    def test_basic(self):
        assert format_bytes(0) == "0.0 B"
        assert format_bytes(1024) == "1.0 KB"
        assert format_bytes(1_500_000_000) == "1.5 GB"

    def test_negative_clamps(self):
        assert format_bytes(-10) == "0.0 B"
