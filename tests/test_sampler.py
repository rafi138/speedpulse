import pytest

from speedpulse.core.config import SamplerConfig
from speedpulse.core.sampler import Sampler


@pytest.fixture()
def driver(monkeypatch):
    """Drive Sampler with scripted (time, counters) pairs.

    Returns a factory: ``make(polls, config)`` where ``polls`` is a list of
    ``(monotonic_time, counters_dict)`` tuples, one per ``poll()`` call.
    """

    def make(polls, config=None):
        state = {"index": 0}
        times = [t for t, _ in polls]
        counters = [c for _, c in polls]

        def fake_monotonic():
            return times[min(state["index"], len(times) - 1)]

        def reader():
            data = counters[min(state["index"], len(counters) - 1)]
            state["index"] += 1
            return data

        monkeypatch.setattr("speedpulse.core.sampler.time.monotonic", fake_monotonic)
        return Sampler(config or SamplerConfig(), reader=reader)

    return make


def test_first_poll_is_baseline(driver):
    sampler = driver([(0.0, {"eth0": (1000, 500)})])
    snapshot = sampler.poll()
    assert snapshot.has_rate is False


def test_second_poll_computes_rate(driver):
    sampler = driver(
        [
            (0.0, {"eth0": (1000, 500)}),
            (1.0, {"eth0": (126_000, 62_500)}),
        ]
    )
    sampler.poll()
    snapshot = sampler.poll()
    assert snapshot.has_rate
    assert snapshot.total.down_bps == pytest.approx(1_000_000.0)
    assert snapshot.total.up_bps == pytest.approx(496_000.0)


def test_virtual_interfaces_are_dropped(driver):
    sampler = driver(
        [
            (0.0, {"eth0": (0, 0), "docker0": (0, 0), "lo": (0, 0)}),
            (1.0, {"eth0": (125_000, 0), "docker0": (999_999, 0), "lo": (0, 0)}),
        ]
    )
    sampler.poll()
    snapshot = sampler.poll()
    assert [i.name for i in snapshot.per_interface] == ["eth0"]


def test_vpn_opt_in(driver):
    config = SamplerConfig(include_vpn=True)
    sampler = driver(
        [
            (0.0, {"eth0": (0, 0), "tun0": (0, 0)}),
            (1.0, {"eth0": (125_000, 0), "tun0": (50_000, 0)}),
        ],
        config=config,
    )
    sampler.poll()
    snapshot = sampler.poll()
    assert sorted(i.name for i in snapshot.per_interface) == ["eth0", "tun0"]
    assert snapshot.total.down_bps == pytest.approx(175_000 * 8)


def test_user_exclusion(driver):
    config = SamplerConfig(excluded_interfaces=["eth0"])
    sampler = driver(
        [
            (0.0, {"eth0": (0, 0), "wlan0": (0, 0)}),
            (1.0, {"eth0": (125_000, 0), "wlan0": (10_000, 0)}),
        ],
        config=config,
    )
    sampler.poll()
    snapshot = sampler.poll()
    assert [i.name for i in snapshot.per_interface] == ["wlan0"]
    assert snapshot.total.down_bps == pytest.approx(10_000 * 8)


def test_reader_failure_is_swallowed(driver):
    def bad_reader():
        raise OSError("kernel said no")

    sampler = Sampler(SamplerConfig(), reader=bad_reader)
    snapshot = sampler.poll()
    assert snapshot.has_rate is False


def test_max_interval_survives_timer_lateness(driver):
    # At interval=10.00 a Qt timer always fires slightly late (>=5% slack
    # is permitted); the gap guard must tolerate that or every sample at
    # the slowest setting would be judged stale forever.
    config = SamplerConfig(interval_seconds=10.0)
    sampler = driver(
        [
            (0.0, {"eth0": (0, 0)}),
            (10.05, {"eth0": (1_256_250, 0)}),  # 10.05 s later: late tick
        ],
        config=config,
    )
    sampler.poll()
    snapshot = sampler.poll()
    assert snapshot.has_rate
    assert snapshot.total.down_bps == pytest.approx(1_000_000.0)


def test_config_change_rebaselines(driver):
    sampler = driver(
        [
            (0.0, {"eth0": (0, 0)}),
            (1.0, {"eth0": (125_000, 0)}),
        ]
    )
    sampler.poll()
    snapshot = sampler.poll()
    assert snapshot.has_rate
    sampler.apply_config(SamplerConfig(max_gap_seconds=5.0))
    snapshot = sampler.poll()
    assert snapshot.has_rate is False  # fresh baseline after config change


def test_same_config_keeps_history(driver, monkeypatch):
    from speedpulse.core.config import SamplerConfig as C

    sampler = driver(
        [
            (0.0, {"eth0": (0, 0)}),
            (1.0, {"eth0": (125_000, 0)}),
            (2.0, {"eth0": (250_000, 0)}),
        ]
    )
    sampler.poll()
    sampler.apply_config(C())
    snapshot = sampler.poll()
    assert snapshot.has_rate  # identical config must not reset the baseline


def test_vanished_interface_forgotten(driver):
    sampler = driver(
        [
            (0.0, {"eth0": (0, 0)}),
            (1.0, {"eth0": (125_000, 0)}),
            (2.0, {}),  # interface disappeared
            (3.0, {"eth0": (300_000, 0)}),  # reappeared with higher counters
        ]
    )
    sampler.poll()
    sampler.poll()
    sampler.poll()  # interface gone
    snapshot = sampler.poll()
    # Fresh baseline on reappearance: no absurd burst from stale counters.
    assert snapshot.has_rate is False
