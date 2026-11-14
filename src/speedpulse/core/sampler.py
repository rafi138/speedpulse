"""Polls OS interface counters and turns them into per-interface rates.

The sampler itself is UI-agnostic: the tray drives it from a timer and
renders the resulting snapshot. The counter reader is injectable so tests
never touch psutil.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

import psutil

from .config import SamplerConfig
from .interfaces import select_interfaces
from .rates import INVALID_RATE, RateCalculator, RateSample


@dataclass(frozen=True)
class InterfaceSnapshot:
    """One interface's rate since the previous poll."""

    name: str
    rate: RateSample


@dataclass(frozen=True)
class SamplerSnapshot:
    """Result of one poll: aggregate + per-interface detail."""

    timestamp: float
    total: RateSample
    per_interface: list[InterfaceSnapshot] = field(default_factory=list)

    @property
    def has_rate(self) -> bool:
        return self.total.valid


CounterReader = Callable[[], dict[str, tuple[int, int]]]


def psutil_counter_reader() -> dict[str, tuple[int, int]]:
    """Default reader: cumulative RX/TX byte counters per interface."""
    counters = psutil.net_io_counters(pernic=True, nowrap=True)
    return {name: (c.bytes_recv, c.bytes_sent) for name, c in counters.items()}


class Sampler:
    """Tracks cumulative counters and computes rates for selected interfaces."""

    def __init__(
        self,
        config: SamplerConfig,
        reader: CounterReader | None = None,
    ) -> None:
        self._config = config
        self._reader = reader or psutil_counter_reader
        self._calculators: dict[str, RateCalculator] = {}

    @property
    def config(self) -> SamplerConfig:
        return self._config

    def apply_config(self, config: SamplerConfig) -> None:
        """Swap configuration; baselines reset so rates restart cleanly."""
        if config == self._config:
            return
        self._config = config
        self.reset()

    def reset(self) -> None:
        self._calculators.clear()

    def _selected(self, available: list[str]) -> list[str]:
        return select_interfaces(
            available,
            include_vpn=self._config.include_vpn,
            excluded=set(self._config.excluded_interfaces),
        )

    def poll(self) -> SamplerSnapshot:
        """Read counters once and return the rates since the previous poll."""
        now = time.monotonic()
        try:
            counters = self._reader()
        except OSError:
            # Transient kernel/permission hiccups: report "measuring" rather
            # than dying; the next tick re-baselines via the gap guard only if
            # enough time passed, so also reset to avoid a bogus burst.
            self.reset()
            return SamplerSnapshot(timestamp=now, total=INVALID_RATE)

        selected = set(self._selected(list(counters)))
        snapshots: list[InterfaceSnapshot] = []
        total_down = 0.0
        total_up = 0.0
        any_valid = False

        for name in sorted(selected):
            rx, tx = counters[name]
            calc = self._calculators.get(name)
            if calc is None:
                calc = RateCalculator(max_gap_seconds=self._config.max_gap_seconds)
                self._calculators[name] = calc
            rate = calc.update(rx, tx, now)
            snapshots.append(InterfaceSnapshot(name=name, rate=rate))
            if rate.valid:
                total_down += rate.down_bps
                total_up += rate.up_bps
                any_valid = True

        # Drop calculators for interfaces that vanished or got deselected, so
        # a re-added interface starts from a fresh baseline instead of
        # comparing against stale counters.
        for stale in set(self._calculators) - selected:
            del self._calculators[stale]

        total = (
            RateSample(down_bps=total_down, up_bps=total_up, valid=True)
            if any_valid
            else INVALID_RATE
        )
        return SamplerSnapshot(timestamp=now, total=total, per_interface=snapshots)
