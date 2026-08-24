"""Deterministic route-aware pedestrian continuum primitives."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


@dataclass(frozen=True, slots=True)
class GridDomain:
    cell_size_m: float
    walkable_mask: BoolArray
    exit_mask: BoolArray | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.cell_size_m) or self.cell_size_m <= 0:
            raise ValueError("cell_size_m must be finite and positive")
        walkable = np.asarray(self.walkable_mask, dtype=bool)
        if walkable.ndim != 2 or not walkable.any():
            raise ValueError("walkable_mask must be a nonempty 2D array")
        exits = (
            np.zeros_like(walkable)
            if self.exit_mask is None
            else np.asarray(self.exit_mask, dtype=bool)
        )
        if exits.shape != walkable.shape:
            raise ValueError("exit_mask shape must match walkable_mask")
        if np.any(exits & ~walkable):
            raise ValueError("exits must be walkable")
        object.__setattr__(self, "walkable_mask", walkable.copy())
        object.__setattr__(self, "exit_mask", exits.copy())

    @property
    def shape(self) -> tuple[int, int]:
        return self.walkable_mask.shape

    @property
    def exits(self) -> BoolArray:
        if self.exit_mask is None:
            raise RuntimeError("exit_mask was not initialized")
        return self.exit_mask


@dataclass(frozen=True, slots=True)
class RouteState:
    density_ppm2: FloatArray
    velocity_mps: FloatArray
    domain: GridDomain
    route_names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        density = np.asarray(self.density_ppm2, dtype=float)
        velocity = np.asarray(self.velocity_mps, dtype=float)
        if density.ndim != 3 or density.shape[1:] != self.domain.shape:
            raise ValueError("density must have shape (routes, rows, columns)")
        if velocity.shape != (*density.shape, 2):
            raise ValueError("velocity must have shape (routes, rows, columns, 2)")
        if not np.all(np.isfinite(density)) or not np.all(np.isfinite(velocity)):
            raise ValueError("route state arrays must be finite")
        if np.any(density < 0):
            raise ValueError("density must be nonnegative")
        if np.any(density[:, ~self.domain.walkable_mask] != 0):
            raise ValueError("non-walkable cells must have zero density")
        names = self.route_names or tuple(f"route-{index}" for index in range(density.shape[0]))
        if len(names) != density.shape[0] or len(set(names)) != len(names):
            raise ValueError("route_names must be unique and match route count")
        object.__setattr__(self, "density_ppm2", density.copy())
        object.__setattr__(self, "velocity_mps", velocity.copy())
        object.__setattr__(self, "route_names", names)

    @property
    def total_density_ppm2(self) -> FloatArray:
        return self.density_ppm2.sum(axis=0)

    @property
    def mass_people(self) -> float:
        return float(self.density_ppm2.sum() * self.domain.cell_size_m**2)


def weidmann_speed(
    density_ppm2: NDArray[np.floating] | list[float],
    *,
    free_speed_mps: float = 1.34,
    jam_density_ppm2: float = 5.4,
    shape: float = 1.913,
) -> FloatArray:
    """Return the Weidmann speed-density relation in metres per second."""

    density = np.asarray(density_ppm2, dtype=float)
    if not np.all(np.isfinite(density)) or np.any(density < 0):
        raise ValueError("density must be finite and nonnegative")
    if free_speed_mps <= 0 or jam_density_ppm2 <= 0 or shape <= 0:
        raise ValueError("Weidmann parameters must be positive")
    speed = np.zeros(density.shape, dtype=np.float64)
    empty = density == 0
    active = (density > 0) & (density < jam_density_ppm2)
    speed[empty] = free_speed_mps
    if np.any(active):
        inverse_gap = (1.0 / density[active]) - (1.0 / jam_density_ppm2)
        speed[active] = free_speed_mps * (1.0 - np.exp(-shape * inverse_gap))
    speed[speed < 0.0] = 0.0
    speed[speed > free_speed_mps] = free_speed_mps
    return speed


def solve_travel_time(
    domain: GridDomain,
    *,
    speed_mps: float | NDArray[np.floating] = 1.0,
) -> FloatArray:
    """Solve a grid eikonal approximation with Dijkstra's method."""

    speed = np.broadcast_to(np.asarray(speed_mps, dtype=float), domain.shape)
    if np.any(~np.isfinite(speed[domain.walkable_mask])) or np.any(
        speed[domain.walkable_mask] <= 0
    ):
        raise ValueError("speed must be finite and positive on walkable cells")
    if not np.any(domain.exits):
        raise ValueError("at least one exit is required")
    travel = np.full(domain.shape, np.inf, dtype=float)
    queue: list[tuple[float, int, int]] = []
    for row, column in np.argwhere(domain.exits):
        travel[row, column] = 0.0
        heapq.heappush(queue, (0.0, int(row), int(column)))
    rows, columns = domain.shape
    while queue:
        cost, row, column = heapq.heappop(queue)
        if cost > travel[row, column]:
            continue
        for delta_row, delta_column in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            next_row = row + delta_row
            next_column = column + delta_column
            if not (0 <= next_row < rows and 0 <= next_column < columns):
                continue
            if not domain.walkable_mask[next_row, next_column]:
                continue
            face_speed = 0.5 * (
                speed[row, column] + speed[next_row, next_column]
            )
            candidate = cost + domain.cell_size_m / face_speed
            if candidate < travel[next_row, next_column]:
                travel[next_row, next_column] = candidate
                heapq.heappush(queue, (candidate, next_row, next_column))
    return travel


def desired_directions(travel_time_s: FloatArray, domain: GridDomain) -> FloatArray:
    """Return unit vectors toward a lower travel-time neighbour."""

    travel = np.asarray(travel_time_s, dtype=float)
    if travel.shape != domain.shape:
        raise ValueError("travel-time shape must match the domain")
    directions = np.zeros((*domain.shape, 2), dtype=float)
    rows, columns = domain.shape
    for row, column in np.argwhere(domain.walkable_mask):
        if not np.isfinite(travel[row, column]) or domain.exits[row, column]:
            continue
        best = travel[row, column]
        vector = (0.0, 0.0)
        for delta_row, delta_column in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            next_row = int(row) + delta_row
            next_column = int(column) + delta_column
            if not (0 <= next_row < rows and 0 <= next_column < columns):
                continue
            if not domain.walkable_mask[next_row, next_column]:
                continue
            candidate = travel[next_row, next_column]
            if candidate < best:
                best = candidate
                vector = (float(delta_column), float(delta_row))
        directions[row, column] = vector
    return directions


@dataclass(frozen=True, slots=True)
class ContinuityDiagnostics:
    cfl_number: float
    substeps: int
    mass_before_people: float
    mass_after_people: float
    outflow_people: float
    mass_balance_error_people: float


@dataclass(frozen=True, slots=True)
class ContinuityResult:
    density_ppm2: FloatArray
    diagnostics: ContinuityDiagnostics


def compute_cfl(
    velocity_mps: NDArray[np.floating],
    domain: GridDomain,
    *,
    dt_s: float,
) -> float:
    velocity = np.asarray(velocity_mps, dtype=float)
    if velocity.ndim != 4 or velocity.shape[1:3] != domain.shape or velocity.shape[-1] != 2:
        raise ValueError("velocity shape must be (routes, rows, columns, 2)")
    if not np.all(np.isfinite(velocity)) or dt_s < 0 or not math.isfinite(dt_s):
        raise ValueError("velocity and dt_s must be finite; dt_s must be nonnegative")
    if dt_s == 0:
        return 0.0
    characteristic = np.abs(velocity[..., 0]) + np.abs(velocity[..., 1])
    characteristic[:, ~domain.walkable_mask] = 0.0
    return float(characteristic.max(initial=0.0) * dt_s / domain.cell_size_m)


def advance_continuity(
    density_ppm2: NDArray[np.floating],
    velocity_mps: NDArray[np.floating],
    domain: GridDomain,
    *,
    dt_s: float,
) -> ContinuityResult:
    """Advance route densities with conservative first-order upwind fluxes."""

    density = np.asarray(density_ppm2, dtype=float).copy()
    velocity = np.asarray(velocity_mps, dtype=float)
    if density.ndim != 3 or density.shape[1:] != domain.shape:
        raise ValueError("density shape must be (routes, rows, columns)")
    if velocity.shape != (*density.shape, 2):
        raise ValueError("velocity shape must match density with a final xy axis")
    if not np.all(np.isfinite(density)) or not np.all(np.isfinite(velocity)):
        raise ValueError("density and velocity must be finite")
    if np.any(density < 0):
        raise ValueError("density must be nonnegative")
    if not math.isfinite(dt_s) or dt_s < 0:
        raise ValueError("dt_s must be finite and nonnegative")
    density[:, ~domain.walkable_mask] = 0.0
    mass_before = float(density.sum() * domain.cell_size_m**2)
    cfl = compute_cfl(velocity, domain, dt_s=dt_s)
    substeps = max(1, math.ceil(cfl - 1e-12))
    step = dt_s / substeps if substeps else 0.0
    outflow = 0.0
    for _ in range(substeps):
        density, step_outflow = _upwind_step(density, velocity, domain, step)
        outflow += step_outflow
    mass_after = float(density.sum() * domain.cell_size_m**2)
    expected_after = mass_before - outflow
    return ContinuityResult(
        density_ppm2=density,
        diagnostics=ContinuityDiagnostics(
            cfl_number=cfl,
            substeps=substeps,
            mass_before_people=mass_before,
            mass_after_people=mass_after,
            outflow_people=outflow,
            mass_balance_error_people=mass_after - expected_after,
        ),
    )


def _upwind_step(
    density: FloatArray,
    velocity: FloatArray,
    domain: GridDomain,
    dt_s: float,
) -> tuple[FloatArray, float]:
    routes, rows, columns = density.shape
    dx = domain.cell_size_m
    flux_x = np.zeros((routes, rows, columns + 1), dtype=float)
    flux_y = np.zeros((routes, rows + 1, columns), dtype=float)
    walkable = domain.walkable_mask

    for column in range(1, columns):
        valid = walkable[:, column - 1] & walkable[:, column]
        face_velocity = 0.5 * (
            velocity[:, :, column - 1, 0] + velocity[:, :, column, 0]
        )
        upwind = np.where(
            face_velocity >= 0,
            density[:, :, column - 1],
            density[:, :, column],
        )
        flux_x[:, :, column] = np.where(valid[None, :], face_velocity * upwind, 0.0)

    for row in range(1, rows):
        valid = walkable[row - 1, :] & walkable[row, :]
        face_velocity = 0.5 * (
            velocity[:, row - 1, :, 1] + velocity[:, row, :, 1]
        )
        upwind = np.where(
            face_velocity >= 0,
            density[:, row - 1, :],
            density[:, row, :],
        )
        flux_y[:, row, :] = np.where(valid[None, :], face_velocity * upwind, 0.0)

    exits = domain.exits
    left_velocity = velocity[:, :, 0, 0]
    right_velocity = velocity[:, :, -1, 0]
    top_velocity = velocity[:, 0, :, 1]
    bottom_velocity = velocity[:, -1, :, 1]
    flux_x[:, :, 0] = np.where(
        exits[:, 0][None, :] & (left_velocity < 0),
        left_velocity * density[:, :, 0],
        0.0,
    )
    flux_x[:, :, -1] = np.where(
        exits[:, -1][None, :] & (right_velocity > 0),
        right_velocity * density[:, :, -1],
        0.0,
    )
    flux_y[:, 0, :] = np.where(
        exits[0, :][None, :] & (top_velocity < 0),
        top_velocity * density[:, 0, :],
        0.0,
    )
    flux_y[:, -1, :] = np.where(
        exits[-1, :][None, :] & (bottom_velocity > 0),
        bottom_velocity * density[:, -1, :],
        0.0,
    )

    updated = density - (dt_s / dx) * (
        flux_x[:, :, 1:] - flux_x[:, :, :-1]
        + flux_y[:, 1:, :]
        - flux_y[:, :-1, :]
    )
    updated[:, ~walkable] = 0.0
    if np.min(updated, initial=0.0) < -1e-10:
        raise RuntimeError("CFL violation produced negative density")
    updated = np.maximum(updated, 0.0)
    boundary_outward = (
        -flux_x[:, :, 0].sum()
        + flux_x[:, :, -1].sum()
        - flux_y[:, 0, :].sum()
        + flux_y[:, -1, :].sum()
    )
    outflow_people = float(boundary_outward * dt_s * dx)
    return updated, outflow_people


__all__ = [
    "ContinuityDiagnostics",
    "ContinuityResult",
    "GridDomain",
    "RouteState",
    "advance_continuity",
    "compute_cfl",
    "desired_directions",
    "solve_travel_time",
    "weidmann_speed",
]
