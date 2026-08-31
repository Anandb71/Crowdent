"""Stage 3 — virtual odometer. Speed from the motion signature, never from ∫a."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from stilldot.sensors import high_pass, moving_rms
from stilldot.types import VehicleClass

# Pedestrian: Weinberg-style mapping from vertical bounce to stride.
# Vehicle: band energy around typical chassis/engine vibration.
PED_ZUPT_RMS = 0.22
VEH_ZUPT_RMS = 0.45
PED_BOUNCE_GAIN = 1.50
VEH_GAIN = 7.25
VEH_NOISE_FLOOR = 0.05


def band_energy(signal: NDArray[np.float64], rate_hz: float, lo: float, hi: float) -> float:
    if signal.size < 8:
        return 0.0
    spec = np.fft.rfft(signal * np.hanning(signal.size))
    freqs = np.fft.rfftfreq(signal.size, d=1.0 / rate_hz)
    mask = (freqs >= lo) & (freqs <= hi)
    if not np.any(mask):
        return 0.0
    return float(np.mean(np.abs(spec[mask]) ** 2) / signal.size)


def estimate_speed(
    acc_nav: NDArray[np.float64],
    gyro_nav: NDArray[np.float64],
    rate_hz: float,
    vehicle_class: VehicleClass,
) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
    """Windowed speed and ZUPT flags. One estimate per sample (causal)."""
    n = acc_nav.shape[0]
    speed = np.zeros(n, dtype=np.float64)
    zupt = np.zeros(n, dtype=np.bool_)
    if n == 0:
        return speed, zupt

    acc_hp = np.column_stack([high_pass(acc_nav[:, i]) for i in range(3)])
    bounce = moving_rms(acc_hp[:, 2], window=max(8, int(rate_hz * 0.4)))
    horiz = moving_rms(np.linalg.norm(acc_hp[:, :2], axis=1), window=max(8, int(rate_hz * 0.4)))
    gyro_rms = moving_rms(np.linalg.norm(gyro_nav, axis=1), window=max(8, int(rate_hz * 0.4)))

    win = max(16, int(rate_hz * 0.8))
    for i in range(n):
        a = 0 if i < win else i - win + 1
        sl = slice(a, i + 1)
        if vehicle_class is VehicleClass.PEDESTRIAN:
            still = bool(bounce[i] < PED_ZUPT_RMS and gyro_rms[i] < 0.12)
            zupt[i] = still
            if still:
                speed[i] = 0.0
            else:
                speed[i] = _pedestrian_speed(acc_hp[sl, 2], rate_hz, float(bounce[i]), float(horiz[i]))
        else:
            still = bool(horiz[i] < VEH_ZUPT_RMS and bounce[i] < VEH_ZUPT_RMS and gyro_rms[i] < 0.08)
            zupt[i] = still
            if still:
                speed[i] = 0.0
            else:
                vib = band_energy(acc_hp[sl, 2], rate_hz, 8.0, 24.0)
                raw = VEH_GAIN * np.sqrt(max(vib - VEH_NOISE_FLOOR, 0.0))
                speed[i] = float(np.clip(raw, 0.0, 40.0))

    # Causal EMA so a single noisy window does not shove the filter
    if n:
        ema = float(speed[0])
        alpha = 0.18
        for i in range(n):
            ema = speed[i] if zupt[i] else (1.0 - alpha) * ema + alpha * float(speed[i])
            speed[i] = ema

    return speed, zupt


def _dominant_freq(signal: NDArray[np.float64], rate_hz: float, lo: float, hi: float) -> float:
    if signal.size < 16:
        return 1.8
    spec = np.abs(np.fft.rfft(signal * np.hanning(signal.size)))
    freqs = np.fft.rfftfreq(signal.size, d=1.0 / rate_hz)
    mask = (freqs >= lo) & (freqs <= hi)
    if not np.any(mask):
        return 1.8
    peak = freqs[mask][int(np.argmax(spec[mask]))]
    return float(peak) if peak > 0.4 else 1.8


def _pedestrian_speed(
    vert_hp: NDArray[np.float64],
    rate_hz: float,
    bounce_rms: float,
    horiz_rms: float,
) -> float:
    amp = float(np.max(vert_hp) - np.min(vert_hp)) if vert_hp.size else 0.0
    freq = _dominant_freq(vert_hp, rate_hz, 1.6, 2.4)
    weinberg = 0.55 * max(amp, 0.0) ** 0.25 * freq
    bounce_speed = PED_BOUNCE_GAIN * bounce_rms + 0.12 * horiz_rms
    # Bounce RMS is the stable live signal; Weinberg helps when cadence is clean.
    blended = 0.75 * bounce_speed + 0.25 * weinberg
    return float(np.clip(blended, 0.0, 3.5))


def covariance_trust(
    gyro_nav: NDArray[np.float64],
    zupt: NDArray[np.bool_],
    odo_speed: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Stage 5 — how much to trust NHC / odometer right now.

    Straight, steady motion: trust the non-holonomic constraint. A hard
    turn, a pothole-scale gyro spike, or a ZUPT lock: widen it.
    """
    wz = np.abs(gyro_nav[:, 2])
    trust = np.ones(gyro_nav.shape[0], dtype=np.float64)
    trust -= np.clip(wz / 1.2, 0.0, 0.65)
    trust[zupt] = 0.95
    jerk = np.abs(np.diff(odo_speed, prepend=odo_speed[:1]))
    trust -= np.clip(jerk / 4.0, 0.0, 0.4)
    return np.clip(trust, 0.15, 1.0)
