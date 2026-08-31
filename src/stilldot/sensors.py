"""Stage 1 — time-align accelerometer and gyroscope onto one clock."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

G = 9.80665


def interpolate_to_rate(
    acc_t: NDArray[np.float64],
    acc: NDArray[np.float64],
    gyro_t: NDArray[np.float64],
    gyro: NDArray[np.float64],
    rate_hz: float = 100.0,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Linearly interpolate acc and gyro onto a shared ``rate_hz`` grid.

    Phone stacks often stamp the two sensors a few milliseconds apart. A
    filter that treats those samples as simultaneous quietly rotates the
    gravity vector into the horizontal channels.
    """
    if acc_t.size < 2 or gyro_t.size < 2:
        raise ValueError("need at least two samples on each sensor")
    if acc.shape[1] != 3 or gyro.shape[1] != 3:
        raise ValueError("acc and gyro must be Nx3")

    t0 = float(max(acc_t[0], gyro_t[0]))
    t1 = float(min(acc_t[-1], gyro_t[-1]))
    if t1 <= t0:
        raise ValueError("accelerometer and gyroscope time ranges do not overlap")

    n = int(np.floor((t1 - t0) * rate_hz)) + 1
    t = t0 + np.arange(n, dtype=np.float64) / rate_hz
    acc_i = np.column_stack([np.interp(t, acc_t, acc[:, i]) for i in range(3)])
    gyro_i = np.column_stack([np.interp(t, gyro_t, gyro[:, i]) for i in range(3)])
    return t, acc_i, gyro_i


def high_pass(signal: NDArray[np.float64], alpha: float = 0.92) -> NDArray[np.float64]:
    """First-order high-pass. ``alpha`` near 1 keeps more of the bounce/vibration."""
    out = np.zeros_like(signal)
    if signal.size == 0:
        return out
    prev_x = signal[0]
    prev_y = 0.0
    for i, x in enumerate(signal):
        y = alpha * (prev_y + x - prev_x)
        out[i] = y
        prev_x = x
        prev_y = y
    return out


def moving_rms(signal: NDArray[np.float64], window: int) -> NDArray[np.float64]:
    if window < 1:
        raise ValueError("window must be >= 1")
    if signal.size == 0:
        return signal.copy()
    c = np.cumsum(np.square(signal), dtype=np.float64)
    out = np.empty_like(signal)
    for i in range(signal.size):
        a = 0 if i < window else i - window + 1
        total = c[i] - (c[a - 1] if a else 0.0)
        out[i] = np.sqrt(total / (i - a + 1))
    return out
