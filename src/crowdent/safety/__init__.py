"""Fail-degraded readiness and advisory-only recommendation policies."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from crowdent.contracts import QualityFlag, ReadinessState


@dataclass(frozen=True, slots=True)
class SafetySignals:
    now: datetime
    stale_sources: tuple[str, ...] = ()
    conflicting_sources: tuple[str, ...] = ()
    missing_sources: tuple[str, ...] = ()
    calibration_valid: bool = True
    in_domain: bool = True
    ensemble_ok: bool = True
    numerical_ok: bool = True
    clock_ok: bool = True

    def __post_init__(self) -> None:
        if self.now.tzinfo is None or self.now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ReadinessAssessment:
    state: ReadinessState
    quality_flags: tuple[QualityFlag, ...]
    reasons: tuple[str, ...]
    countdown_seconds: int | None = None
    advice: tuple[str, ...] = ()
    research_only: bool = True


class ReadinessEvaluator:
    """Converts runtime health into a conservative readiness state."""

    def evaluate(self, signals: SafetySignals) -> ReadinessAssessment:
        hard_flags: list[QualityFlag] = []
        hard_reasons: list[str] = []
        if signals.missing_sources:
            hard_flags.append(QualityFlag.MISSING_INPUT)
            hard_reasons.append(f"missing sources: {', '.join(signals.missing_sources)}")
        if not signals.calibration_valid:
            hard_flags.append(QualityFlag.INVALID_CALIBRATION)
            hard_reasons.append("calibration is invalid or expired")
        if not signals.in_domain:
            hard_flags.append(QualityFlag.OUT_OF_DOMAIN)
            hard_reasons.append("input is outside the validated operating domain")
        if not signals.ensemble_ok:
            hard_flags.append(QualityFlag.ENSEMBLE_FAILURE)
            hard_reasons.append("ensemble diagnostics failed")
        if not signals.numerical_ok:
            hard_flags.append(QualityFlag.NUMERICAL_FAILURE)
            hard_reasons.append("numerical stability or conservation check failed")
        if not signals.clock_ok:
            hard_flags.append(QualityFlag.CLOCK_ERROR)
            hard_reasons.append("clock health check failed")
        if hard_flags:
            return ReadinessAssessment(
                state=ReadinessState.UNKNOWN,
                quality_flags=tuple(hard_flags),
                reasons=tuple(hard_reasons),
            )

        degraded_flags: list[QualityFlag] = []
        degraded_reasons: list[str] = []
        if signals.stale_sources:
            degraded_flags.append(QualityFlag.STALE_INPUT)
            degraded_reasons.append(f"stale sources: {', '.join(signals.stale_sources)}")
        if signals.conflicting_sources:
            degraded_flags.append(QualityFlag.CONFLICTING_INPUT)
            degraded_reasons.append(
                f"conflicting sources: {', '.join(signals.conflicting_sources)}"
            )
        if degraded_flags:
            return ReadinessAssessment(
                state=ReadinessState.DEGRADED,
                quality_flags=tuple(degraded_flags),
                reasons=tuple(degraded_reasons),
            )
        return ReadinessAssessment(
            state=ReadinessState.READY,
            quality_flags=(),
            reasons=("all configured research readiness checks passed",),
        )


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    permitted: bool
    recommendations: tuple[str, ...] = ()
    countdown_seconds: int | None = None
    reason_codes: tuple[str, ...] = ()
    research_only: bool = True
    hardware_actuation_available: bool = False


@dataclass(frozen=True, slots=True)
class RecommendationPolicy:
    allowed_actions: frozenset[str]
    prohibited_action_tokens: frozenset[str] = field(
        default_factory=lambda: frozenset({"ACTUATE", "AUTOMATIC", "EVACUATE_NOW"})
    )

    def evaluate(
        self,
        *,
        action: str,
        assessment: ReadinessAssessment,
        parameters: Mapping[str, object],
    ) -> PolicyDecision:
        del parameters  # Site constraints are evaluated before reaching this allowlist.
        if assessment.state is not ReadinessState.READY:
            return PolicyDecision(
                permitted=False,
                reason_codes=("READINESS_SUPPRESSED", *assessment.reasons),
            )
        normalized = action.strip().upper()
        if any(token in normalized for token in self.prohibited_action_tokens):
            return PolicyDecision(
                permitted=False,
                reason_codes=("ACTUATION_OR_UNSAFE_AUTOMATION_FORBIDDEN",),
            )
        if normalized not in self.allowed_actions:
            return PolicyDecision(permitted=False, reason_codes=("ACTION_NOT_ALLOWLISTED",))
        return PolicyDecision(
            permitted=True,
            recommendations=(normalized,),
            reason_codes=("RESEARCH_ADVISORY_ONLY",),
        )


__all__ = [
    "PolicyDecision",
    "ReadinessAssessment",
    "ReadinessEvaluator",
    "RecommendationPolicy",
    "SafetySignals",
]
