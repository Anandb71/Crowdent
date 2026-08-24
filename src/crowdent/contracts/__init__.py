"""Versioned boundary contracts for Crowdent.

Contracts deliberately keep units, provenance, quality and readiness visible.
They are the serialization boundary; numerical hot loops use NumPy arrays.
"""

from __future__ import annotations

import math
from datetime import datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = 1
SHA256_PATTERN = r"^[0-9a-f]{64}$"


class RuntimeMode(StrEnum):
    DEMO_DETERMINISTIC = "DEMO_DETERMINISTIC"
    REPLAY_RESEARCH = "REPLAY_RESEARCH"
    FIELD_RESEARCH = "FIELD_RESEARCH"


class ReadinessState(StrEnum):
    READY = "READY"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"


class QualityFlag(StrEnum):
    STALE_INPUT = "STALE_INPUT"
    CONFLICTING_INPUT = "CONFLICTING_INPUT"
    MISSING_INPUT = "MISSING_INPUT"
    INVALID_CALIBRATION = "INVALID_CALIBRATION"
    OUT_OF_DOMAIN = "OUT_OF_DOMAIN"
    ENSEMBLE_FAILURE = "ENSEMBLE_FAILURE"
    NUMERICAL_FAILURE = "NUMERICAL_FAILURE"
    CLOCK_ERROR = "CLOCK_ERROR"


class InstructionLifecycle(StrEnum):
    DRAFT = "draft"
    ACKNOWLEDGED = "acknowledged"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    PHYSICAL_ACTION_CONFIRMED = "physical_action_confirmed"


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
        allow_inf_nan=False,
        use_enum_values=False,
    )


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value


def _finite_nested(value: Any, *, field_name: str) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (float, int)):
        if not math.isfinite(float(value)):
            raise ValueError(f"{field_name} values must be finite")
        return value
    if isinstance(value, (list, tuple)):
        for item in value:
            _finite_nested(item, field_name=field_name)
    return value


def _validate_covariance(value: tuple[tuple[float, ...], ...]) -> tuple[tuple[float, ...], ...]:
    if not value:
        raise ValueError("covariance must not be empty")
    width = len(value)
    if any(len(row) != width for row in value):
        raise ValueError("covariance must be square")
    _finite_nested(value, field_name="covariance")
    for row in range(width):
        if value[row][row] < 0:
            raise ValueError("covariance diagonal must be nonnegative")
        for column in range(row + 1, width):
            if not math.isclose(
                value[row][column],
                value[column][row],
                rel_tol=1e-9,
                abs_tol=1e-12,
            ):
                raise ValueError("covariance must be symmetric")
    return value


class Provenance(StrictModel):
    source_id: str = Field(min_length=1)
    observed_at: datetime
    sequence: int = Field(ge=0)
    content_hash: str = Field(pattern=SHA256_PATTERN)
    transformations: tuple[str, ...] = ()

    _timestamp_is_aware = field_validator("observed_at")(_aware)


class EventMetadata(StrictModel):
    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)
    timestamp: datetime
    source_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    site_id: str = Field(min_length=1)
    sequence: int = Field(ge=0)
    config_hash: str = Field(pattern=SHA256_PATTERN)
    model_hash: str = Field(pattern=SHA256_PATTERN)
    calibration_hash: str = Field(pattern=SHA256_PATTERN)
    research_only: bool = True

    _timestamp_is_aware = field_validator("timestamp")(_aware)

    @field_validator("research_only")
    @classmethod
    def _research_only_cannot_be_disabled(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Crowdent outputs are research-only")
        return value


class FusedStateSummary(EventMetadata):
    mean: tuple[float, ...]
    covariance: tuple[tuple[float, ...], ...]
    density_people_per_m2: float = Field(ge=0)
    speed_mps: float = Field(ge=0)
    units: dict[str, str]
    coordinate_frame: str = Field(min_length=1)
    provenance: tuple[Provenance, ...]

    @field_validator("mean")
    @classmethod
    def _mean_is_finite(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        if not value:
            raise ValueError("mean must not be empty")
        _finite_nested(value, field_name="mean")
        return value

    _covariance_is_valid = field_validator("covariance")(_validate_covariance)

    @model_validator(mode="after")
    def _dimensions_match(self) -> Self:
        if len(self.covariance) != len(self.mean):
            raise ValueError("covariance dimension must match mean")
        return self


class Forecast(EventMetadata):
    target_timestamp: datetime
    horizon_seconds: int = Field(gt=0)
    risk_probability: float | None = Field(default=None, ge=0, le=1)
    risk_interval: tuple[float, float] | None = None
    covariance: tuple[tuple[float, ...], ...]
    readiness: ReadinessState
    quality_flags: tuple[QualityFlag, ...] = ()
    countdown_seconds: int | None = Field(default=None, ge=0)
    advice: tuple[str, ...] = ()
    units: dict[str, str]
    coordinate_frame: str = Field(min_length=1)
    provenance: tuple[Provenance, ...]

    _target_is_aware = field_validator("target_timestamp")(_aware)
    _covariance_is_valid = field_validator("covariance")(_validate_covariance)

    @model_validator(mode="after")
    def _validate_forecast_semantics(self) -> Self:
        if self.target_timestamp <= self.timestamp:
            raise ValueError("target_timestamp must be after timestamp")
        if self.risk_interval is not None:
            low, high = self.risk_interval
            if not 0 <= low <= high <= 1:
                raise ValueError("risk_interval must be ordered within [0, 1]")
            if self.risk_probability is not None and not low <= self.risk_probability <= high:
                raise ValueError("risk_probability must lie inside risk_interval")
        if self.readiness is not ReadinessState.READY:
            if self.countdown_seconds is not None:
                raise ValueError("countdown is forbidden unless readiness is READY")
            if self.advice:
                raise ValueError("advice is forbidden unless readiness is READY")
        return self


class SensorHealth(StrictModel):
    source_id: str
    observed_at: datetime | None = None
    age_seconds: float | None = Field(default=None, ge=0)
    quality_flags: tuple[QualityFlag, ...] = ()
    readiness: ReadinessState = ReadinessState.UNKNOWN
    clock_error_seconds: float | None = Field(default=None, ge=0)

    @field_validator("observed_at")
    @classmethod
    def _optional_timestamp_is_aware(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _aware(value)


class InterventionScenario(StrictModel):
    scenario_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    parameters: dict[str, str | int | float | bool]
    assumptions: tuple[str, ...] = ()
    violated_constraints: tuple[str, ...] = ()
    permitted: bool = False
    recommendations: tuple[str, ...] = ()
    countdown_seconds: int | None = Field(default=None, ge=0)
    research_only: bool = True


class InstructionDraft(StrictModel):
    instruction_id: str
    scenario_id: str
    recommendation: str
    text: str
    created_at: datetime
    expires_at: datetime
    lifecycle: InstructionLifecycle = InstructionLifecycle.DRAFT
    actor_id: str
    reason: str | None = None
    research_only: bool = True
    hardware_actuation_available: bool = False

    _created_is_aware = field_validator("created_at")(_aware)
    _expires_is_aware = field_validator("expires_at")(_aware)

    @model_validator(mode="after")
    def _expiry_is_future(self) -> Self:
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")
        if self.hardware_actuation_available:
            raise ValueError("hardware actuation is not available")
        return self


class ApprovalDecision(StrictModel):
    instruction_id: str
    actor_id: str
    actor_role: str
    lifecycle: InstructionLifecycle
    reason: str
    timestamp: datetime
    research_only: bool = True

    _timestamp_is_aware = field_validator("timestamp")(_aware)


class AuditRecord(StrictModel):
    sequence: int = Field(ge=1)
    timestamp: datetime
    event_type: str
    actor_id: str
    actor_role: str
    payload: dict[str, Any]
    previous_hash: str = Field(pattern=SHA256_PATTERN)
    entry_hash: str = Field(pattern=SHA256_PATTERN)
    research_only: bool = True

    _timestamp_is_aware = field_validator("timestamp")(_aware)


__all__ = [
    "SCHEMA_VERSION",
    "ApprovalDecision",
    "AuditRecord",
    "EventMetadata",
    "Forecast",
    "FusedStateSummary",
    "InstructionDraft",
    "InstructionLifecycle",
    "InterventionScenario",
    "Provenance",
    "QualityFlag",
    "ReadinessState",
    "RuntimeMode",
    "SensorHealth",
]
