import numpy as np

from stilldot.filter import DeadReckonFilter, NaiveIntegrator


def test_zupt_zeros_speed_and_learns_gyro_bias() -> None:
    filt = DeadReckonFilter()
    filt.state.v = 2.0
    for _ in range(80):
        filt.predict(gyro_z=0.01, dt=0.01, trust=0.9)
        filt.update_zupt(gyro_z=0.01)
    assert abs(filt.state.v) < 0.05
    assert abs(filt.state.bg - 0.01) < 0.005


def test_forward_integration_tracks_a_straight_line() -> None:
    filt = DeadReckonFilter()
    dt = 0.01
    for _ in range(200):
        filt.predict(gyro_z=0.0, dt=dt, trust=1.0)
        filt.update_odometer(2.0, trust=1.0)
    assert abs(filt.state.x - 4.0) < 0.4
    assert abs(filt.state.y) < 0.15


def test_naive_double_integrate_grows_with_time_squared() -> None:
    short = NaiveIntegrator()
    long = NaiveIntegrator()
    bias = 0.08
    for _ in range(200):
        short.step(bias, 0.0, 0.0, 0.01)
    for _ in range(800):
        long.step(bias, 0.0, 0.0, 0.01)
    assert long.state.x > 4.0 * short.state.x
    assert np.isfinite(long.state.x)
