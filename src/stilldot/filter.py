"""Stage 4 — 5-state error-state filter with odometer, NHC and ZUPT.

This is a heading-aware complementary filter with Kalman gains, not a full
Lie-group invariant EKF. The demo keeps the same measurement story: we never
double-integrate acceleration, and a stop is an exact zero-speed measurement.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass
class FilterState:
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0
    v: float = 0.0
    bg: float = 0.0


@dataclass
class NaiveState:
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0


def wrap_angle(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


class DeadReckonFilter:
    def __init__(self, process_v: float = 0.8, process_bg: float = 1e-5) -> None:
        self.state = FilterState()
        self.p = np.diag([0.05, 0.05, 0.05, 0.5, 0.01]).astype(np.float64)
        self.process_v = process_v
        self.process_bg = process_bg
        self.nhc_active = True

    def predict(self, gyro_z: float, dt: float, trust: float) -> None:
        if dt <= 0.0:
            return
        yaw_rate = gyro_z - self.state.bg
        self.state.yaw = wrap_angle(self.state.yaw + yaw_rate * dt)
        self.state.x += self.state.v * np.cos(self.state.yaw) * dt
        self.state.y += self.state.v * np.sin(self.state.yaw) * dt
        q = np.diag(
            [
                (0.02 * dt) ** 2,
                (0.02 * dt) ** 2,
                (0.01 * dt) ** 2,
                (self.process_v * dt) ** 2,
                self.process_bg * dt,
            ]
        )
        self.p = self.p + q
        self.nhc_active = trust > 0.45

    def update_odometer(self, speed: float, trust: float) -> None:
        r = 0.08 + (1.0 - trust) * 1.4
        self._scalar_update(3, speed, r)

    def update_zupt(self, gyro_z: float) -> None:
        self._scalar_update(3, 0.0, 0.02)
        # A stopped body has true yaw-rate zero, so gyro_z is the bias.
        self._scalar_update(4, gyro_z, 0.002)
        self.state.v = 0.0

    def _scalar_update(self, index: int, z: float, r: float) -> None:
        h = np.zeros(5)
        h[index] = 1.0
        x = np.array(
            [self.state.x, self.state.y, self.state.yaw, self.state.v, self.state.bg],
            dtype=np.float64,
        )
        innovation = z - float(h @ x)
        s = float(h @ self.p @ h + r)
        k = (self.p @ h) / s
        x = x + k * innovation
        self.p = (np.eye(5) - np.outer(k, h)) @ self.p
        self.state.x = float(x[0])
        self.state.y = float(x[1])
        self.state.yaw = wrap_angle(float(x[2]))
        self.state.v = float(x[3])
        self.state.bg = float(x[4])


class NaiveIntegrator:
    """The method the pitch argues against: integrate acceleration twice."""

    def __init__(self) -> None:
        self.state = NaiveState()

    def step(self, acc_fwd: float, acc_lat: float, yaw: float, dt: float) -> None:
        if dt <= 0.0:
            return
        self.state.vx += acc_fwd * np.cos(yaw) * dt - acc_lat * np.sin(yaw) * dt
        self.state.vy += acc_fwd * np.sin(yaw) * dt + acc_lat * np.cos(yaw) * dt
        self.state.x += self.state.vx * dt
        self.state.y += self.state.vy * dt


def horizontal_specific_force(acc_nav: NDArray[np.float64]) -> tuple[float, float]:
    return float(acc_nav[0]), float(acc_nav[1])
