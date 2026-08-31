import numpy as np

from stilldot.alignment import estimate_alignment, gravity_roll_pitch, rotation_from_rpy
from stilldot.sensors import G


def test_level_phone_has_near_zero_roll_pitch() -> None:
    roll, pitch = gravity_roll_pitch(np.array([0.0, 0.0, G]))
    assert abs(roll) < 1e-6
    assert abs(pitch) < 1e-6


def test_rotation_round_trip_maps_gravity_to_z() -> None:
    rot = rotation_from_rpy(0.2, -0.1, 0.3)
    g_phone = rot.T @ np.array([0.0, 0.0, G])
    recovered = rot @ g_phone
    assert np.allclose(recovered, [0.0, 0.0, G], atol=1e-9)


def test_alignment_recovers_yaw_within_fifteen_degrees() -> None:
    rate = 100.0
    n = 400
    t = np.arange(n) / rate
    # 1.2 s still, then a surge along +X in nav
    acc_nav = np.zeros((n, 3))
    acc_nav[:, 2] = G
    acc_nav[120:, 0] = 1.2
    gyro = np.zeros((n, 3))
    mount = rotation_from_rpy(0.1, -0.05, 0.4)
    acc_phone = (mount.T @ acc_nav.T).T
    gyro_phone = (mount.T @ gyro.T).T

    rot, _yaw_deg = estimate_alignment(acc_phone, gyro_phone, rate)
    recovered = rot @ acc_phone[200]
    # Forward surge should land mostly on +X after alignment
    assert recovered[0] > 0.8
    heading_err = abs(np.degrees(np.arctan2(recovered[1], recovered[0])))
    assert heading_err < 15.0
    _ = t
