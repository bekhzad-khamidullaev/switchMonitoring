from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CounterSnapshot:
    in_octets: int
    out_octets: int


def _compute_delta(prev: int, curr: int, bits: int) -> Optional[int]:
    """Compute delta with rollover handling.

    Returns None if delta looks like a reset/invalid.
    """
    if prev < 0 or curr < 0:
        return None

    if curr >= prev:
        return curr - prev

    # rollover
    max_val = (1 << bits) - 1
    # Example: prev=4294967200, curr=100 -> delta = (max-prev)+curr+1
    delta = (max_val - prev) + curr + 1

    # If rollover delta is absurdly large compared to max, treat as reset
    if delta < 0 or delta > max_val:
        return None
    return delta


def compute_bps(
    prev: CounterSnapshot,
    curr: CounterSnapshot,
    interval_sec: float,
    counter_bits: int,
) -> Optional[tuple[int, int]]:
    """Compute in/out bps for given snapshots.

    Handles rollover for 32/64-bit counters.
    Returns None if interval is invalid or counter delta can't be computed.
    """
    if interval_sec <= 0:
        return None

    in_delta = _compute_delta(prev.in_octets, curr.in_octets, counter_bits)
    out_delta = _compute_delta(prev.out_octets, curr.out_octets, counter_bits)
    if in_delta is None or out_delta is None:
        return None

    in_bps = int((in_delta * 8) / interval_sec)
    out_bps = int((out_delta * 8) / interval_sec)

    # Safety clamp
    if in_bps < 0 or out_bps < 0:
        return None

    return in_bps, out_bps
