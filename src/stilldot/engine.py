"""Run the six-stage pipeline on a scenario or a live IMU batch."""

from __future__ import annotations

from typing import Literal

import numpy as np
from numpy.typing import NDArray

from stilldot.alignment import estimate_alignment, rotate_batch
from stilldot.filter import DeadReckonFilter, NaiveIntegrator, horizontal_specific_force
from stilldot.odometer import covariance_trust, estimate_speed
from stilldot.scenarios import SCENARIOS, SimulatedStream, simulate
from stilldot.sensors import interpolate_to_rate
from stilldot.types import Frame, ImuSample, RunMetrics, RunResult, ScenarioSpec, VehicleClass

Stage = Literal["idle", "align", "odometer", "filter", "zupt", "map"]


OUTPUT_HZ = 10.0
CAPTURE_HZ = 100.0


def _path_length(xy: NDArray[np.float64]) -> float:
    if xy.shape[0] < 2:
        return 0.0
    step = np.linalg.norm(np.diff(xy, axis=0), axis=1)
    return float(np.sum(step))


def _stage_name(zupt: bool, t: float, still_end: float, turning: bool) -> Stage:
    if t < 0.35:
        return "idle"
    if t < still_end:
        return "align"
    if zupt:
        return "zupt"
    if turning:
        return "odometer"
    return "filter"


def run_stream(stream: SimulatedStream, capture_hz: float = CAPTURE_HZ) -> RunResult:
    t, acc, gyro = interpolate_to_rate(
        stream.acc_t,
        stream.acc_phone,
        stream.gyro_t,
        stream.gyro_phone,
        rate_hz=capture_hz,
    )
    rot, yaw_deg = estimate_alignment(acc, gyro, capture_hz)
    acc_nav = rotate_batch(rot, acc)
    gyro_nav = rotate_batch(rot, gyro)
    odo, zupt = estimate_speed(acc_nav, gyro_nav, capture_hz, stream.spec.vehicle_class)
    trust = covariance_trust(gyro_nav, zupt, odo)

    filt = DeadReckonFilter()
    naive = NaiveIntegrator()
    dt = 1.0 / capture_hz
    stride = max(1, round(capture_hz / OUTPUT_HZ))
    frames: list[Frame] = []
    still_end = 1.8

    # Truth is on the original (unskewed) clock; resample onto t
    truth_x = np.interp(t, stream.t, stream.truth_xy[:, 0])
    truth_y = np.interp(t, stream.t, stream.truth_xy[:, 1])

    for i in range(t.size):
        filt.predict(float(gyro_nav[i, 2]), dt, float(trust[i]))
        if zupt[i]:
            filt.update_zupt(float(gyro_nav[i, 2]))
        else:
            filt.update_odometer(float(odo[i]), float(trust[i]))
        fwd, lat = horizontal_specific_force(acc_nav[i])
        naive.step(fwd, lat, filt.state.yaw, dt)

        if i % stride != 0 and i != t.size - 1:
            continue
        z = bool(zupt[i])
        stage = _stage_name(z, float(t[i]), still_end, abs(float(gyro_nav[i, 2])) > 0.25)
        frames.append(
            Frame(
                t=float(t[i]),
                x=filt.state.x,
                y=filt.state.y,
                heading=filt.state.yaw,
                speed=filt.state.v,
                truth_x=float(truth_x[i]),
                truth_y=float(truth_y[i]),
                naive_x=naive.state.x,
                naive_y=naive.state.y,
                zupt=z,
                nhc=filt.nhc_active,
                odo_speed=float(odo[i]),
                gnss_denied=True,
                alignment_yaw_deg=yaw_deg,
                trust=float(trust[i]),
                stage=stage,
            )
        )

    est = np.array([[f.x, f.y] for f in frames], dtype=np.float64)
    truth = np.array([[f.truth_x, f.truth_y] for f in frames], dtype=np.float64)
    naive_xy = np.array([[f.naive_x, f.naive_y] for f in frames], dtype=np.float64)
    distance = _path_length(truth)
    drift = float(np.linalg.norm(est[-1] - truth[-1])) if frames else 0.0
    naive_drift = float(np.linalg.norm(naive_xy[-1] - truth[-1])) if frames else 0.0
    duration = float(t[-1] - t[0]) if t.size else 0.0
    drift_pct = 100.0 * drift / distance if distance > 1e-6 else 0.0
    naive_pct = 100.0 * naive_drift / distance if distance > 1e-6 else 0.0

    return RunResult(
        scenario=stream.spec,
        metrics=RunMetrics(
            distance_m=distance,
            duration_s=duration,
            drift_m=drift,
            drift_pct=drift_pct,
            naive_drift_m=naive_drift,
            naive_drift_pct=naive_pct,
            requirement_pct=stream.spec.requirement_pct,
            requirement_met=drift_pct < stream.spec.requirement_pct,
            final_speed=frames[-1].speed if frames else 0.0,
            zupt_locked=bool(frames[-1].zupt) if frames else False,
            sample_hz=capture_hz,
            output_hz=OUTPUT_HZ,
        ),
        frames=frames,
        start=(float(truth[0, 0]), float(truth[0, 1])) if frames else (0.0, 0.0),
        end_truth=(float(truth[-1, 0]), float(truth[-1, 1])) if frames else (0.0, 0.0),
        end_estimate=(float(est[-1, 0]), float(est[-1, 1])) if frames else (0.0, 0.0),
    )


def run_scenario(scenario_id: str, seed: int = 7) -> RunResult:
    spec = SCENARIOS.get(scenario_id)
    if spec is None:
        known = ", ".join(SCENARIOS)
        raise KeyError(f"unknown scenario '{scenario_id}'. known: {known}")
    return run_stream(simulate(spec, rate_hz=CAPTURE_HZ, seed=seed))


def run_live_samples(
    samples: list[ImuSample],
    vehicle_class: VehicleClass = VehicleClass.PEDESTRIAN,
) -> RunResult:
    if len(samples) < 16:
        raise ValueError("need at least 16 IMU samples")
    spec = ScenarioSpec(
        id="live",
        title="Live phone IMU",
        pitch_line="Nothing leaves this machine. The track is the filter.",
        vehicle_class=vehicle_class,
        requirement_note="No surveyed end point — drift is distance from the origin, not a scored run.",
        honesty=[
            "Live DeviceMotion. No GNSS is fused.",
            "There is no surveyed ground truth on this run, so drift is not a PS score.",
        ],
    )
    t = np.array([s.t for s in samples], dtype=np.float64)
    acc = np.array([s.acc for s in samples], dtype=np.float64)
    gyro = np.array([s.gyro for s in samples], dtype=np.float64)
    # Live samples share a clock already; still run interpolation to 100 Hz.
    stream = SimulatedStream(
        spec=spec,
        t=t,
        acc_phone=acc,
        gyro_phone=gyro,
        acc_t=t,
        gyro_t=t,
        truth_xy=np.zeros((t.size, 2), dtype=np.float64),
        truth_yaw=np.zeros(t.size, dtype=np.float64),
        truth_speed=np.zeros(t.size, dtype=np.float64),
        mount_yaw_deg=0.0,
    )
    result = run_stream(stream)
    # Live has no truth: report path length of the estimate, drift unknown (NaN-like 0 with note)
    est = np.array([[f.x, f.y] for f in result.frames], dtype=np.float64)
    distance = _path_length(est)
    result.metrics.distance_m = distance
    result.metrics.drift_m = 0.0
    result.metrics.drift_pct = 0.0
    result.metrics.requirement_met = False
    return result
