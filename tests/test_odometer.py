import numpy as np

from stilldot.odometer import estimate_speed
from stilldot.sensors import G
from stilldot.types import VehicleClass


def test_stillness_is_zupt_and_zero_speed() -> None:
    n = 200
    acc = np.zeros((n, 3))
    acc[:, 2] = G
    gyro = np.zeros((n, 3))
    speed, zupt = estimate_speed(acc, gyro, 100.0, VehicleClass.PEDESTRIAN)
    assert bool(np.all(zupt[50:]))
    assert float(np.max(speed[50:])) < 0.05


def test_vehicle_vibration_scales_with_speed() -> None:
    rate = 100.0
    n = 400
    t = np.arange(n) / rate
    acc_slow = np.zeros((n, 3))
    acc_fast = np.zeros((n, 3))
    acc_slow[:, 2] = G + 0.22 * 5.0 * np.sin(2 * np.pi * 16 * t)
    acc_fast[:, 2] = G + 0.22 * 16.0 * np.sin(2 * np.pi * 16 * t)
    gyro = np.zeros((n, 3))
    v_slow, z_slow = estimate_speed(acc_slow, gyro, rate, VehicleClass.VEHICLE)
    v_fast, z_fast = estimate_speed(acc_fast, gyro, rate, VehicleClass.VEHICLE)
    assert not bool(np.all(z_fast[100:]))
    assert float(np.median(v_fast[150:])) > float(np.median(v_slow[150:]))
    _ = z_slow
