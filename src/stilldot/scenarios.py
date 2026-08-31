"""Synthetic IMU + surveyed ground truth for the two pitch demos.

These are not IO-VNBD recordings. They exist so the laptop fallback in the
demo script is deterministic with the network physically off.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from stilldot.alignment import rotation_from_rpy
from stilldot.sensors import G
from stilldot.types import ScenarioSpec, VehicleClass

ROOM = ScenarioSpec(
    id="room_walk",
    title="Room walk · 50 m L-path",
    pitch_line="GPS is off. Airplane mode. Watch the track.",
    vehicle_class=VehicleClass.PEDESTRIAN,
    requirement_pct=10.0,
    requirement_note="Problem statement worked example: under 5 m drift over 50 m denied.",
    honesty=[
        "Synthetic surveyed path, not a live GNSS log.",
        "Pedestrian bounce model — the vehicle network is the tunnel run.",
        "Hold-out country numbers are not claimed here.",
    ],
)

TUNNEL = ScenarioSpec(
    id="tunnel",
    title="Tunnel · 1 km at 60 km/h",
    pitch_line="One kilometre of denied rail. The filter never saw this path in training.",
    vehicle_class=VehicleClass.VEHICLE,
    requirement_pct=10.0,
    requirement_note="Problem statement worked example: under 100 m over 1 km denied at 60 km/h.",
    honesty=[
        "Synthetic chassis vibration, not IO-VNBD.",
        "Speed comes from the 8-24 Hz band, not from a wheel encoder.",
        "No map matching is applied - odometry plus constraints only.",
    ],
)

SCENARIOS: dict[str, ScenarioSpec] = {ROOM.id: ROOM, TUNNEL.id: TUNNEL}


@dataclass
class SimulatedStream:
    spec: ScenarioSpec
    t: NDArray[np.float64]
    acc_phone: NDArray[np.float64]
    gyro_phone: NDArray[np.float64]
    acc_t: NDArray[np.float64]
    gyro_t: NDArray[np.float64]
    truth_xy: NDArray[np.float64]
    truth_yaw: NDArray[np.float64]
    truth_speed: NDArray[np.float64]
    mount_yaw_deg: float


def _piecewise_path(
    segments: list[tuple[float, float, float]],
    dt: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """segments: (duration_s, speed_mps, yaw_rate_rad_s)."""
    xs: list[float] = []
    ys: list[float] = []
    yaws: list[float] = []
    speeds: list[float] = []
    x = 0.0
    y = 0.0
    yaw = 0.0
    for duration, speed, yaw_rate in segments:
        n = max(1, round(duration / dt))
        for _ in range(n):
            yaw += yaw_rate * dt
            x += speed * np.cos(yaw) * dt
            y += speed * np.sin(yaw) * dt
            xs.append(x)
            ys.append(y)
            yaws.append(yaw)
            speeds.append(speed)
    return (
        np.array(xs),
        np.array(ys),
        np.array(yaws),
        np.array(speeds),
    )


def _room_segments() -> list[tuple[float, float, float]]:
    walk = 1.35
    leg = 25.0 / walk
    turn = 1.6
    return [
        (2.2, 0.0, 0.0),
        (leg, walk, 0.0),
        (turn, 0.35, (np.pi / 2) / turn),
        (leg, walk, 0.0),
        (3.0, 0.0, 0.0),
    ]


def _tunnel_segments() -> list[tuple[float, float, float]]:
    v = 60_000 / 3_600  # 16.667 m/s
    # Gentle S-curve so heading error is visible, then a long straight.
    cruise = max(8.0, 1000.0 / v - 32.0)
    return [
        (2.0, 0.0, 0.0),
        (8.0, v, 0.0),
        (6.0, v, 0.08),
        (6.0, v, -0.08),
        (6.0, v, -0.08),
        (6.0, v, 0.08),
        (cruise, v, 0.0),
        (2.5, 0.0, 0.0),
    ]


def simulate(
    spec: ScenarioSpec,
    rate_hz: float = 100.0,
    seed: int = 7,
    stamp_skew_s: float = 0.004,
) -> SimulatedStream:
    rng = np.random.default_rng(seed)
    dt = 1.0 / rate_hz
    segments = _room_segments() if spec.id == ROOM.id else _tunnel_segments()
    x, y, yaw, speed = _piecewise_path(segments, dt)
    n = x.size
    t = np.arange(n, dtype=np.float64) * dt

    mount_roll, mount_pitch, mount_yaw = 0.12, -0.08, 0.18
    r_nav_from_phone = rotation_from_rpy(mount_roll, mount_pitch, mount_yaw)
    r_phone_from_nav = r_nav_from_phone.T

    acc_nav = np.zeros((n, 3), dtype=np.float64)
    gyro_nav = np.zeros((n, 3), dtype=np.float64)
    acc_nav[:, 2] = G

    if spec.vehicle_class is VehicleClass.PEDESTRIAN:
        step_w = 2.0 * np.pi * 1.85
        bounce = 1.65 * np.sin(step_w * t) * (speed > 0.2)
        acc_nav[:, 2] += bounce
        acc_nav[:, 0] += 0.35 * np.sin(step_w * t + 0.6) * (speed > 0.2)
        gyro_nav[:, 1] += 0.18 * np.sin(step_w * t) * (speed > 0.2)
    else:
        vib_w = 2.0 * np.pi * 16.0
        acc_nav[:, 2] += 0.22 * speed * np.sin(vib_w * t)
        acc_nav[:, 0] += 0.06 * speed * np.sin(vib_w * t + 0.5)
        acc_nav[:, 1] += 0.03 * speed * np.sin(vib_w * t + 1.1)

    # Kinematic yaw rate in nav frame
    yaw_rate = np.gradient(yaw, dt)
    gyro_nav[:, 2] += yaw_rate

    # Small tangential accel from speed changes
    speed_dot = np.gradient(speed, dt)
    acc_nav[:, 0] += speed_dot

    acc_bias = np.array([0.08, -0.03, 0.02])
    gyro_bias = np.array([0.002, -0.0015, 0.0012])
    acc_noise = 0.04 if spec.vehicle_class is VehicleClass.PEDESTRIAN else 0.12
    gyro_noise = 0.008

    acc_phone = (r_phone_from_nav @ acc_nav.T).T + acc_bias + rng.normal(0.0, acc_noise, (n, 3))
    gyro_phone = (r_phone_from_nav @ gyro_nav.T).T + gyro_bias + rng.normal(0.0, gyro_noise, (n, 3))

    # Deliberate timestamp skew so stage 1 has work to do
    acc_t = t.copy()
    gyro_t = t + stamp_skew_s
    return SimulatedStream(
        spec=spec,
        t=t,
        acc_phone=acc_phone,
        gyro_phone=gyro_phone,
        acc_t=acc_t,
        gyro_t=gyro_t,
        truth_xy=np.column_stack([x, y]),
        truth_yaw=yaw,
        truth_speed=speed,
        mount_yaw_deg=float(np.degrees(mount_yaw)),
    )


def list_scenarios() -> list[ScenarioSpec]:
    return [ROOM, TUNNEL]
