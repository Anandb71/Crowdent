from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from crowdent.contracts import (
    Forecast,
    FusedStateSummary,
    Provenance,
    QualityFlag,
    ReadinessState,
)

NOW = datetime(2026, 8, 24, 10, 0, tzinfo=UTC)
HASH = "a" * 64


def metadata() -> dict[str, object]:
    return {
        "timestamp": NOW,
        "source_id": "fusion-primary",
        "run_id": "run-001",
        "site_id": "site-a",
        "sequence": 7,
        "config_hash": HASH,
        "model_hash": HASH,
        "calibration_hash": HASH,
    }


def provenance() -> Provenance:
    return Provenance(
        source_id="camera-north",
        observed_at=NOW,
        sequence=41,
        content_hash=HASH,
    )


def test_contract_rejects_naive_timestamps_and_non_finite_values() -> None:
    values = metadata()
    values["timestamp"] = NOW.replace(tzinfo=None)
    with pytest.raises(ValidationError, match="timezone-aware"):
        FusedStateSummary(
            **values,
            mean=(1.0, 2.0),
            covariance=((1.0, 0.0), (0.0, 1.0)),
            density_people_per_m2=1.2,
            speed_mps=0.4,
            units={"density": "people/m^2", "speed": "m/s"},
            coordinate_frame="site-local-enu",
            provenance=(provenance(),),
        )

    values = metadata()
    with pytest.raises(ValidationError):
        FusedStateSummary(
            **values,
            mean=(float("nan"), 2.0),
            covariance=((1.0, 0.0), (0.0, 1.0)),
            density_people_per_m2=1.2,
            speed_mps=0.4,
            units={"density": "people/m^2", "speed": "m/s"},
            coordinate_frame="site-local-enu",
            provenance=(provenance(),),
        )


def test_covariance_must_be_square_and_symmetric() -> None:
    with pytest.raises(ValidationError, match="square"):
        FusedStateSummary(
            **metadata(),
            mean=(1.0, 2.0),
            covariance=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
            density_people_per_m2=1.2,
            speed_mps=0.4,
            units={"density": "people/m^2", "speed": "m/s"},
            coordinate_frame="site-local-enu",
            provenance=(provenance(),),
        )


def test_degraded_forecast_cannot_expose_countdown_or_advice() -> None:
    with pytest.raises(ValidationError, match="countdown"):
        Forecast(
            **metadata(),
            target_timestamp=NOW + timedelta(seconds=30),
            horizon_seconds=30,
            risk_probability=0.7,
            risk_interval=(0.6, 0.8),
            covariance=((0.1,),),
            readiness=ReadinessState.DEGRADED,
            quality_flags=(QualityFlag.STALE_INPUT,),
            countdown_seconds=12,
            advice=("Pause inflow",),
            units={"risk_probability": "1"},
            coordinate_frame="site-local-enu",
            provenance=(provenance(),),
        )

    forecast = Forecast(
        **metadata(),
        target_timestamp=NOW + timedelta(seconds=30),
        horizon_seconds=30,
        risk_probability=None,
        risk_interval=None,
        covariance=((0.1,),),
        readiness=ReadinessState.UNKNOWN,
        quality_flags=(QualityFlag.MISSING_INPUT,),
        units={"risk_probability": "1"},
        coordinate_frame="site-local-enu",
        provenance=(provenance(),),
    )
    assert forecast.research_only is True
    assert forecast.countdown_seconds is None
    assert forecast.advice == ()
