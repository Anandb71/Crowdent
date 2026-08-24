"""Scoring rules are checked against closed forms, not against themselves."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from crowdent.verification import (
    brier_decomposition,
    brier_score,
    crps_ensemble,
    crps_gaussian,
    energy_score,
    pinball_loss,
    skill_score,
)


def test_crps_of_a_deterministic_ensemble_is_the_absolute_error() -> None:
    forecast = np.full((3, 8), 4.0)
    observation = np.array([4.0, 6.5, 1.0])
    scores = crps_ensemble(forecast, observation, fair=False)
    assert np.allclose(scores, np.array([0.0, 2.5, 3.0]))


def test_fair_crps_matches_the_two_member_closed_form() -> None:
    forecast = np.array([[1.0, 5.0]])
    observation = np.array([2.0])
    expected = (abs(1.0 - 2.0) + abs(5.0 - 2.0)) / 2 - (5.0 - 1.0) / 2
    assert crps_ensemble(forecast, observation)[0] == pytest.approx(expected)


def test_ensemble_crps_converges_to_the_gaussian_closed_form() -> None:
    generator = np.random.default_rng(20260824)
    members = generator.normal(0.0, 1.0, size=(1, 40000))
    observation = np.array([0.5])
    estimated = crps_ensemble(members, observation)[0]
    analytic = crps_gaussian(np.array([0.0]), np.array([1.0]), observation)[0]
    assert estimated == pytest.approx(analytic, abs=0.01)


def test_crps_prefers_the_correctly_centred_ensemble() -> None:
    """A proper score must not be improvable by lying about the mean."""

    generator = np.random.default_rng(7)
    observation = generator.normal(0.0, 1.0, size=600)
    honest = generator.normal(0.0, 1.0, size=(600, 40))
    biased = honest + 1.5
    assert np.mean(crps_ensemble(honest, observation)) < np.mean(
        crps_ensemble(biased, observation)
    )


def test_crps_prefers_honest_spread_over_overconfidence() -> None:
    generator = np.random.default_rng(11)
    observation = generator.normal(0.0, 1.0, size=600)
    honest = generator.normal(0.0, 1.0, size=(600, 40))
    overconfident = generator.normal(0.0, 0.1, size=(600, 40))
    assert np.mean(crps_ensemble(honest, observation)) < np.mean(
        crps_ensemble(overconfident, observation)
    )


@settings(max_examples=40, suppress_health_check=[HealthCheck.too_slow])
@given(
    values=st.lists(
        st.floats(min_value=-1e3, max_value=1e3, allow_nan=False, allow_infinity=False),
        min_size=2,
        max_size=25,
    ),
    observation=st.floats(
        min_value=-1e3, max_value=1e3, allow_nan=False, allow_infinity=False
    ),
)
def test_empirical_crps_is_never_negative(values: list[float], observation: float) -> None:
    forecast = np.array([values], dtype=float)
    score = crps_ensemble(forecast, np.array([observation]), fair=False)[0]
    assert score >= -1e-9


def test_energy_score_reduces_to_crps_in_one_dimension() -> None:
    generator = np.random.default_rng(3)
    forecast = generator.normal(size=(12, 16))
    observation = generator.normal(size=12)
    univariate = crps_ensemble(forecast, observation)
    multivariate = energy_score(forecast[:, :, None], observation[:, None])
    assert np.allclose(univariate, multivariate)


def test_energy_score_sees_correlation_that_per_zone_crps_misses() -> None:
    """Two zones that surge together must not be scored as independent."""

    generator = np.random.default_rng(5)
    observation = np.tile(np.array([[2.0, 2.0]]), (400, 1))
    common = generator.normal(size=(400, 60, 1))
    correlated = np.concatenate([common, common], axis=2) + 2.0
    independent = generator.normal(size=(400, 60, 2)) + 2.0
    correlated_score = float(np.mean(energy_score(correlated, observation)))
    independent_score = float(np.mean(energy_score(independent, observation)))
    assert correlated_score != pytest.approx(independent_score, rel=0.05)


def test_brier_decomposition_identity_holds_exactly() -> None:
    generator = np.random.default_rng(19)
    probability = generator.uniform(size=500)
    outcome = (generator.uniform(size=500) < probability).astype(float)
    decomposition = brier_decomposition(probability, outcome, bins=10)
    rebuilt = (
        decomposition.reliability
        - decomposition.resolution
        + decomposition.uncertainty
        + decomposition.residual
    )
    assert rebuilt == pytest.approx(decomposition.brier)


def test_brier_residual_vanishes_when_forecasts_sit_on_bin_centres() -> None:
    probability = np.repeat(np.array([0.05, 0.45, 0.95]), 200)
    generator = np.random.default_rng(23)
    outcome = (generator.uniform(size=probability.size) < probability).astype(float)
    decomposition = brier_decomposition(probability, outcome, bins=10)
    assert decomposition.residual == pytest.approx(0.0, abs=1e-12)


def test_a_reliable_forecast_has_small_reliability_and_positive_skill() -> None:
    generator = np.random.default_rng(29)
    probability = generator.uniform(size=8000)
    outcome = (generator.uniform(size=8000) < probability).astype(float)
    decomposition = brier_decomposition(probability, outcome, bins=10)
    assert decomposition.reliability < 0.005
    assert decomposition.skill_versus_climatology > 0.0


def test_perfect_forecast_scores_zero() -> None:
    outcome = np.array([1.0, 0.0, 1.0, 0.0])
    assert brier_score(outcome, outcome) == pytest.approx(0.0)


def test_pinball_loss_at_the_median_is_half_the_absolute_error() -> None:
    forecast = np.array([[3.0]])
    observation = np.array([5.0])
    levels = np.array([0.5])
    assert pinball_loss(forecast, observation, levels)[0, 0] == pytest.approx(1.0)


def test_pinball_loss_penalises_the_two_tails_asymmetrically() -> None:
    levels = np.array([0.9])
    under = pinball_loss(np.array([[0.0]]), np.array([1.0]), levels)[0, 0]
    over = pinball_loss(np.array([[1.0]]), np.array([0.0]), levels)[0, 0]
    assert under == pytest.approx(0.9)
    assert over == pytest.approx(0.1)


def test_skill_score_reports_loss_against_a_better_reference() -> None:
    assert skill_score(0.5, 1.0) == pytest.approx(0.5)
    assert skill_score(2.0, 1.0) == pytest.approx(-1.0)
    assert skill_score(1.0, 0.0) == 0.0


@pytest.mark.parametrize(
    ("forecast", "observation", "message"),
    [
        (np.array([[np.nan, 1.0]]), np.array([1.0]), "finite"),
        (np.array([[1.0, 2.0]]), np.array([1.0, 2.0]), "one entry per case"),
        (np.zeros((2, 2, 2)), np.array([1.0, 2.0]), "cases, members"),
    ],
)
def test_crps_rejects_malformed_input(
    forecast: np.ndarray, observation: np.ndarray, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        crps_ensemble(forecast, observation)


def test_fair_crps_requires_two_members() -> None:
    with pytest.raises(ValueError, match="at least two members"):
        crps_ensemble(np.array([[1.0]]), np.array([1.0]))


def test_probabilities_outside_the_unit_interval_are_rejected() -> None:
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        brier_score(np.array([1.5]), np.array([1.0]))


def test_non_binary_outcomes_are_rejected() -> None:
    with pytest.raises(ValueError, match="binary"):
        brier_score(np.array([0.5]), np.array([0.7]))
