from __future__ import annotations

import numpy as np
import pytest

from crowdent.numerics import (
    GridDomain,
    RouteState,
    advance_continuity,
    compute_cfl,
    desired_directions,
    solve_travel_time,
    weidmann_speed,
)


def test_route_state_supports_opposing_flows_and_rejects_nonfinite_values() -> None:
    walkable = np.ones((3, 4), dtype=bool)
    domain = GridDomain(cell_size_m=0.5, walkable_mask=walkable)
    density = np.full((2, 3, 4), 0.8)
    velocity = np.zeros((2, 3, 4, 2))
    velocity[0, ..., 0] = 1.0
    velocity[1, ..., 0] = -1.0

    state = RouteState(
        density_ppm2=density,
        velocity_mps=velocity,
        domain=domain,
        route_names=("eastbound", "westbound"),
    )

    np.testing.assert_allclose(state.total_density_ppm2, 1.6)
    assert state.mass_people == pytest.approx(2 * 3 * 4 * 0.8 * 0.25)

    density[0, 0, 0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        RouteState(density, velocity, domain)


def test_weidmann_relation_is_safe_at_empty_and_jam_density() -> None:
    rho = np.array([0.0, 0.5, 2.0, 5.4, 6.0])
    speed = weidmann_speed(rho, free_speed_mps=1.34, jam_density_ppm2=5.4)

    assert speed[0] == pytest.approx(1.34)
    assert speed[-2] == 0.0
    assert speed[-1] == 0.0
    assert np.all(np.diff(speed) <= 0.0)
    assert np.all(np.isfinite(speed))


def test_travel_time_marks_unreachable_cells_and_directions_do_not_cross_walls() -> None:
    walkable = np.ones((5, 7), dtype=bool)
    walkable[:, 3] = False
    walkable[2, 3] = True
    walkable[2, 2] = False  # The left side remains disconnected from the opening.
    exits = np.zeros_like(walkable)
    exits[2, 6] = True
    domain = GridDomain(1.0, walkable, exit_mask=exits)

    travel_time = solve_travel_time(domain, speed_mps=1.0)
    direction = desired_directions(travel_time, domain)

    assert np.isinf(travel_time[0, 0])
    assert travel_time[2, 6] == 0.0
    assert np.all(direction[~walkable] == 0.0)
    assert direction[2, 4, 0] > 0.0
    assert direction[1, 2, 0] <= 0.0  # Never points east into the wall at (1, 3).


def test_first_order_upwind_matches_unit_courant_translation() -> None:
    walkable = np.ones((3, 8), dtype=bool)
    domain = GridDomain(1.0, walkable)
    density = np.zeros((1, 3, 8))
    density[0, 1, 2:4] = 1.0
    velocity = np.zeros((1, 3, 8, 2))
    velocity[..., 0] = 1.0

    result = advance_continuity(density, velocity, domain, dt_s=1.0)

    expected = np.zeros_like(density)
    expected[0, 1, 3:5] = 1.0
    np.testing.assert_allclose(result.density_ppm2, expected, atol=1e-12)
    assert result.diagnostics.cfl_number == pytest.approx(1.0)
    assert result.diagnostics.mass_balance_error_people == pytest.approx(0.0, abs=1e-12)
    assert np.all(result.density_ppm2 >= 0.0)


def test_walls_have_zero_flux_and_large_steps_are_safely_subcycled() -> None:
    walkable = np.ones((3, 7), dtype=bool)
    walkable[:, 3] = False
    domain = GridDomain(1.0, walkable)
    density = np.zeros((1, 3, 7))
    density[0, 1, 2] = 2.0
    velocity = np.zeros((1, 3, 7, 2))
    velocity[..., 0] = 2.0

    assert compute_cfl(velocity, domain, dt_s=2.0) == pytest.approx(4.0)
    result = advance_continuity(density, velocity, domain, dt_s=2.0)

    assert np.sum(result.density_ppm2[..., 4:]) == 0.0
    assert result.diagnostics.substeps == 4
    assert result.diagnostics.mass_after_people == pytest.approx(
        result.diagnostics.mass_before_people
    )
    assert np.all(result.density_ppm2 >= 0.0)


def test_exit_flux_is_reported_in_mass_balance() -> None:
    walkable = np.ones((1, 3), dtype=bool)
    exits = np.zeros_like(walkable)
    exits[0, -1] = True
    domain = GridDomain(1.0, walkable, exit_mask=exits)
    density = np.ones((1, 1, 3))
    velocity = np.zeros((1, 1, 3, 2))
    velocity[..., 0] = 1.0

    result = advance_continuity(density, velocity, domain, dt_s=0.5)

    assert result.diagnostics.outflow_people > 0.0
    assert result.diagnostics.mass_after_people == pytest.approx(
        result.diagnostics.mass_before_people - result.diagnostics.outflow_people
    )
    assert result.diagnostics.mass_balance_error_people == pytest.approx(0.0, abs=1e-12)
