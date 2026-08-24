"""Calibration diagnostics for ensemble forecasts.

A proper score says how good a forecast is. These diagnostics say
*whether the stated uncertainty is honest*, which is the claim Crowdent
puts in front of a human decision maker. An advisory that reports a
90 percent interval must contain the truth about 90 percent of the time,
or the interval is decoration.

Nothing in this module feeds the advisory path. It is verification, run
against recorded timelines and twin experiments.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]


@dataclass(frozen=True, slots=True)
class RankHistogram:
    """Talagrand rank histogram of observations within their ensemble.

    Under a calibrated ensemble every rank is equally likely, so the
    counts are flat. A U shape means the ensemble is under-dispersed:
    the truth keeps falling outside the ensemble and the forecast is
    overconfident. A dome means over-dispersed. A slope means bias.
    """

    counts: IntArray
    members: int
    cases: int

    @property
    def frequencies(self) -> FloatArray:
        result: FloatArray = self.counts.astype(float) / float(self.cases)
        return result

    @property
    def expected_frequency(self) -> float:
        return 1.0 / float(self.members + 1)

    @property
    def flatness_chi_square(self) -> float:
        """Chi-square statistic against a flat histogram, with ``members`` dof."""

        expected = float(self.cases) * self.expected_frequency
        if expected <= 0.0:
            return 0.0
        return float(np.sum((self.counts.astype(float) - expected) ** 2) / expected)

    @property
    def degrees_of_freedom(self) -> int:
        return self.members

    @property
    def reliability_index(self) -> float:
        """Sum of absolute deviations from flatness. Zero is perfectly flat."""

        return float(np.sum(np.abs(self.frequencies - self.expected_frequency)))


def rank_histogram(
    forecasts: NDArray[np.floating],
    observations: NDArray[np.floating],
    *,
    seed: int = 0,
) -> RankHistogram:
    """Rank each observation among its ensemble members.

    Ties are broken with a seeded generator so that discrete or clipped
    states (a zone pinned at zero density, for example) do not pile up an
    artificial spike at rank zero. The seed keeps the diagnostic
    reproducible, which the replay mode requires.
    """

    forecast, observation = _aligned(forecasts, observations)
    members = forecast.shape[1]
    generator = np.random.default_rng(seed)
    below = np.sum(forecast < observation[:, None], axis=1)
    tied = np.sum(forecast == observation[:, None], axis=1)
    offset = generator.integers(0, tied + 1)
    ranks = (below + offset).astype(np.int64)
    counts = np.bincount(ranks, minlength=members + 1).astype(np.int64)
    return RankHistogram(counts=counts, members=members, cases=forecast.shape[0])


@dataclass(frozen=True, slots=True)
class ReliabilityCurve:
    """Observed frequency against forecast probability, bin by bin.

    Perfect reliability is the diagonal. Points below the diagonal mean
    the forecast over-warns; points above mean it under-warns. Bins with
    a small ``counts`` entry carry little evidence and should not be read
    as calibration failures.
    """

    bin_lower: FloatArray
    bin_upper: FloatArray
    mean_probability: FloatArray
    observed_frequency: FloatArray
    counts: IntArray

    @property
    def populated(self) -> NDArray[np.bool_]:
        result: NDArray[np.bool_] = self.counts > 0
        return result


def reliability_curve(
    probabilities: NDArray[np.floating],
    outcomes: NDArray[np.floating],
    *,
    bins: int = 10,
) -> ReliabilityCurve:
    """Bin probabilistic forecasts and compare against observed frequency."""

    probability = _finite(probabilities, "probabilities").ravel()
    outcome = _finite(outcomes, "outcomes").ravel()
    if probability.shape != outcome.shape:
        raise ValueError("probabilities and outcomes must share a shape")
    if probability.size == 0:
        raise ValueError("at least one forecast is required")
    if np.any((probability < 0.0) | (probability > 1.0)):
        raise ValueError("probabilities must lie within [0, 1]")
    if np.any((outcome != 0.0) & (outcome != 1.0)):
        raise ValueError("outcomes must be binary")
    if bins < 1:
        raise ValueError("bins must be positive")
    edges = np.linspace(0.0, 1.0, bins + 1)
    assignment = np.clip(np.digitize(probability, edges[1:-1], right=False), 0, bins - 1)
    mean_probability = np.full(bins, np.nan)
    observed_frequency = np.full(bins, np.nan)
    counts = np.zeros(bins, dtype=np.int64)
    for index in range(bins):
        selected = assignment == index
        count = int(selected.sum())
        counts[index] = count
        if count == 0:
            continue
        mean_probability[index] = float(probability[selected].mean())
        observed_frequency[index] = float(outcome[selected].mean())
    return ReliabilityCurve(
        bin_lower=edges[:-1],
        bin_upper=edges[1:],
        mean_probability=mean_probability,
        observed_frequency=observed_frequency,
        counts=counts,
    )


@dataclass(frozen=True, slots=True)
class SpreadSkill:
    """Ensemble spread against the error of the ensemble mean.

    For a calibrated ensemble the ratio is close to one. Below one the
    ensemble is overconfident, which is the dangerous direction for a
    crowd advisory: the interval looks tighter than the physics warrants.
    """

    mean_spread: float
    root_mean_square_error: float
    ratio: float
    cases: int


def spread_skill_ratio(
    forecasts: NDArray[np.floating],
    observations: NDArray[np.floating],
) -> SpreadSkill:
    """Compare average ensemble spread against ensemble-mean RMSE.

    The spread carries the ``sqrt((m + 1) / m)`` small-ensemble
    correction, so a finite ensemble drawn from the correct distribution
    gives a ratio near one instead of a systematic underestimate.
    """

    forecast, observation = _aligned(forecasts, observations)
    members = forecast.shape[1]
    if members < 2:
        raise ValueError("spread-skill requires at least two members")
    variance = forecast.var(axis=1, ddof=1)
    correction = float(np.sqrt((members + 1.0) / members))
    mean_spread = float(np.sqrt(variance.mean())) * correction
    error = forecast.mean(axis=1) - observation
    root_mean_square_error = float(np.sqrt(np.mean(error**2)))
    ratio = mean_spread / root_mean_square_error if root_mean_square_error > 0.0 else 0.0
    return SpreadSkill(
        mean_spread=mean_spread,
        root_mean_square_error=root_mean_square_error,
        ratio=ratio,
        cases=forecast.shape[0],
    )


@dataclass(frozen=True, slots=True)
class IntervalCoverage:
    """Empirical coverage of a central prediction interval built from order statistics.

    ``attainable`` is the coverage a calibrated ensemble of this size can
    actually deliver, which is not the same as ``nominal``. Dropping ``k``
    members from each tail of ``m`` exchangeable members gives exactly
    ``(m - 2k - 1) / (m + 1)`` coverage, so a 40-member ensemble asked for
    90 percent can only offer 90.2 percent, and a 12-member ensemble
    cannot get close at all. Judging ``empirical`` against ``nominal``
    would condemn a perfectly honest small ensemble, so ``deviation``
    compares against ``attainable`` instead.
    """

    nominal: float
    attainable: float
    empirical: float
    mean_width: float
    members_dropped_per_tail: int
    cases: int

    @property
    def deviation(self) -> float:
        """Signed miss against attainable coverage. Negative means too narrow."""

        return self.empirical - self.attainable


def interval_coverage(
    forecasts: NDArray[np.floating],
    observations: NDArray[np.floating],
    *,
    nominal: float = 0.9,
) -> IntervalCoverage:
    """Check how often the central interval actually contains the truth.

    The interval is a pair of order statistics rather than an interpolated
    quantile, because only order statistics have an exact coverage
    identity for a finite ensemble. ``mean_width`` is the sharpness of
    that interval: coverage alone is trivial to achieve by widening, so
    the two are always reported together.
    """

    forecast, observation = _aligned(forecasts, observations)
    if not 0.0 < nominal < 1.0:
        raise ValueError("nominal coverage must lie strictly within (0, 1)")
    members = forecast.shape[1]
    if members < 2:
        raise ValueError("interval coverage requires at least two members")
    dropped = round((members - 1 - nominal * (members + 1)) / 2.0)
    dropped = max(0, min(dropped, (members - 1) // 2))
    ordered = np.sort(forecast, axis=1)
    lower = ordered[:, dropped]
    upper = ordered[:, members - 1 - dropped]
    contained = (observation >= lower) & (observation <= upper)
    return IntervalCoverage(
        nominal=nominal,
        attainable=float(members - 2 * dropped - 1) / float(members + 1),
        empirical=float(contained.mean()),
        mean_width=float(np.mean(upper - lower)),
        members_dropped_per_tail=dropped,
        cases=forecast.shape[0],
    )


def _aligned(
    forecasts: NDArray[np.floating],
    observations: NDArray[np.floating],
) -> tuple[FloatArray, FloatArray]:
    forecast = _finite(forecasts, "forecasts")
    observation = _finite(observations, "observations")
    if forecast.ndim == 1:
        forecast = forecast[None, :]
    if observation.ndim == 0:
        observation = observation[None]
    if forecast.ndim != 2:
        raise ValueError("forecasts must have shape (cases, members)")
    if observation.ndim != 1 or observation.shape[0] != forecast.shape[0]:
        raise ValueError("observations must have one entry per case")
    if forecast.shape[0] == 0:
        raise ValueError("at least one case is required")
    return forecast, observation


def _finite(value: NDArray[np.floating], name: str) -> FloatArray:
    array = np.asarray(value, dtype=float)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be finite")
    return array


__all__ = [
    "IntervalCoverage",
    "RankHistogram",
    "ReliabilityCurve",
    "SpreadSkill",
    "interval_coverage",
    "rank_histogram",
    "reliability_curve",
    "spread_skill_ratio",
]
