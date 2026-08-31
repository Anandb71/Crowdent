"""Stage 2 — phone-to-vehicle (or phone-to-path) rotation."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from stilldot.sensors import G


def gravity_roll_pitch(acc: NDArray[np.float64]) -> tuple[float, float]:
    """Roll and pitch from a low-passed accelerometer reading (phone frame)."""
    ax, ay, az = (float(v) for v in acc)
    norm = float(np.linalg.norm([ax, ay, az])) or 1.0
    ax, ay, az = ax / norm, ay / norm, az / norm
    roll = float(np.arctan2(ay, az))
    pitch = float(np.arctan2(-ax, np.sqrt(ay * ay + az * az)))
    return roll, pitch


def rotation_from_rpy(roll: float, pitch: float, yaw: float = 0.0) -> NDArray[np.float64]:
    """R such that v_nav = R @ v_phone, Z-up, yaw from +X toward +Y."""
    cr, sr = np.cos(roll), np.sin(roll)
    cp, sp = np.cos(pitch), np.sin(pitch)
    cy, sy = np.cos(yaw), np.sin(yaw)
    rz = np.array([[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    ry = np.array([[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]], dtype=np.float64)
    rx = np.array([[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]], dtype=np.float64)
    return np.asarray(rz @ ry @ rx, dtype=np.float64)


def estimate_alignment(
    acc: NDArray[np.float64],
    gyro: NDArray[np.float64],
    rate_hz: float,
) -> tuple[NDArray[np.float64], float]:
    """Estimate phone-to-nav rotation from gravity, then yaw from first motion.

    Gravity gives two angles. Yaw comes from the direction of the strongest
    horizontal specific force once the body starts moving — the same idea as
    using braking/acceleration on a vehicle, applied to the first steps here.
    """
    if acc.shape[0] < int(rate_hz):
        raise ValueError("need at least one second of IMU to align")

    n_still = min(acc.shape[0], int(rate_hz * 1.5))
    g_phone = acc[:n_still].mean(axis=0)
    roll, pitch = gravity_roll_pitch(g_phone)
    r_rp = rotation_from_rpy(roll, pitch, 0.0)

    acc_nav = (r_rp @ acc.T).T
    horizontal = acc_nav[:, :2] - np.array([0.0, 0.0])
    # specific force besides gravity
    horiz_mag = np.linalg.norm(horizontal, axis=1)
    gyro_mag = np.linalg.norm(gyro, axis=1)
    moving = (horiz_mag > 0.35) | (gyro_mag > 0.15)
    if not np.any(moving):
        return r_rp, 0.0

    idx = int(np.argmax(moving))
    window = acc_nav[idx : min(acc_nav.shape[0], idx + int(rate_hz))]
    mean_h = window[:, :2].mean(axis=0)
    yaw = (
        0.0
        if float(np.linalg.norm(mean_h)) < 1e-6
        else float(np.arctan2(mean_h[1], mean_h[0]))
    )
    rot = rotation_from_rpy(roll, pitch, -yaw)
    return rot, float(np.degrees(-yaw))


def rotate_batch(rot: NDArray[np.float64], vectors: NDArray[np.float64]) -> NDArray[np.float64]:
    return (rot @ vectors.T).T


def gravity_vector() -> NDArray[np.float64]:
    return np.array([0.0, 0.0, G], dtype=np.float64)
