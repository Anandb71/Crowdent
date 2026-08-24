"""Lead-time verification reports for recorded timelines and twin experiments.

This is the layer that answers the only question that matters before a
venue trusts a number on a screen: over a recorded timeline, was the
forecast better than persistence, and was its uncertainty honest?

The report is deliberately loud about under-dispersion. An overconfident
interval is worse than a wide one, because it invites a human to act on
precision the physics does not support.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from crowdent.verification.calibration import (
    IntervalCoverage,
    RankHistogram,
    SpreadSkill,
    interval_coverage,
    rank_histogram,
    spread_skill_ratio,
)
from crowdent.verification.scores import (
    BrierDecomposition,
    brier_decomposition,
    crps_ensemble,
    skill_score,
)

FloatArray = NDArray[np.float64]

#: Spread-skill below this is reported as overconfident.
UNDER_DISPERSION_RATIO = 0.85
#: Spread-skill above this is reported as over-dispersed.
OVER_DISPERSION_RATIO = 1.25
#: Coverage may miss its nominal level by this much before it is flagged.
COVERAGE_TOLERANCE = 0.05


@dataclass(frozen=True, slots=True)
class LeadTimeVerification:
    """Verification of one lead time across every case in a timeline."""

    lead_time_min: int
    cases: int
    members: int
    crps: float
    crps_baseline: float | None
    crps_skill: float | None
    spread_skill: SpreadSkill
    coverage: IntervalCoverage
    ranks: RankHistogram
    exceedance: BrierDecomposition | None
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "lead_time_min": self.lead_time_min,
            "cases": self.cases,
            "members": self.members,
            "crps": self.crps,
            "crps_baseline": self.crps_baseline,
            "crps_skill": self.crps_skill,
            "spread_skill_ratio": self.spread_skill.ratio,
            "mean_spread": self.spread_skill.mean_spread,
            "rmse": self.spread_skill.root_mean_square_error,
            "coverage_nominal": self.coverage.nominal,
            "coverage_attainable": self.coverage.attainable,
            "coverage_empirical": self.coverage.empirical,
            "coverage_mean_width": self.coverage.mean_width,
            "rank_flatness_chi_square": self.ranks.flatness_chi_square,
            "rank_degrees_of_freedom": self.ranks.degrees_of_freedom,
            "rank_reliability_index": self.ranks.reliability_index,
            "rank_counts": [int(value) for value in self.ranks.counts],
            "warnings": list(self.warnings),
        }
        if self.exceedance is not None:
            payload["exceedance"] = {
                "brier": self.exceedance.brier,
                "reliability": self.exceedance.reliability,
                "resolution": self.exceedance.resolution,
                "uncertainty": self.exceedance.uncertainty,
                "base_rate": self.exceedance.base_rate,
                "skill_versus_climatology": self.exceedance.skill_versus_climatology,
            }
        return payload


@dataclass(frozen=True, slots=True)
class VerificationReport:
    """Full verification across every lead time.

    ``calibrated`` is a screening result, not a certificate. It says the
    diagnostics found nothing alarming on this timeline. It does not
    authorize deployment, and no code path treats it as readiness.
    """

    leads: tuple[LeadTimeVerification, ...]
    threshold: float | None

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(warning for lead in self.leads for warning in lead.warnings)

    @property
    def calibrated(self) -> bool:
        return not self.warnings

    @property
    def mean_crps_skill(self) -> float | None:
        skills = [lead.crps_skill for lead in self.leads if lead.crps_skill is not None]
        if not skills:
            return None
        return float(np.mean(skills))

    def to_dict(self) -> dict[str, Any]:
        return {
            "research_only": True,
            "deployment_certified": False,
            "threshold": self.threshold,
            "calibrated": self.calibrated,
            "mean_crps_skill": self.mean_crps_skill,
            "warnings": list(self.warnings),
            "leads": [lead.to_dict() for lead in self.leads],
        }


def verify_ensemble_forecast(
    forecasts_by_lead: Mapping[int, NDArray[np.floating]],
    observations_by_lead: Mapping[int, NDArray[np.floating]],
    *,
    baseline_by_lead: Mapping[int, NDArray[np.floating]] | None = None,
    threshold: float | None = None,
    nominal_coverage: float = 0.9,
    seed: int = 0,
) -> VerificationReport:
    """Verify ensemble forecasts against observed outcomes, lead time by lead time.

    ``forecasts_by_lead`` maps a lead time in minutes to an array of shape
    ``(cases, members)``. ``observations_by_lead`` maps the same lead
    times to the verifying truth of shape ``(cases,)``. Supplying
    ``baseline_by_lead`` (typically persistence) turns the absolute CRPS
    into a skill score, which is the only form worth quoting: a small
    CRPS on a quiet timeline means nothing on its own.
    """

    if not forecasts_by_lead:
        raise ValueError("at least one lead time is required")
    if set(forecasts_by_lead) != set(observations_by_lead):
        raise ValueError("forecasts and observations must cover the same lead times")
    if baseline_by_lead is not None and set(baseline_by_lead) != set(forecasts_by_lead):
        raise ValueError("baseline must cover the same lead times")
    if threshold is not None and (not np.isfinite(threshold) or threshold < 0):
        raise ValueError("threshold must be finite and nonnegative")

    leads: list[LeadTimeVerification] = []
    for lead in sorted(forecasts_by_lead):
        if lead <= 0:
            raise ValueError("lead times must be positive minutes")
        forecast = np.asarray(forecasts_by_lead[lead], dtype=float)
        observation = np.asarray(observations_by_lead[lead], dtype=float)
        if forecast.ndim != 2:
            raise ValueError("each forecast must have shape (cases, members)")
        if forecast.shape[1] < 2:
            raise ValueError("verification requires at least two ensemble members")

        crps = float(np.mean(crps_ensemble(forecast, observation)))
        baseline_crps: float | None = None
        skill: float | None = None
        if baseline_by_lead is not None:
            baseline = np.asarray(baseline_by_lead[lead], dtype=float)
            if baseline.ndim == 1:
                baseline = baseline[:, None]
            baseline_crps = float(np.mean(crps_ensemble(baseline, observation, fair=False)))
            skill = skill_score(crps, baseline_crps)

        spread = spread_skill_ratio(forecast, observation)
        coverage = interval_coverage(forecast, observation, nominal=nominal_coverage)
        ranks = rank_histogram(forecast, observation, seed=seed)
        exceedance: BrierDecomposition | None = None
        if threshold is not None:
            probability = np.mean(forecast > threshold, axis=1)
            outcome = (observation > threshold).astype(float)
            exceedance = brier_decomposition(probability, outcome)

        leads.append(
            LeadTimeVerification(
                lead_time_min=int(lead),
                cases=forecast.shape[0],
                members=forecast.shape[1],
                crps=crps,
                crps_baseline=baseline_crps,
                crps_skill=skill,
                spread_skill=spread,
                coverage=coverage,
                ranks=ranks,
                exceedance=exceedance,
                warnings=_warnings_for(lead, spread, coverage, skill),
            )
        )
    return VerificationReport(leads=tuple(leads), threshold=threshold)


def _warnings_for(
    lead: int,
    spread: SpreadSkill,
    coverage: IntervalCoverage,
    skill: float | None,
) -> tuple[str, ...]:
    messages: list[str] = []
    if spread.ratio < UNDER_DISPERSION_RATIO:
        messages.append(
            f"lead {lead} min is under-dispersed "
            f"(spread-skill {spread.ratio:.2f}); intervals are overconfident"
        )
    elif spread.ratio > OVER_DISPERSION_RATIO:
        messages.append(
            f"lead {lead} min is over-dispersed "
            f"(spread-skill {spread.ratio:.2f}); intervals are uninformatively wide"
        )
    if coverage.deviation < -COVERAGE_TOLERANCE:
        messages.append(
            f"lead {lead} min covers {coverage.empirical:.0%} of outcomes against the "
            f"{coverage.attainable:.0%} this ensemble size can attain"
        )
    if skill is not None and skill <= 0.0:
        messages.append(
            f"lead {lead} min has no skill over the baseline (CRPS skill {skill:.2f})"
        )
    return tuple(messages)


def summarize_warnings(reports: Sequence[VerificationReport]) -> tuple[str, ...]:
    """Flatten warnings across several reports, preserving order and dropping repeats."""

    seen: dict[str, None] = {}
    for report in reports:
        for warning in report.warnings:
            seen.setdefault(warning, None)
    return tuple(seen)


__all__ = [
    "COVERAGE_TOLERANCE",
    "OVER_DISPERSION_RATIO",
    "UNDER_DISPERSION_RATIO",
    "LeadTimeVerification",
    "VerificationReport",
    "summarize_warnings",
    "verify_ensemble_forecast",
]
