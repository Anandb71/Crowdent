"""The report must stay loud about overconfidence and silent about readiness."""

from __future__ import annotations

import json

import numpy as np
import pytest

from crowdent.verification import (
    VerificationReport,
    summarize_warnings,
    verify_ensemble_forecast,
)

LEADS = (5, 15, 30)
CASES = 2000
MEMBERS = 40


def _timeline(
    scale: float,
    *,
    seed: int = 77,
    drift: float = 0.0,
) -> tuple[dict[int, np.ndarray], dict[int, np.ndarray], dict[int, np.ndarray]]:
    generator = np.random.default_rng(seed)
    forecasts: dict[int, np.ndarray] = {}
    observations: dict[int, np.ndarray] = {}
    baselines: dict[int, np.ndarray] = {}
    for lead in LEADS:
        truth = generator.normal(2.0, 1.0, size=CASES)
        forecasts[lead] = (
            truth[:, None] + generator.normal(drift, scale, size=(CASES, MEMBERS))
        )
        observations[lead] = truth + generator.normal(0.0, scale, size=CASES)
        baselines[lead] = truth + generator.normal(0.0, scale * 4.0, size=CASES)
    return forecasts, observations, baselines


def test_an_honest_ensemble_produces_no_warnings() -> None:
    forecasts, observations, _ = _timeline(scale=0.5)
    report = verify_ensemble_forecast(forecasts, observations)
    assert report.warnings == ()
    assert report.calibrated is True
    assert len(report.leads) == len(LEADS)
    assert [lead.lead_time_min for lead in report.leads] == sorted(LEADS)


def test_an_overconfident_ensemble_is_flagged_at_every_lead() -> None:
    generator = np.random.default_rng(5)
    forecasts = {lead: generator.normal(0.0, 0.05, size=(CASES, MEMBERS)) for lead in LEADS}
    observations = {lead: generator.normal(0.0, 1.0, size=CASES) for lead in LEADS}
    report = verify_ensemble_forecast(forecasts, observations)
    assert report.calibrated is False
    assert len(report.warnings) >= len(LEADS)
    assert any("under-dispersed" in warning for warning in report.warnings)
    assert any("overconfident" in warning for warning in report.warnings)


def test_wildly_wide_intervals_are_flagged_too() -> None:
    generator = np.random.default_rng(6)
    truth = generator.normal(0.0, 1.0, size=CASES)
    forecasts = {5: truth[:, None] + generator.normal(0.0, 8.0, size=(CASES, MEMBERS))}
    observations = {5: truth}
    report = verify_ensemble_forecast(forecasts, observations)
    assert any("over-dispersed" in warning for warning in report.warnings)


def test_skill_is_measured_against_the_supplied_baseline() -> None:
    forecasts, observations, baselines = _timeline(scale=0.5)
    report = verify_ensemble_forecast(
        forecasts, observations, baseline_by_lead=baselines
    )
    for lead in report.leads:
        assert lead.crps_baseline is not None
        assert lead.crps_skill is not None
        assert lead.crps < lead.crps_baseline
        assert lead.crps_skill > 0.0
    mean_skill = report.mean_crps_skill
    assert mean_skill is not None and mean_skill > 0.0


def test_a_forecast_no_better_than_its_baseline_is_called_out() -> None:
    generator = np.random.default_rng(8)
    truth = generator.normal(size=CASES)
    forecasts = {10: truth[:, None] + generator.normal(0.0, 1.0, size=(CASES, MEMBERS))}
    observations = {10: truth}
    baselines = {10: truth}  # a perfect baseline cannot be beaten
    report = verify_ensemble_forecast(
        forecasts, observations, baseline_by_lead=baselines
    )
    assert any("no skill over the baseline" in warning for warning in report.warnings)


def test_threshold_exceedance_is_scored_when_a_threshold_is_given() -> None:
    forecasts, observations, _ = _timeline(scale=0.5)
    report = verify_ensemble_forecast(forecasts, observations, threshold=2.0)
    assert report.threshold == 2.0
    for lead in report.leads:
        assert lead.exceedance is not None
        assert 0.0 <= lead.exceedance.brier <= 1.0
        assert lead.exceedance.skill_versus_climatology > 0.0


def test_no_threshold_means_no_exceedance_section() -> None:
    forecasts, observations, _ = _timeline(scale=0.5)
    report = verify_ensemble_forecast(forecasts, observations)
    assert all(lead.exceedance is None for lead in report.leads)
    assert "exceedance" not in report.to_dict()["leads"][0]


def test_report_serializes_to_json_and_never_claims_certification() -> None:
    forecasts, observations, baselines = _timeline(scale=0.5)
    report = verify_ensemble_forecast(
        forecasts, observations, baseline_by_lead=baselines, threshold=2.0
    )
    payload = json.loads(json.dumps(report.to_dict()))
    assert payload["research_only"] is True
    assert payload["deployment_certified"] is False
    assert len(payload["leads"]) == len(LEADS)
    assert payload["leads"][0]["rank_counts"]
    assert sum(payload["leads"][0]["rank_counts"]) == CASES


def test_calibrated_is_a_screening_result_not_a_readiness_signal() -> None:
    """Nothing in the verification package may be mistaken for readiness."""

    forecasts, observations, _ = _timeline(scale=0.5)
    report = verify_ensemble_forecast(forecasts, observations)
    payload = report.to_dict()
    assert "readiness" not in payload
    assert "countdown_seconds" not in payload
    assert "advice" not in payload


def test_summarize_warnings_deduplicates_across_reports() -> None:
    generator = np.random.default_rng(12)
    forecasts = {5: generator.normal(0.0, 0.05, size=(CASES, MEMBERS))}
    observations = {5: generator.normal(0.0, 1.0, size=CASES)}
    report = verify_ensemble_forecast(forecasts, observations)
    combined = summarize_warnings([report, report])
    assert combined == report.warnings
    assert len(set(combined)) == len(combined)


def test_empty_reports_summarize_to_nothing() -> None:
    assert summarize_warnings([]) == ()
    assert VerificationReport(leads=(), threshold=None).calibrated is True
    assert VerificationReport(leads=(), threshold=None).mean_crps_skill is None


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"forecasts_by_lead": {}, "observations_by_lead": {}}, "at least one lead"),
        (
            {
                "forecasts_by_lead": {5: np.zeros((4, 3))},
                "observations_by_lead": {10: np.zeros(4)},
            },
            "same lead times",
        ),
        (
            {
                "forecasts_by_lead": {-5: np.zeros((4, 3))},
                "observations_by_lead": {-5: np.zeros(4)},
            },
            "positive minutes",
        ),
        (
            {
                "forecasts_by_lead": {5: np.zeros((4, 1))},
                "observations_by_lead": {5: np.zeros(4)},
            },
            "at least two ensemble members",
        ),
        (
            {
                "forecasts_by_lead": {5: np.zeros(4)},
                "observations_by_lead": {5: np.zeros(4)},
            },
            "cases, members",
        ),
    ],
)
def test_malformed_verification_input_is_rejected(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        verify_ensemble_forecast(**kwargs)  # type: ignore[arg-type]


def test_a_negative_threshold_is_rejected() -> None:
    forecasts, observations, _ = _timeline(scale=0.5)
    with pytest.raises(ValueError, match="nonnegative"):
        verify_ensemble_forecast(forecasts, observations, threshold=-1.0)


def test_baseline_must_cover_the_same_leads() -> None:
    forecasts, observations, _ = _timeline(scale=0.5)
    with pytest.raises(ValueError, match="baseline must cover"):
        verify_ensemble_forecast(
            forecasts, observations, baseline_by_lead={99: np.zeros((CASES, 2))}
        )
