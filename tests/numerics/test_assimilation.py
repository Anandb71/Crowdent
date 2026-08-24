from __future__ import annotations

import numpy as np
import pytest

from crowdent.numerics import (
    LinearObservationOperator,
    LocalizedDeterministicEnKF,
    ObservationBatch,
)


def _ensemble() -> np.ndarray:
    return np.array(
        [
            [0.5, 2.0, 0.0],
            [0.8, 2.2, 0.1],
            [1.0, 1.8, -0.1],
            [1.2, 2.1, 0.2],
            [1.5, 1.9, -0.2],
        ],
        dtype=float,
    )


def test_filter_moves_toy_ensemble_toward_observation_and_reports_mass_increment() -> None:
    ensemble = _ensemble()
    operator = LinearObservationOperator(
        matrix=np.array([[1.0, 0.0, 0.0]]),
        locations_m=np.array([[0.0, 0.0]]),
    )
    observations = ObservationBatch(
        values=np.array([1.8]),
        error_std=np.array([0.15]),
        operator=operator,
    )
    filter_ = LocalizedDeterministicEnKF(
        state_locations_m=np.array([[0.0, 0.0], [2.0, 0.0], [50.0, 0.0]]),
        localization_radius_m=10.0,
        covariance_floor=1e-6,
    )

    result = filter_.analyze(
        ensemble,
        observations,
        mass_weights=np.array([2.0, 2.0, 0.0]),
        nonnegative_indices=np.array([0, 1]),
    )

    assert abs(result.ensemble.mean(axis=0)[0] - 1.8) < abs(ensemble.mean(axis=0)[0] - 1.8)
    assert result.diagnostics.used_observations == 1
    assert np.isfinite(result.diagnostics.mass_increment_people)
    assert np.all(result.ensemble[:, :2] >= 0.0)
    assert np.all(result.ensemble.std(axis=0, ddof=1) >= 1e-6 - 1e-12)


def test_missing_observations_are_an_exact_noop() -> None:
    ensemble = _ensemble()
    operator = LinearObservationOperator(
        np.eye(3),
        np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]]),
    )
    observations = ObservationBatch(
        values=np.array([np.nan, np.nan, np.nan]),
        error_std=np.ones(3),
        operator=operator,
    )
    filter_ = LocalizedDeterministicEnKF(
        state_locations_m=np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]]),
        localization_radius_m=5.0,
    )

    result = filter_.analyze(ensemble, observations)

    np.testing.assert_array_equal(result.ensemble, ensemble)
    assert result.diagnostics.used_observations == 0
    assert result.diagnostics.mass_increment_people == 0.0


def test_batch_update_is_invariant_to_observation_permutation() -> None:
    ensemble = _ensemble()
    matrix = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    locations = np.array([[0.0, 0.0], [2.0, 0.0]])
    values = np.array([1.7, 1.5])
    errors = np.array([0.2, 0.3])
    filter_ = LocalizedDeterministicEnKF(
        state_locations_m=np.array([[0.0, 0.0], [2.0, 0.0], [50.0, 0.0]]),
        localization_radius_m=20.0,
    )

    original = ObservationBatch(
        values,
        errors,
        LinearObservationOperator(matrix, locations),
    )
    permutation = np.array([1, 0])
    permuted = ObservationBatch(
        values[permutation],
        errors[permutation],
        LinearObservationOperator(matrix[permutation], locations[permutation]),
    )

    a = filter_.analyze(ensemble, original).ensemble
    b = filter_.analyze(ensemble, permuted).ensemble

    np.testing.assert_allclose(a, b, rtol=1e-12, atol=1e-12)


def test_innovation_gate_rejects_extreme_observation() -> None:
    ensemble = _ensemble()
    observations = ObservationBatch(
        values=np.array([100.0]),
        error_std=np.array([0.1]),
        operator=LinearObservationOperator(
            np.array([[1.0, 0.0, 0.0]]),
            np.array([[0.0, 0.0]]),
        ),
        gate_sigma=3.0,
    )
    filter_ = LocalizedDeterministicEnKF(
        state_locations_m=np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]]),
        localization_radius_m=10.0,
    )

    result = filter_.analyze(ensemble, observations)

    np.testing.assert_array_equal(result.ensemble, ensemble)
    assert result.diagnostics.gated_observations == 1
    assert result.diagnostics.used_observations == 0


def test_invalid_covariance_and_shapes_are_rejected() -> None:
    with pytest.raises(ValueError):
        ObservationBatch(
            values=np.array([1.0]),
            error_std=np.array([0.0]),
            operator=LinearObservationOperator(
                np.array([[1.0, 0.0]]),
                np.array([[0.0, 0.0]]),
            ),
        )
