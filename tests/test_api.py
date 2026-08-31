from fastapi.testclient import TestClient

from stilldot.api import app

client = TestClient(app)


def test_health_is_offline_and_research_only() -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["offline"] is True
    assert body["research_only"] is True
    assert body["hardware_actuation_available"] is False


def test_scenarios_lists_room_and_tunnel() -> None:
    res = client.get("/api/scenarios")
    ids = {row["id"] for row in res.json()}
    assert ids == {"room_walk", "tunnel"}


def test_run_room_walk() -> None:
    res = client.get("/api/scenarios/room_walk/run")
    assert res.status_code == 200
    body = res.json()
    assert body["metrics"]["requirement_met"] is True
    assert body["metrics"]["drift_pct"] < 10.0
    assert body["frames"]


def test_unknown_scenario_is_404() -> None:
    res = client.get("/api/scenarios/nope/run")
    assert res.status_code == 404


def test_live_rejects_short_payload() -> None:
    res = client.post("/api/live", json={"samples": []})
    assert res.status_code == 422
