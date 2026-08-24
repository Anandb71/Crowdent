"""Proper scoring rules for ensemble forecasts.

Every score here is *negatively oriented*: lower is better. Scores are
returned per case so callers can aggregate over zones, lead times, or
recorded timelines without re-deriving the arithmetic.

The continuous ranked probability score is computed from the ensemble
directly rather than from a fitted parametric distribution, because
Crowdent forecasts are not Gaussian near capacity limits.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.special import ndtr

FloatArray = NDArray[np.float64]

_SQRT_PI = float(np.sqrt(np.pi))


def crps_ensemble(
    forecasts: NDArray[np.floating],
    observations: NDArray[np.floating],
    *,
    fair: bool = True,
) -> FloatArray:
    """Per-case CRPS of an ensemble forecast, in the units of the state.

    ``forecasts`` has shape ``(cases, members)`` and ``observations`` has
    shape ``(cases,)``. The score uses the energy form
    ``E|X - y| - 0.5 * E|X - X'|`` where the spread term is estimated with
    ``1 / (m * (m - 1))`` when ``fair`` is true. The fair estimator is
    unbiased for the CRPS of the underlying predictive distribution, so
    ensembles of different sizes stay comparable. The biased estimator is
    the exact CRPS of the empirical distribution and is never negative.
    """

    forecast, observation = _aligned_ensemble(forecasts, observations)
    members = forecast.shape[1]
    if fair and members < 2:
        raise ValueError("the fair CRPS estimator requires at least two members")
    absolute_error = np.abs(forecast - observation[:, None]).mean(axis=1)
    # sum_{i<j} (x_(j) - x_(i)) via the sorted-order identity, which is
    # O(m log m) instead of the O(m^2) pairwise expansion.
    ordered = np.sort(forecast, axis=1)
    weights = 2.0 * np.arange(1, members + 1, dtype=float) - members - 1.0
    pairwise_gap = ordered @ weights
    denominator = float(members * (members - 1)) if fair else float(members * members)
    result: FloatArray = absolute_error - pairwise_gap / denominator
    return result


def crps_gaussian(
    mean: NDArray[np.floating],
    standard_deviation: NDArray[np.floating],
    observations: NDArray[np.floating],
) -> FloatArray:
    """Closed-form CRPS of a Gaussian predictive distribution.

    Kept as an analytic reference for checking the ensemble estimator and
    for cheap baselines. It is not used on the advisory path.
    """

    location = _finite(mean, "mean")
    scale = _finite(standard_deviation, "standard deviation")
    target = _finite(observations, "observations")
    if location.shape != scale.shape or location.shape != target.shape:
        raise ValueError("mean, standard deviation and observations must share a shape")
    if np.any(scale <= 0):
        raise ValueError("standard deviation must be positive")
    standardized = (target - location) / scale
    density = np.exp(-0.5 * standardized**2) / np.sqrt(2.0 * np.pi)
    cumulative = np.asarray(ndtr(standardized), dtype=float)
    result: FloatArray = scale * (
        standardized * (2.0 * cumulative - 1.0) + 2.0 * density - 1.0 / _SQRT_PI
    )
    return result


def energy_score(
    forecasts: NDArray[np.floating],
    observations: NDArray[np.floating],
    *,
    fair: bool = True,
) -> FloatArray:
    """Multivariate generalization of CRPS for joint zone forecasts.

    ``forecasts`` has shape ``(cases, members, dimensions)`` and
    ``observations`` has shape ``(cases, dimensions)``. Unlike a sum of
    per-zone CRPS values, the energy score is sensitive to the spatial
    correlation between zones, which is what route-aware advisories
    depend on.
    """

    forecast = _finite(forecasts, "forecasts")
    observation = _finite(observations, "observations")
    if forecast.ndim != 3:
        raise ValueError("forecasts must have shape (cases, members, dimensions)")
    if observation.ndim != 2:
        raise ValueError("observations must have shape (cases, dimensions)")
    if forecast.shape[0] != observation.shape[0] or forecast.shape[2] != observation.shape[1]:
        raise ValueError("forecast and observation shapes are inconsistent")
    members = forecast.shape[1]
    if members < 2:
        raise ValueError("the energy score requires at least two members")
    error_norms = np.linalg.norm(forecast - observation[:, None, :], axis=2).mean(axis=1)
    differences = forecast[:, :, None, :] - forecast[:, None, :, :]
    pairwise = np.linalg.norm(differences, axis=3).sum(axis=(1, 2))
    denominator = float(members * (members - 1)) if fair else float(members * members)
    result: FloatArray = error_norms - 0.5 * pairwise / denominator
    return result


def pinball_loss(
    quantile_forecasts: NDArray[np.floating],
    observations: NDArray[np.floating],
    quantile_levels: NDArray[np.floating],
) -> FloatArray:
    """Per-case, per-level quantile (check) loss.

    ``quantile_forecasts`` has shape ``(cases, levels)``. Averaging across
    levels approximates CRPS, which makes this the natural score for the
    published forecast quantiles rather than the full ensemble.
    """

    forecast = _finite(quantile_forecasts, "quantile forecasts")
    target = _finite(observations, "observations")
    levels = _finite(quantile_levels, "quantile levels")
    if forecast.ndim != 2:
        raise ValueError("quantile forecasts must have shape (cases, levels)")
    if target.ndim != 1 or target.shape[0] != forecast.shape[0]:
        raise ValueError("observations must have one entry per case")
    if levels.ndim != 1 or levels.shape[0] != forecast.shape[1]:
        raise ValueError("quantile levels must have one entry per forecast column")
    if np.any((levels <= 0) | (levels >= 1)):
        raise ValueError("quantile levels must lie strictly within (0, 1)")
    difference = target[:, None] - forecast
    result: FloatArray = np.maximum(levels * difference, (levels - 1.0) * difference)
    return result


def brier_score(
    probabilities: NDArray[np.floating],
    outcomes: NDArray[np.floating],
) -> float:
    """Mean squared error of probabilistic threshold-exceedance forecasts."""

    probability, outcome = _aligned_probabilities(probabilities, outcomes)
    return float(np.mean((probability - outcome) ** 2))


@dataclass(frozen=True, slots=True)
class BrierDecomposition:
    """Murphy decomposition of the Brier score.

    ``reliability`` is the calibration penalty and is lower-is-better.
    ``resolution`` rewards separating high-risk from low-risk cases and is
    higher-is-better. ``uncertainty`` is the irreducible base-rate term.
    ``residual`` absorbs within-bin forecast variance so that
    ``brier == reliability - resolution + uncertainty + residual`` holds
    exactly for any binning.
    """

    brier: float
    reliability: float
    resolution: float
    uncertainty: float
    residual: float
    base_rate: float

    @property
    def skill_versus_climatology(self) -> float:
        """Brier skill score against the constant base-rate forecast."""

        if self.uncertainty <= 0.0:
            return 0.0
        return 1.0 - self.brier / self.uncertainty


def brier_decomposition(
    probabilities: NDArray[np.floating],
    outcomes: NDArray[np.floating],
    *,
    bins: int = 10,
) -> BrierDecomposition:
    """Decompose the Brier score into reliability, resolution and uncertainty."""

    probability, outcome = _aligned_probabilities(probabilities, outcomes)
    if bins < 1:
        raise ValueError("bins must be positive")
    total = probability.shape[0]
    edges = np.linspace(0.0, 1.0, bins + 1)
    assignment = np.clip(np.digitize(probability, edges[1:-1], right=False), 0, bins - 1)
    base_rate = float(outcome.mean())
    reliability = 0.0
    resolution = 0.0
    for index in range(bins):
        selected = assignment == index
        count = int(selected.sum())
        if count == 0:
            continue
        mean_probability = float(probability[selected].mean())
        mean_outcome = float(outcome[selected].mean())
        reliability += count * (mean_probability - mean_outcome) ** 2
        resolution += count * (mean_outcome - base_rate) ** 2
    reliability /= total
    resolution /= total
    uncertainty = base_rate * (1.0 - base_rate)
    score = brier_score(probability, outcome)
    return BrierDecomposition(
        brier=score,
        reliability=reliability,
        resolution=resolution,
        uncertainty=uncertainty,
        residual=score - (reliability - resolution + uncertainty),
        base_rate=base_rate,
    )


def skill_score(score: float, reference: float) -> float:
    """Fraction of the reference score removed. One is perfect, zero is no gain.

    A negative value means the forecast is worse than the reference, which
    is the result that matters most when comparing against persistence.
    """

    if not np.isfinite(score) or not np.isfinite(reference):
        raise ValueError("scores must be finite")
    if reference == 0.0:
        return 0.0
    return float(1.0 - score / reference)


def _aligned_ensemble(
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
    if forecast.shape[1] < 1:
        raise ValueError("each case requires at least one ensemble member")
    return forecast, observation


def _aligned_probabilities(
    probabilities: NDArray[np.floating],
    outcomes: NDArray[np.floating],
) -> tuple[FloatArray, FloatArray]:
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
    return probability, outcome


def _finite(value: NDArray[np.floating], name: str) -> FloatArray:
    array = np.asarray(value, dtype=float)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be finite")
    return array


__all__ = [
    "BrierDecomposition",
    "brier_decomposition",
    "brier_score",
    "crps_ensemble",
    "crps_gaussian",
    "energy_score",
    "pinball_loss",
    "skill_score",
]
