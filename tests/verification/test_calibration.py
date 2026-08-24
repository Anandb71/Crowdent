"""Calibration diagnostics must detect overconfidence, which is the unsafe direction."""

from __future__ import annotations

import numpy as np
import pytest

from crowdent.verification import (
    interval_coverage,
    rank_histogram,
    reliability_curve,
    spread_skill_ratio,
)

CASES = 6000
MEMBERS = 20


def _calibrated(seed: int = 101) -> tuple[np.ndarray, np.ndarray]:
    """Observation and ensemble drawn from the same law, so ranks are exchangeable."""

    generator = np.random.default_rng(seed)
    observation = generator.normal(size=CASES)
    forecast = generator.normal(size=(CASES, MEMBERS))
    return forecast, observation


def _under_dispersed(seed: int = 202) -> tuple[np.ndarray, np.ndarray]:
    generator = np.random.default_rng(seed)
    observation = generator.normal(size=CASES)
    forecast = generator.normal(scale=0.2, size=(CASES, MEMBERS))
    return forecast, observation


def test_rank_histogram_is_flat_for_a_calibrated_ensemble() -> None:
    forecast, observation = _calibrated()
    histogram = rank_histogram(forecast, observation, seed=1)
    assert histogram.counts.shape == (MEMBERS + 1,)
    assert int(histogram.counts.sum()) == CASES
    assert histogram.degrees_of_freedom == MEMBERS
    # chi-square on 20 dof; 45 is far into the tail but catches gross failure.
    assert histogram.flatness_chi_square < 45.0
    assert histogram.reliability_index < 0.1


def test_rank_histogram_is_u_shaped_when_the_ensemble_is_overconfident() -> None:
    forecast, observation = _under_dispersed()
    histogram = rank_histogram(forecast, observation, seed=1)
    extremes = int(histogram.counts[0] + histogram.counts[-1])
    assert extremes > CASES // 2
    assert histogram.flatness_chi_square > 100.0


def test_rank_histogram_randomises_ties_instead_of_spiking_at_zero() -> None:
    """A zone pinned at zero density must not fake perfect calibration."""

    forecast = np.zeros((2000, 8))
    observation = np.zeros(2000)
    histogram = rank_histogram(forecast, observation, seed=4)
    assert int(histogram.counts.sum()) == 2000
    assert np.count_nonzero(histogram.counts) == 9
    assert histogram.flatness_chi_square < 30.0


def test_spread_skill_is_near_one_when_the_ensemble_is_honest() -> None:
    forecast, observation = _calibrated()
    spread = spread_skill_ratio(forecast, observation)
    assert spread.ratio == pytest.approx(1.0, abs=0.05)
    assert spread.cases == CASES


def test_spread_skill_falls_below_one_when_the_ensemble_is_overconfident() -> None:
    forecast, observation = _under_dispersed()
    assert spread_skill_ratio(forecast, observation).ratio < 0.5


def test_interval_coverage_tracks_its_nominal_level() -> None:
    generator = np.random.default_rng(303)
    observation = generator.normal(size=CASES)
    forecast = generator.normal(size=(CASES, 200))
    coverage = interval_coverage(forecast, observation, nominal=0.9)
    assert coverage.empirical == pytest.approx(0.9, abs=0.03)
    assert coverage.mean_width > 0.0


def test_small_ensembles_report_the_coverage_they_can_actually_attain() -> None:
    """A 12-member ensemble cannot offer 90 percent, and must say so."""

    forecast, observation = _calibrated(seed=13)
    coverage = interval_coverage(forecast[:, :12], observation, nominal=0.9)
    assert coverage.attainable == pytest.approx(11.0 / 13.0)
    assert coverage.attainable < coverage.nominal
    assert coverage.empirical == pytest.approx(coverage.attainable, abs=0.03)
    assert abs(coverage.deviation) < 0.03


def test_attainable_coverage_tightens_as_the_ensemble_grows() -> None:
    forecast, observation = _calibrated(seed=14)
    small = interval_coverage(forecast[:, :12], observation, nominal=0.9)
    large = interval_coverage(forecast, observation, nominal=0.9)
    assert abs(large.attainable - 0.9) < abs(small.attainable - 0.9)
    assert large.members_dropped_per_tail >= small.members_dropped_per_tail


def test_interval_coverage_collapses_for_an_overconfident_ensemble() -> None:
    forecast, observation = _under_dispersed()
    coverage = interval_coverage(forecast, observation, nominal=0.9)
    assert coverage.empirical < 0.5
    assert coverage.deviation < -0.4


def test_reliability_curve_follows_the_diagonal_for_reliable_forecasts() -> None:
    generator = np.random.default_rng(404)
    probability = generator.uniform(size=20000)
    outcome = (generator.uniform(size=20000) < probability).astype(float)
    curve = reliability_curve(probability, outcome, bins=10)
    populated = curve.populated
    assert bool(populated.all())
    deviation = np.abs(
        curve.observed_frequency[populated] - curve.mean_probability[populated]
    )
    assert float(deviation.max()) < 0.05


def test_reliability_curve_exposes_a_systematically_over_warning_forecast() -> None:
    probability = np.full(4000, 0.8)
    outcome = np.zeros(4000)
    outcome[:800] = 1.0
    curve = reliability_curve(probability, outcome, bins=10)
    populated = curve.populated
    assert int(populated.sum()) == 1
    assert float(curve.observed_frequency[populated][0]) == pytest.approx(0.2)
    assert float(curve.mean_probability[populated][0]) == pytest.approx(0.8)


def test_empty_bins_are_reported_rather_than_silently_filled() -> None:
    curve = reliability_curve(np.array([0.05, 0.05]), np.array([0.0, 1.0]), bins=10)
    assert int(curve.counts[0]) == 2
    assert bool(np.isnan(curve.observed_frequency[5]))
    assert int(curve.counts[5]) == 0


@pytest.mark.parametrize("nominal", [0.0, 1.0, -0.2, 1.5])
def test_interval_coverage_rejects_impossible_nominal_levels(nominal: float) -> None:
    forecast, observation = _calibrated(seed=9)
    with pytest.raises(ValueError, match="strictly within"):
        interval_coverage(forecast[:10], observation[:10], nominal=nominal)


def test_spread_skill_requires_a_real_ensemble() -> None:
    with pytest.raises(ValueError, match="at least two members"):
        spread_skill_ratio(np.array([[1.0]]), np.array([1.0]))


def test_diagnostics_reject_non_finite_input() -> None:
    with pytest.raises(ValueError, match="finite"):
        rank_histogram(np.array([[1.0, np.inf]]), np.array([1.0]))
