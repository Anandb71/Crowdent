from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from crowdent.api import create_app
from crowdent.contracts import (
    Forecast,
    Provenance,
    ReadinessState,
    RuntimeMode,
)
from crowdent.core import ResearchService
from crowdent.runtime import RuntimeProfile, RuntimeSettings

NOW = datetime(2026, 8, 24, 10, 0, tzinfo=UTC)
HASH = "b" * 64


def ready_forecast() -> Forecast:
    return Forecast(
        timestamp=NOW,
        target_timestamp=NOW + timedelta(seconds=30),
        horizon_seconds=30,
        source_id="forecast-engine",
        run_id="run-001",
        site_id="site-a",
        sequence=9,
        config_hash=HASH,
        model_hash=HASH,
        calibration_hash=HASH,
        risk_probability=0.65,
        risk_interval=(0.55, 0.75),
        covariance=((0.03,),),
        readiness=ReadinessState.READY,
        units={"risk_probability": "1"},
        coordinate_frame="site-local-enu",
        provenance=(
            Provenance(
                source_id="fusion-primary",
                observed_at=NOW,
                sequence=8,
                content_hash=HASH,
            ),
        ),
    )


def test_placeholder_health_and_status_are_safe() -> None:
    settings = RuntimeSettings.for_profile(RuntimeProfile.DEMO)
    client = TestClient(create_app(settings=settings))

    live = client.get("/health/live")
    ready = client.get("/health/ready")
    status = client.get("/api/v1/status")
    forecast = client.get("/api/v1/forecasts/latest")

    assert live.status_code == 200
    assert live.json()["research_only"] is True
    assert live.json()["hardware_actuation_available"] is False
    assert ready.status_code == 503
    assert status.json()["readiness"] == "UNKNOWN"
    assert status.json()["research_only"] is True
    assert forecast.json()["countdown_seconds"] is None
    assert forecast.json()["advice"] == []


def test_instruction_lifecycle_is_human_controlled_and_audited() -> None:
    settings = RuntimeSettings.for_profile(RuntimeProfile.DEMO)
    service = ResearchService(settings=settings, clock=lambda: NOW)
    service.set_latest_forecast(ready_forecast())
    client = TestClient(create_app(settings=settings, engine=service))
    supervisor = {
        "X-Crowdent-Actor": "supervisor-1",
        "X-Crowdent-Role": "supervisor",
    }

    evaluation = client.post(
        "/api/v1/interventions/evaluate",
        headers=supervisor,
        json={
            "scenario_id": "scenario-1",
            "action": "PAUSE_INFLOW",
            "parameters": {"gate": "north"},
        },
    )
    assert evaluation.status_code == 200
    assert evaluation.json()["permitted"] is True

    draft = client.post(
        "/api/v1/instructions",
        headers=supervisor,
        json={
            "scenario_id": "scenario-1",
            "recommendation": "PAUSE_INFLOW",
            "text": "Pause admission at the north gate.",
            "expires_at": (NOW + timedelta(minutes=5)).isoformat(),
        },
    )
    assert draft.status_code == 201
    instruction_id = draft.json()["instruction_id"]
    assert draft.json()["lifecycle"] == "draft"

    acknowledged = client.post(
        f"/api/v1/instructions/{instruction_id}/acknowledge",
        headers={
            "X-Crowdent-Actor": "operator-1",
            "X-Crowdent-Role": "operator",
        },
        json={"reason": "Reviewed on the research console."},
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["lifecycle"] == "acknowledged"

    accepted = client.post(
        f"/api/v1/instructions/{instruction_id}/accept",
        headers=supervisor,
        json={"reason": "Supervisor accepted the research recommendation."},
    )
    assert accepted.status_code == 200
    assert accepted.json()["lifecycle"] == "accepted"

    confirmed = client.post(
        f"/api/v1/instructions/{instruction_id}/physical-action-confirmed",
        headers=supervisor,
        json={"reason": "A human reported the physical action separately."},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["lifecycle"] == "physical_action_confirmed"
    assert confirmed.json()["hardware_actuation_available"] is False

    audit = client.get("/api/v1/audit", headers=supervisor)
    assert audit.status_code == 200
    assert len(audit.json()["records"]) == 4
    assert audit.json()["research_only"] is True


def test_field_mode_disables_docs_and_requires_authentication() -> None:
    settings = RuntimeSettings.for_profile(RuntimeProfile.FIELD)
    app = create_app(settings=settings)
    client = TestClient(app)

    assert settings.mode is RuntimeMode.FIELD_RESEARCH
    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None
    assert client.get("/api/v1/audit").status_code == 401


def test_websocket_stream_starts_with_safe_status() -> None:
    settings = RuntimeSettings.for_profile(RuntimeProfile.DEMO)
    client = TestClient(create_app(settings=settings))

    with client.websocket_connect("/api/v1/ws/status") as websocket:
        status = websocket.receive_json()

    assert status["research_only"] is True
    assert status["hardware_actuation_available"] is False
    assert status["readiness"] == "UNKNOWN"
