import pytest

from stilldot.engine import run_live_samples, run_scenario
from stilldot.types import ImuSample


def test_room_walk_meets_ten_percent_and_beats_naive() -> None:
    result = run_scenario("room_walk")
    m = result.metrics
    assert m.distance_m == pytest.approx(50.0, rel=0.12)
    assert m.drift_pct < 10.0
    assert m.requirement_met
    assert m.naive_drift_m > m.drift_m
    assert m.zupt_locked
    assert result.frames[0].gnss_denied
    assert result.frames[-1].zupt


def test_tunnel_meets_ten_percent() -> None:
    result = run_scenario("tunnel")
    m = result.metrics
    assert m.distance_m == pytest.approx(1000.0, rel=0.15)
    assert m.drift_pct < 10.0
    assert m.naive_drift_m > m.drift_m
    assert result.metrics.output_hz == 10.0


def test_unknown_scenario_raises() -> None:
    with pytest.raises(KeyError, match="unknown"):
        run_scenario("moonwalk")


def test_live_samples_need_a_minimum_window() -> None:
    with pytest.raises(ValueError, match="16"):
        run_live_samples([ImuSample(t=0.0, acc=(0.0, 0.0, 9.8), gyro=(0.0, 0.0, 0.0))])


def test_live_batch_returns_a_track() -> None:
    samples = [
        ImuSample(
            t=i * 0.01,
            acc=(0.0, 0.0, 9.81),
            gyro=(0.0, 0.0, 0.0),
        )
        for i in range(200)
    ]
    result = run_live_samples(samples)
    assert result.scenario.id == "live"
    assert result.frames
    assert result.metrics.final_speed == pytest.approx(0.0, abs=0.2)
