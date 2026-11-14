"""Byte-counter delta math with the anomaly guards a tray app needs.

Guards (mirroring the semantics proven by the reference GNOME extension,
plus suspend/resume handling it lacked):

* the first sample establishes a baseline and yields no rate;
* negative deltas (counter reset / interface replacement) clamp to zero;
* non-positive elapsed time yields no rate;
* a gap longer than ``max_gap_seconds`` (sleep, pause, frozen machine)
  yields no rate instead of an absurd spike.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class RateSample:
    """A throughput sample in bits per second; ``valid`` gates display."""

    down_bps: float = 0.0
    up_bps: float = 0.0
    valid: bool = False


#: Shared "no rate available" sentinel (first poll, sleep gap, ...).
INVALID_RATE = RateSample()


class RateCalculator:
    """Convert cumulative byte counters into bits-per-second rates."""

    def __init__(self, max_gap_seconds: float = 10.0) -> None:
        if max_gap_seconds <= 0:
            raise ValueError("max_gap_seconds must be positive")
        self._max_gap = max_gap_seconds
        self._prev: tuple[int, int, float] | None = None  # (rx, tx, monotonic)

    def update(self, rx_bytes: int, tx_bytes: int, now: float | None = None) -> RateSample:
        """Feed one cumulative counter reading; return the rate since last call."""
        if now is None:
            now = time.monotonic()
        prev = self._prev
        self._prev = (rx_bytes, tx_bytes, now)
        if prev is None:
            return INVALID_RATE
        prev_rx, prev_tx, prev_t = prev
        elapsed = now - prev_t
        if elapsed <= 0:
            return INVALID_RATE
        if elapsed > self._max_gap:
            return INVALID_RATE
        down_bps = max(rx_bytes - prev_rx, 0) * 8.0 / elapsed
        up_bps = max(tx_bytes - prev_tx, 0) * 8.0 / elapsed
        return RateSample(down_bps=down_bps, up_bps=up_bps, valid=True)

    def reset(self) -> None:
        """Forget history; the next update becomes a new baseline."""
        self._prev = None
