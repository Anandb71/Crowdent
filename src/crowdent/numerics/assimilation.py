"""Localized deterministic ensemble data assimilation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class LinearObservationOperator:
    matrix: FloatArray
    locations_m: FloatArray

    def __post_init__(self) -> None:
        matrix = np.asarray(self.matrix, dtype=float)
        locations = np.asarray(self.locations_m, dtype=float)
        if matrix.ndim != 2:
            raise ValueError("observation matrix must be two-dimensional")
        if locations.shape != (matrix.shape[0], 2):
            raise ValueError("observation locations must have shape (observations, 2)")
        if not np.all(np.isfinite(matrix)) or not np.all(np.isfinite(locations)):
            raise ValueError("observation operator must be finite")
        object.__setattr__(self, "matrix", matrix.copy())
        object.__setattr__(self, "locations_m", locations.copy())

    def apply(self, ensemble: FloatArray) -> FloatArray:
        return ensemble @ self.matrix.T


@dataclass(frozen=True, slots=True)
class ObservationBatch:
    values: FloatArray
    error_std: FloatArray
    operator: LinearObservationOperator
    gate_sigma: float = 6.0

    def __post_init__(self) -> None:
        values = np.asarray(self.values, dtype=float)
        error = np.asarray(self.error_std, dtype=float)
        count = self.operator.matrix.shape[0]
        if values.shape != (count,) or error.shape != (count,):
            raise ValueError("observation values and errors must match operator rows")
        if np.any(~np.isfinite(error)) or np.any(error <= 0):
            raise ValueError("observation error standard deviations must be positive")
        if self.gate_sigma <= 0 or not np.isfinite(self.gate_sigma):
            raise ValueError("gate_sigma must be finite and positive")
        object.__setattr__(self, "values", values.copy())
        object.__setattr__(self, "error_std", error.copy())


@dataclass(frozen=True, slots=True)
class AssimilationDiagnostics:
    used_observations: int
    gated_observations: int
    missing_observations: int
    mass_increment_people: float
    innovation_norm: float


@dataclass(frozen=True, slots=True)
class AssimilationResult:
    ensemble: FloatArray
    diagnostics: AssimilationDiagnostics


class LocalizedDeterministicEnKF:
    """Batch deterministic EnKF with distance-based covariance localization."""

    def __init__(
        self,
        *,
        state_locations_m: FloatArray,
        localization_radius_m: float,
        covariance_floor: float = 1e-9,
    ) -> None:
        locations = np.asarray(state_locations_m, dtype=float)
        if locations.ndim != 2 or locations.shape[1] != 2:
            raise ValueError("state_locations_m must have shape (state, 2)")
        if not np.all(np.isfinite(locations)):
            raise ValueError("state locations must be finite")
        if localization_radius_m <= 0 or covariance_floor < 0:
            raise ValueError("localization radius must be positive and floor nonnegative")
        self.state_locations_m = locations.copy()
        self.localization_radius_m = float(localization_radius_m)
        self.covariance_floor = float(covariance_floor)

    def analyze(
        self,
        ensemble: FloatArray,
        observations: ObservationBatch,
        *,
        mass_weights: FloatArray | None = None,
        nonnegative_indices: NDArray[np.integer] | None = None,
    ) -> AssimilationResult:
        prior = np.asarray(ensemble, dtype=float)
        if prior.ndim != 2 or prior.shape[0] < 3:
            raise ValueError("ensemble must have shape (at least 3 members, state)")
        if prior.shape[1] != self.state_locations_m.shape[0]:
            raise ValueError("ensemble state size must match state locations")
        if observations.operator.matrix.shape[1] != prior.shape[1]:
            raise ValueError("observation operator state size mismatch")
        if not np.all(np.isfinite(prior)):
            raise ValueError("ensemble must be finite")

        projected = observations.operator.apply(prior)
        projected_mean = projected.mean(axis=0)
        projected_anomalies = projected - projected_mean
        missing = ~np.isfinite(observations.values)
        sample_variance = projected_anomalies.var(axis=0, ddof=1)
        normalized_innovation = np.zeros_like(observations.values)
        valid = ~missing
        normalized_innovation[valid] = np.abs(
            observations.values[valid] - projected_mean[valid]
        ) / np.sqrt(sample_variance[valid] + observations.error_std[valid] ** 2)
        gated = valid & (normalized_innovation > observations.gate_sigma)
        used = valid & ~gated
        if not np.any(used):
            return AssimilationResult(
                ensemble=prior.copy(),
                diagnostics=AssimilationDiagnostics(
                    used_observations=0,
                    gated_observations=int(gated.sum()),
                    missing_observations=int(missing.sum()),
                    mass_increment_people=0.0,
                    innovation_norm=0.0,
                ),
            )

        selected_values = observations.values[used]
        selected_errors = observations.error_std[used]
        selected_matrix = observations.operator.matrix[used]
        selected_locations = observations.operator.locations_m[used]
        n_members = prior.shape[0]
        prior_mean = prior.mean(axis=0)
        anomalies = prior - prior_mean
        projected_selected = prior @ selected_matrix.T
        projected_selected_mean = projected_selected.mean(axis=0)
        projected_selected_anomalies = projected_selected - projected_selected_mean
        cross_covariance = anomalies.T @ projected_selected_anomalies / (n_members - 1)
        distances = np.linalg.norm(
            self.state_locations_m[:, None, :] - selected_locations[None, :, :],
            axis=2,
        )
        localization = _gaspari_cohn(distances / self.localization_radius_m)
        localized_cross = cross_covariance * localization
        observation_covariance = (
            projected_selected_anomalies.T @ projected_selected_anomalies
            / (n_members - 1)
            + np.diag(selected_errors**2)
        )
        gain = localized_cross @ np.linalg.pinv(
            observation_covariance,
            hermitian=True,
        )
        innovation = selected_values - projected_selected_mean
        posterior_mean = prior_mean + gain @ innovation

        # Deterministic EnKF anomaly update. Batch algebra makes the result
        # independent of observation order.
        posterior_anomalies = anomalies - 0.5 * (
            projected_selected_anomalies @ gain.T
        )
        posterior = posterior_mean + posterior_anomalies

        if nonnegative_indices is not None:
            indices = np.asarray(nonnegative_indices, dtype=int)
            if np.any((indices < 0) | (indices >= posterior.shape[1])):
                raise ValueError("nonnegative index out of bounds")
            posterior[:, indices] = np.maximum(posterior[:, indices], 0.0)
        posterior = _apply_spread_floor(posterior, self.covariance_floor)

        increment = 0.0
        if mass_weights is not None:
            weights = np.asarray(mass_weights, dtype=float)
            if weights.shape != (prior.shape[1],) or not np.all(np.isfinite(weights)):
                raise ValueError("mass_weights must be finite and match state size")
            increment = float((posterior.mean(axis=0) - prior_mean) @ weights)
        return AssimilationResult(
            ensemble=posterior,
            diagnostics=AssimilationDiagnostics(
                used_observations=int(used.sum()),
                gated_observations=int(gated.sum()),
                missing_observations=int(missing.sum()),
                mass_increment_people=increment,
                innovation_norm=float(np.linalg.norm(innovation)),
            ),
        )


def _gaspari_cohn(distance_ratio: FloatArray) -> FloatArray:
    """Compactly supported Gaspari-Cohn taper for ratio distance/radius."""

    ratio = np.abs(np.asarray(distance_ratio, dtype=float))
    result = np.zeros_like(ratio)
    first = ratio <= 1
    r = ratio[first]
    result[first] = (
        1
        - (5 / 3) * r**2
        + (5 / 8) * r**3
        + 0.5 * r**4
        - 0.25 * r**5
    )
    second = (ratio > 1) & (ratio < 2)
    r = ratio[second]
    result[second] = (
        4
        - 5 * r
        + (5 / 3) * r**2
        + (5 / 8) * r**3
        - 0.5 * r**4
        + (1 / 12) * r**5
        - 2 / (3 * r)
    )
    return np.clip(result, 0.0, 1.0)


def _apply_spread_floor(ensemble: FloatArray, floor: float) -> FloatArray:
    if floor <= 0:
        return ensemble
    output = ensemble.copy()
    standard_deviation = output.std(axis=0, ddof=1)
    deficient = np.flatnonzero(standard_deviation < floor)
    if deficient.size:
        pattern = np.linspace(-1.0, 1.0, output.shape[0])
        pattern -= pattern.mean()
        pattern /= pattern.std(ddof=1)
        for index in deficient:
            output[:, index] = output[:, index].mean() + pattern * floor
    return output


__all__ = [
    "AssimilationDiagnostics",
    "AssimilationResult",
    "LinearObservationOperator",
    "LocalizedDeterministicEnKF",
    "ObservationBatch",
]
