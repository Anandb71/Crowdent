"""Public forecast-verification API for Crowdent.

Scoring rules and calibration diagnostics for ensemble forecasts. This
package is verification only: it never influences readiness, advice, or
the countdown, and it holds no hardware interface.
"""

from crowdent.verification.calibration import (
    IntervalCoverage,
    RankHistogram,
    ReliabilityCurve,
    SpreadSkill,
    interval_coverage,
    rank_histogram,
    reliability_curve,
    spread_skill_ratio,
)
from crowdent.verification.report import (
    COVERAGE_TOLERANCE,
    OVER_DISPERSION_RATIO,
    UNDER_DISPERSION_RATIO,
    LeadTimeVerification,
    VerificationReport,
    summarize_warnings,
    verify_ensemble_forecast,
)
from crowdent.verification.scores import (
    BrierDecomposition,
    brier_decomposition,
    brier_score,
    crps_ensemble,
    crps_gaussian,
    energy_score,
    pinball_loss,
    skill_score,
)

__all__ = [
    "COVERAGE_TOLERANCE",
    "OVER_DISPERSION_RATIO",
    "UNDER_DISPERSION_RATIO",
    "BrierDecomposition",
    "IntervalCoverage",
    "LeadTimeVerification",
    "RankHistogram",
    "ReliabilityCurve",
    "SpreadSkill",
    "VerificationReport",
    "brier_decomposition",
    "brier_score",
    "crps_ensemble",
    "crps_gaussian",
    "energy_score",
    "interval_coverage",
    "pinball_loss",
    "rank_histogram",
    "reliability_curve",
    "skill_score",
    "spread_skill_ratio",
    "summarize_warnings",
    "verify_ensemble_forecast",
]
