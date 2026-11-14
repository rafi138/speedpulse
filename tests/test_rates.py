import pytest

from speedpulse.core.rates import RateCalculator, RateSample


class TestRateCalculator:
    def test_first_sample_is_baseline_only(self):
        calc = RateCalculator()
        sample = calc.update(1000, 500, now=0.0)
        assert sample.valid is False

    def test_normal_delta(self):
        calc = RateCalculator()
        calc.update(1000, 500, now=0.0)
        sample = calc.update(126_000, 62_500, now=1.0)
        assert sample.valid
        assert sample.down_bps == pytest.approx(125_000 * 8)
        assert sample.up_bps == pytest.approx(62_000 * 8)

    def test_negative_delta_clamps_to_zero(self):
        calc = RateCalculator()
        calc.update(2000, 2000, now=0.0)
        sample = calc.update(500, 500, now=1.0)
        assert sample.valid
        assert sample.down_bps == 0.0
        assert sample.up_bps == 0.0

    def test_zero_elapsed_is_invalid(self):
        calc = RateCalculator()
        calc.update(1000, 1000, now=5.0)
        assert calc.update(2000, 2000, now=5.0).valid is False

    def test_suspend_resume_gap_is_invalid(self):
        calc = RateCalculator(max_gap_seconds=10.0)
        calc.update(0, 0, now=0.0)
        sample = calc.update(80_000, 80_000, now=60.0)  # laptop slept 60 s
        assert sample.valid is False

    def test_rate_resumes_after_gap(self):
        calc = RateCalculator(max_gap_seconds=10.0)
        calc.update(0, 0, now=0.0)
        calc.update(80_000, 80_000, now=60.0)  # gap: new baseline
        sample = calc.update(160_000, 160_000, now=61.0)
        assert sample.valid
        assert sample.down_bps == pytest.approx(80_000 * 8)

    def test_reset_rebaselines(self):
        calc = RateCalculator()
        calc.update(1000, 1000, now=0.0)
        calc.reset()
        assert calc.update(2000, 2000, now=1.0).valid is False

    def test_invalid_max_gap_rejected(self):
        with pytest.raises(ValueError):
            RateCalculator(max_gap_seconds=0)

    def test_uses_monotonic_clock_by_default(self):
        calc = RateCalculator()
        # No explicit timestamp: must not raise.
        sample = calc.update(1000, 1000)
        assert isinstance(sample, RateSample)
