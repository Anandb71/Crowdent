from datetime import UTC, datetime

from crowdent.contracts import QualityFlag, ReadinessState
from crowdent.safety import (
    ReadinessEvaluator,
    RecommendationPolicy,
    SafetySignals,
)

NOW = datetime(2026, 8, 24, 10, 0, tzinfo=UTC)


def test_stale_or_conflicting_inputs_suppress_countdown_and_advice() -> None:
    evaluator = ReadinessEvaluator()

    stale = evaluator.evaluate(
        SafetySignals(now=NOW, stale_sources=("camera-north",)),
    )
    conflicting = evaluator.evaluate(
        SafetySignals(now=NOW, conflicting_sources=("camera-a", "camera-b")),
    )

    assert stale.state is ReadinessState.DEGRADED
    assert stale.quality_flags == (QualityFlag.STALE_INPUT,)
    assert stale.countdown_seconds is None
    assert stale.advice == ()
    assert conflicting.state is ReadinessState.DEGRADED
    assert conflicting.countdown_seconds is None
    assert conflicting.advice == ()


def test_hard_failures_produce_unknown_and_no_recommendation() -> None:
    evaluator = ReadinessEvaluator()
    assessment = evaluator.evaluate(
        SafetySignals(
            now=NOW,
            missing_sources=("pressure-grid",),
            calibration_valid=False,
            ensemble_ok=False,
            numerical_ok=False,
        ),
    )
    policy = RecommendationPolicy(allowed_actions=frozenset({"PAUSE_INFLOW"}))

    decision = policy.evaluate(
        action="PAUSE_INFLOW",
        assessment=assessment,
        parameters={"gate": "north"},
    )

    assert assessment.state is ReadinessState.UNKNOWN
    assert decision.permitted is False
    assert decision.recommendations == ()
    assert decision.countdown_seconds is None
    assert decision.research_only is True


def test_ready_policy_only_returns_allowlisted_recommendations() -> None:
    assessment = ReadinessEvaluator().evaluate(SafetySignals(now=NOW))
    policy = RecommendationPolicy(allowed_actions=frozenset({"PAUSE_INFLOW"}))

    allowed = policy.evaluate(
        action="PAUSE_INFLOW",
        assessment=assessment,
        parameters={"gate": "north"},
    )
    blocked = policy.evaluate(
        action="ACTUATE_GATE",
        assessment=assessment,
        parameters={"gate": "north"},
    )

    assert assessment.state is ReadinessState.READY
    assert allowed.permitted is True
    assert allowed.recommendations == ("PAUSE_INFLOW",)
    assert blocked.permitted is False
    assert blocked.recommendations == ()
