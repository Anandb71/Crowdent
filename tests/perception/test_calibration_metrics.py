from __future__ import annotations

import numpy as np
import pytest

from crowdent.perception import (
    CROWD_PRESSURE_INDEX_UNITS,
    HomographyCalibration,
    calibrate_homography,
    compute_crowd_pressure_index,
    crowd_flux,
)


def _calibration() -> HomographyCalibration:
    image = np.array([[0.0, 0.0], [100.0, 0.0], [100.0, 50.0], [0.0, 50.0]])
    ground = np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]])
    return calibrate_homography(
        image,
        ground,
        max_reprojection_error_m=1e-9,
        max_condition_number=1e6,
    )


def test_homography_projects_points_and_velocities_in_si_units() -> None:
    calibration = _calibration()

    ground = calibration.project_points(np.array([[25.0, 10.0]]))
    endpoint_velocity = calibration.project_velocities(
        np.array([[25.0, 10.0]]),
        np.array([[20.0, 5.0]]),
        method="endpoint",
    )
    jacobian_velocity = calibration.project_velocities(
        np.array([[25.0, 10.0]]),
        np.array([[20.0, 5.0]]),
        method="jacobian",
    )

    np.testing.assert_allclose(ground, np.array([[2.5, 2.0]]), atol=1e-9)
    np.testing.assert_allclose(endpoint_velocity, np.array([[2.0, 1.0]]), atol=1e-9)
    np.testing.assert_allclose(jacobian_velocity, endpoint_velocity, atol=1e-9)
    assert calibration.reprojection_rmse_m < 1e-9
    assert calibration.contains_image_points(np.array([[50.0, 25.0]]))[0]
    assert not calibration.contains_image_points(np.array([[101.0, 25.0]]))[0]


def test_calibration_rejects_degenerate_or_badly_fitted_data() -> None:
    collinear = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [3.0, 0.0]])
    with pytest.raises(ValueError, match="degenerate|condition"):
        calibrate_homography(collinear, collinear)

    image = np.array(
        [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [5.0, 5.0]]
    )
    ground = image.copy()
    ground[-1] = np.array([100.0, 100.0])
    with pytest.raises(ValueError, match="reprojection"):
        calibrate_homography(image, ground, max_reprojection_error_m=0.1)


def test_flux_uses_independent_density_and_has_people_per_metre_second_units() -> None:
    density_ppm2 = np.array([2.0, 3.0])
    velocity_mps = np.array([[1.5, 0.0], [-2.0, 0.5]])

    flux = crowd_flux(density_ppm2, velocity_mps, normal=np.array([1.0, 0.0]))

    np.testing.assert_allclose(flux, np.array([3.0, -6.0]))


def test_crowd_pressure_is_explicitly_an_index_not_pascals() -> None:
    density_ppm2 = np.array([2.0, 4.0])
    velocity_variance_m2ps2 = np.array([0.5, 0.25])

    index = compute_crowd_pressure_index(density_ppm2, velocity_variance_m2ps2)

    np.testing.assert_allclose(index.values, np.array([1.0, 1.0]))
    assert index.units == CROWD_PRESSURE_INDEX_UNITS
    assert "index" in index.label.lower()
    assert "pascal" not in index.units.lower()


def test_perception_arrays_must_be_finite() -> None:
    with pytest.raises(ValueError, match="finite"):
        crowd_flux(
            np.array([np.nan]),
            np.array([[1.0, 0.0]]),
            normal=np.array([1.0, 0.0]),
        )
