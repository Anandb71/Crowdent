import numpy as np
import pytest

from stilldot.sensors import interpolate_to_rate, moving_rms


def test_interpolate_aligns_skewed_clocks() -> None:
    t_acc = np.linspace(0.0, 1.0, 101)
    t_gyro = t_acc + 0.004
    acc = np.column_stack([np.sin(2 * np.pi * t_acc), np.zeros(101), np.full(101, 9.8)])
    gyro = np.column_stack([np.zeros(101), np.zeros(101), np.cos(2 * np.pi * t_gyro)])

    t, acc_i, gyro_i = interpolate_to_rate(t_acc, acc, t_gyro, gyro, rate_hz=100.0)

    assert t[0] == pytest.approx(0.004, abs=1e-9)
    assert np.allclose(np.diff(t), 0.01, atol=1e-9)
    assert acc_i.shape == gyro_i.shape
    assert acc_i.shape[1] == 3


def test_interpolate_rejects_non_overlapping_streams() -> None:
    acc_t = np.array([0.0, 0.1])
    gyro_t = np.array([5.0, 5.1])
    zeros = np.zeros((2, 3))
    with pytest.raises(ValueError, match="overlap"):
        interpolate_to_rate(acc_t, zeros, gyro_t, zeros)


def test_moving_rms_of_constant_is_abs() -> None:
    signal = np.full(20, 3.0)
    rms = moving_rms(signal, window=5)
    assert np.allclose(rms, 3.0)
