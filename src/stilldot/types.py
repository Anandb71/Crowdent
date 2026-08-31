from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class VehicleClass(StrEnum):
    PEDESTRIAN = "pedestrian"
    VEHICLE = "vehicle"


class ImuSample(BaseModel):
    t: float
    acc: tuple[float, float, float]
    gyro: tuple[float, float, float]


class Frame(BaseModel):
    t: float
    x: float
    y: float
    heading: float
    speed: float
    truth_x: float
    truth_y: float
    naive_x: float
    naive_y: float
    zupt: bool
    nhc: bool
    odo_speed: float
    gnss_denied: bool
    alignment_yaw_deg: float
    trust: float
    stage: Literal[
        "idle",
        "align",
        "odometer",
        "filter",
        "zupt",
        "map",
    ]


class ScenarioSpec(BaseModel):
    id: str
    title: str
    pitch_line: str
    vehicle_class: VehicleClass
    requirement_pct: float = 10.0
    requirement_note: str
    honesty: list[str]


class RunMetrics(BaseModel):
    distance_m: float
    duration_s: float
    drift_m: float
    drift_pct: float
    naive_drift_m: float
    naive_drift_pct: float
    requirement_pct: float
    requirement_met: bool
    final_speed: float
    zupt_locked: bool
    sample_hz: float
    output_hz: float = 10.0


class RunResult(BaseModel):
    scenario: ScenarioSpec
    metrics: RunMetrics
    frames: list[Frame] = Field(default_factory=list)
    start: tuple[float, float]
    end_truth: tuple[float, float]
    end_estimate: tuple[float, float]
