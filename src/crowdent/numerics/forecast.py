"""Probabilistic forecast summaries, baselines and fair counterfactuals."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
DEFAULT_LEAD_TIMES_MIN = (5, 10, 15, 30, 45, 60)


@dataclass(frozen=True, slots=True)
class ForecastSummary:
    lead_time_min: int
    quantiles: dict[float, FloatArray]
    threshold_exceedance: dict[str, FloatArray]
    ensemble_size: int


def summarize_forecast(
    samples_by_lead: Mapping[int, NDArray[np.floating]],
    *,
    quantiles: tuple[float, ...] = (0.1, 0.5, 0.9),
    thresholds: Mapping[str, float] | None = None,
) -> dict[int, ForecastSummary]:
    if not samples_by_lead:
        raise ValueError("forecast samples are required")
    if not quantiles or any(not 0 <= value <= 1 for value in quantiles):
        raise ValueError("quantiles must lie within [0, 1]")
    configured_thresholds = dict(thresholds or {})
    if any(
        not name or not np.isfinite(value) or value < 0
        for name, value in configured_thresholds.items()
    ):
        raise ValueError("threshold names must be nonempty and values nonnegative")
    result: dict[int, ForecastSummary] = {}
    expected_shape: tuple[int, ...] | None = None
    for lead in sorted(samples_by_lead):
        samples = np.asarray(samples_by_lead[lead], dtype=float)
        if lead <= 0 or samples.ndim < 2 or samples.shape[0] < 2:
            raise ValueError("each lead requires at least two ensemble members")
        if not np.all(np.isfinite(samples)):
            raise ValueError("forecast samples must be finite")
        if expected_shape is None:
            expected_shape = samples.shape[1:]
        elif samples.shape[1:] != expected_shape:
            raise ValueError("all lead times must share a state shape")
        quantile_values = {
            value: np.quantile(samples, value, axis=0) for value in quantiles
        }
        exceedance = {
            name: np.mean(samples > threshold, axis=0)
            for name, threshold in configured_thresholds.items()
        }
        result[lead] = ForecastSummary(
            lead_time_min=lead,
            quantiles=quantile_values,
            threshold_exceedance=exceedance,
            ensemble_size=samples.shape[0],
        )
    return result


def persistence_baseline(
    state: NDArray[np.floating],
    *,
    lead_times_min: tuple[int, ...] = DEFAULT_LEAD_TIMES_MIN,
) -> dict[int, FloatArray]:
    current = _finite_array(state, "state")
    return {lead: current.copy() for lead in _lead_times(lead_times_min)}


def no_assimilation_baseline(
    forecast: Mapping[int, NDArray[np.floating]],
) -> dict[int, FloatArray]:
    return {
        int(lead): _finite_array(value, "forecast").copy()
        for lead, value in sorted(forecast.items())
    }


def schedule_baseline(
    state: NDArray[np.floating],
    schedule_delta_by_lead: Mapping[int, NDArray[np.floating]],
) -> dict[int, FloatArray]:
    current = _finite_array(state, "state")
    result: dict[int, FloatArray] = {}
    for lead, delta in sorted(schedule_delta_by_lead.items()):
        increment = _finite_array(delta, "schedule delta")
        if increment.shape != current.shape:
            raise ValueError("schedule delta shape must match state")
        result[int(lead)] = current + increment
    return result


@dataclass(frozen=True, slots=True)
class Intervention:
    name: str
    gate_open_fraction: Mapping[str, float] = field(default_factory=dict)
    inflow_multiplier: Mapping[str, float] = field(default_factory=dict)
    adjacent_zone_capacity_people: Mapping[str, float] = field(default_factory=dict)
    projected_adjacent_zone_people: Mapping[str, float] = field(default_factory=dict)
    egress_capacity_people_per_s: Mapping[str, float] = field(default_factory=dict)
    requested_egress_people_per_s: Mapping[str, float] = field(default_factory=dict)

    def validate_constraints(self) -> None:
        if not self.name:
            raise ValueError("intervention name is required")
        for gate, fraction in self.gate_open_fraction.items():
            if not 0 <= fraction <= 1:
                raise ValueError(f"gate fraction for {gate} must be in [0, 1]")
        for entry, multiplier in self.inflow_multiplier.items():
            if not np.isfinite(multiplier) or multiplier < 0:
                raise ValueError(f"inflow multiplier for {entry} must be nonnegative")
        for zone, projected in self.projected_adjacent_zone_people.items():
            capacity = self.adjacent_zone_capacity_people.get(zone)
            if capacity is None:
                raise ValueError(f"adjacent-zone capacity missing for {zone}")
            if projected < 0 or capacity < 0 or projected > capacity:
                raise ValueError(f"adjacent-zone capacity exceeded for {zone}")
        for gate, requested in self.requested_egress_people_per_s.items():
            capacity = self.egress_capacity_people_per_s.get(gate)
            if capacity is None:
                raise ValueError(f"egress capacity missing for {gate}")
            if requested < 0 or capacity < 0 or requested > capacity:
                raise ValueError(f"egress capacity exceeded for {gate}")


Simulator = Callable[
    [FloatArray, Intervention, np.random.Generator, tuple[int, ...]],
    Mapping[int, NDArray[np.floating]],
]


def branch_counterfactuals(
    ensemble_members: NDArray[np.floating],
    interventions: Mapping[str, Intervention],
    simulator: Simulator,
    *,
    seed: int,
    lead_times_min: tuple[int, ...] = DEFAULT_LEAD_TIMES_MIN,
) -> dict[str, dict[int, FloatArray]]:
    """Run branches with common random numbers for fair comparisons."""

    members = _finite_array(ensemble_members, "ensemble")
    if members.ndim < 2 or members.shape[0] < 1:
        raise ValueError("ensemble must contain at least one member")
    leads = _lead_times(lead_times_min)
    branches: dict[str, dict[int, FloatArray]] = {}
    for branch_name, intervention in interventions.items():
        intervention.validate_constraints()
        collected: dict[int, list[FloatArray]] = {lead: [] for lead in leads}
        for member_index, member in enumerate(members):
            # Recreating the member stream for each branch guarantees common
            # random numbers without allowing one simulator call to affect another.
            rng = np.random.default_rng(np.random.SeedSequence([seed, member_index]))
            outputs = simulator(member.copy(), intervention, rng, leads)
            if set(outputs) != set(leads):
                raise ValueError("simulator must return every requested lead time")
            for lead in leads:
                collected[lead].append(_finite_array(outputs[lead], "simulation output"))
        branches[branch_name] = {
            lead: np.stack(values, axis=0) for lead, values in collected.items()
        }
    return branches


def _lead_times(values: tuple[int, ...]) -> tuple[int, ...]:
    if not values or any(value <= 0 for value in values) or len(set(values)) != len(values):
        raise ValueError("lead times must be unique positive minutes")
    return tuple(values)


def _finite_array(value: NDArray[np.floating], name: str) -> FloatArray:
    array = np.asarray(value, dtype=float)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be finite")
    return array


__all__ = [
    "DEFAULT_LEAD_TIMES_MIN",
    "ForecastSummary",
    "Intervention",
    "branch_counterfactuals",
    "no_assimilation_baseline",
    "persistence_baseline",
    "schedule_baseline",
    "summarize_forecast",
]
