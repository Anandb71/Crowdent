from datetime import UTC, datetime

from fastapi.testclient import TestClient

from crowdent.api import create_app
from crowdent.contracts import ReadinessState
from crowdent.core import ResearchService
from crowdent.runtime import RuntimeProfile, RuntimeSettings
from crowdent.safety import ReadinessEvaluator, RecommendationPolicy, SafetySignals

NOW = datetime(2026, 8, 24, 10, 0, tzinfo=UTC)


def test_api_exposes_no_hardware_or_actuation_routes() -> None:
    app = create_app(settings=RuntimeSettings.for_profile(RuntimeProfile.DEMO))
    paths = " ".join(getattr(route, "path", "") for route in app.routes).lower()

    assert "actuate" not in paths
    assert "/hardware" not in paths
    assert "signage" not in paths


def test_security_headers_are_present_on_health() -> None:
    client = TestClient(create_app(settings=RuntimeSettings.for_profile(RuntimeProfile.DEMO)))
    response = client.get("/health/live")

    assert response.status_code == 200
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_actuate_tokens_are_blocked_even_when_ready() -> None:
    assessment = ReadinessEvaluator().evaluate(SafetySignals(now=NOW))
    policy = RecommendationPolicy(allowed_actions=frozenset({"PAUSE_INFLOW"}))

    decision = policy.evaluate(
        action="ACTUATE_GATE",
        assessment=assessment,
        parameters={"gate": "north"},
    )

    assert assessment.state is ReadinessState.READY
    assert decision.permitted is False
    assert decision.hardware_actuation_available is False
    assert decision.countdown_seconds is None


def test_degraded_readiness_keeps_status_advisory_empty() -> None:
    settings = RuntimeSettings.for_profile(RuntimeProfile.DEMO)
    service = ResearchService(settings=settings, clock=lambda: NOW)
    client = TestClient(create_app(settings=settings, engine=service))

    status = client.get("/api/v1/status")
    forecast = client.get("/api/v1/forecasts/latest")

    assert status.json()["hardware_actuation_available"] is False
    assert forecast.json()["advice"] == []
    assert forecast.json()["countdown_seconds"] is None
