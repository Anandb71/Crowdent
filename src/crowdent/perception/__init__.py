"""Ground-plane calibration and replaceable offline perception adapters."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

import cv2
import numpy as np
import onnxruntime as ort
from numpy.typing import NDArray

CROWD_PRESSURE_INDEX_UNITS = "s^-2 (density-weighted velocity-variance index)"


def _points(value: NDArray[np.floating], name: str) -> NDArray[np.float64]:
    array = np.asarray(value, dtype=float)
    if array.ndim != 2 or array.shape[1] != 2 or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a finite array with shape (points, 2)")
    return array


@dataclass(frozen=True, slots=True)
class HomographyCalibration:
    matrix: NDArray[np.float64]
    image_points: NDArray[np.float64]
    ground_points_m: NDArray[np.float64]
    image_support_polygon: NDArray[np.float64]
    reprojection_rmse_m: float
    condition_number: float

    def project_points(
        self,
        image_points: NDArray[np.floating],
        *,
        require_support: bool = True,
    ) -> NDArray[np.float64]:
        points = _points(image_points, "image_points")
        if require_support and not np.all(self.contains_image_points(points)):
            raise ValueError("image point lies outside the surveyed support polygon")
        homogeneous = np.column_stack((points, np.ones(points.shape[0])))
        mapped = homogeneous @ self.matrix.T
        if np.any(np.abs(mapped[:, 2]) < 1e-12):
            raise ValueError("homography maps point to infinity")
        return mapped[:, :2] / mapped[:, 2, None]

    def contains_image_points(
        self,
        image_points: NDArray[np.floating],
    ) -> NDArray[np.bool_]:
        points = _points(image_points, "image_points")
        polygon = self.image_support_polygon.astype(np.float32)
        return np.array(
            [
                cv2.pointPolygonTest(polygon, tuple(map(float, point)), False) >= 0
                for point in points
            ],
            dtype=bool,
        )

    def project_velocities(
        self,
        image_points: NDArray[np.floating],
        velocity_px_per_s: NDArray[np.floating],
        *,
        method: Literal["endpoint", "jacobian"] = "endpoint",
    ) -> NDArray[np.float64]:
        points = _points(image_points, "image_points")
        velocity = _points(velocity_px_per_s, "velocity_px_per_s")
        if velocity.shape != points.shape:
            raise ValueError("velocity shape must match points")
        if method == "endpoint":
            start = self.project_points(points)
            end = self.project_points(points + velocity)
            return end - start
        if method != "jacobian":
            raise ValueError("method must be endpoint or jacobian")
        h = self.matrix
        x = points[:, 0]
        y = points[:, 1]
        denominator = h[2, 0] * x + h[2, 1] * y + h[2, 2]
        numerator_x = h[0, 0] * x + h[0, 1] * y + h[0, 2]
        numerator_y = h[1, 0] * x + h[1, 1] * y + h[1, 2]
        jacobian = np.empty((points.shape[0], 2, 2), dtype=float)
        jacobian[:, 0, 0] = (
            h[0, 0] * denominator - numerator_x * h[2, 0]
        ) / denominator**2
        jacobian[:, 0, 1] = (
            h[0, 1] * denominator - numerator_x * h[2, 1]
        ) / denominator**2
        jacobian[:, 1, 0] = (
            h[1, 0] * denominator - numerator_y * h[2, 0]
        ) / denominator**2
        jacobian[:, 1, 1] = (
            h[1, 1] * denominator - numerator_y * h[2, 1]
        ) / denominator**2
        mapped = np.einsum("nij,nj->ni", jacobian, velocity)
        return np.asarray(mapped, dtype=np.float64)


def calibrate_homography(
    image_points: NDArray[np.floating],
    ground_points_m: NDArray[np.floating],
    *,
    max_reprojection_error_m: float = 0.25,
    max_condition_number: float = 1e8,
) -> HomographyCalibration:
    image = _points(image_points, "image_points")
    ground = _points(ground_points_m, "ground_points_m")
    if image.shape != ground.shape or image.shape[0] < 4:
        raise ValueError("homography requires at least four corresponding points")
    if np.linalg.matrix_rank(np.column_stack((image, np.ones(image.shape[0])))) < 3:
        raise ValueError("degenerate image calibration geometry")
    if np.linalg.matrix_rank(np.column_stack((ground, np.ones(ground.shape[0])))) < 3:
        raise ValueError("degenerate ground calibration geometry")
    matrix, _ = cv2.findHomography(image.astype(np.float64), ground.astype(np.float64), 0)
    if matrix is None or not np.all(np.isfinite(matrix)):
        raise ValueError("degenerate homography")
    matrix = matrix / matrix[2, 2]
    condition = float(np.linalg.cond(matrix))
    if not math.isfinite(condition) or condition > max_condition_number:
        raise ValueError("homography condition number exceeds limit")
    homogeneous = np.column_stack((image, np.ones(image.shape[0])))
    mapped = homogeneous @ matrix.T
    projected = mapped[:, :2] / mapped[:, 2, None]
    rmse = float(np.sqrt(np.mean(np.sum((projected - ground) ** 2, axis=1))))
    if rmse > max_reprojection_error_m:
        raise ValueError("homography reprojection error exceeds limit")
    polygon = cv2.convexHull(image.astype(np.float32)).reshape(-1, 2).astype(float)
    return HomographyCalibration(
        matrix=matrix,
        image_points=image.copy(),
        ground_points_m=ground.copy(),
        image_support_polygon=polygon,
        reprojection_rmse_m=rmse,
        condition_number=condition,
    )


def crowd_flux(
    density_ppm2: NDArray[np.floating],
    velocity_mps: NDArray[np.floating],
    *,
    normal: NDArray[np.floating],
) -> NDArray[np.float64]:
    density = np.asarray(density_ppm2, dtype=float)
    velocity = np.asarray(velocity_mps, dtype=float)
    direction = np.asarray(normal, dtype=float)
    if not np.all(np.isfinite(density)) or not np.all(np.isfinite(velocity)):
        raise ValueError("density and velocity must be finite")
    if density.shape != velocity.shape[:-1] or velocity.shape[-1] != 2:
        raise ValueError("density and velocity shapes are incompatible")
    if direction.shape != (2,) or not np.all(np.isfinite(direction)):
        raise ValueError("normal must be a finite xy vector")
    norm = float(np.linalg.norm(direction))
    if norm <= 0:
        raise ValueError("normal must be nonzero")
    if np.any(density < 0):
        raise ValueError("density must be nonnegative")
    return np.asarray(
        density * np.einsum("...i,i->...", velocity, direction / norm),
        dtype=np.float64,
    )


@dataclass(frozen=True, slots=True)
class CrowdPressureIndex:
    values: NDArray[np.float64]
    units: str = CROWD_PRESSURE_INDEX_UNITS
    label: str = "Crowd pressure index (not mechanical pressure)"


def compute_crowd_pressure_index(
    density_ppm2: NDArray[np.floating],
    velocity_variance_m2ps2: NDArray[np.floating],
) -> CrowdPressureIndex:
    density = np.asarray(density_ppm2, dtype=float)
    variance = np.asarray(velocity_variance_m2ps2, dtype=float)
    if density.shape != variance.shape:
        raise ValueError("density and velocity variance shapes must match")
    if (
        not np.all(np.isfinite(density))
        or not np.all(np.isfinite(variance))
        or np.any(density < 0)
        or np.any(variance < 0)
    ):
        raise ValueError("density and velocity variance must be finite and nonnegative")
    return CrowdPressureIndex(values=density * variance)


@dataclass(frozen=True, slots=True)
class OpticalFlowConfig:
    pyramid_scale: float = 0.5
    levels: int = 3
    window_size: int = 15
    iterations: int = 3
    polynomial_neighborhood: int = 5
    polynomial_sigma: float = 1.2


@dataclass(frozen=True, slots=True)
class OpticalFlowResult:
    velocity_px_per_s: NDArray[np.float32]
    units: str = "pixels_per_second"


class OpticalFlowAdapter:
    def __init__(self, config: OpticalFlowConfig | None = None) -> None:
        self.config = config or OpticalFlowConfig()

    def estimate(
        self,
        previous_frame: NDArray[np.generic],
        current_frame: NDArray[np.generic],
        *,
        dt_s: float,
    ) -> OpticalFlowResult:
        if not math.isfinite(dt_s) or dt_s <= 0:
            raise ValueError("dt_s must be finite and positive")
        previous = _grayscale(previous_frame)
        current = _grayscale(current_frame)
        if previous.shape != current.shape:
            raise ValueError("frame shape must match")
        config = self.config
        seed_flow = np.zeros((*previous.shape, 2), dtype=np.float32)
        flow = cv2.calcOpticalFlowFarneback(
            previous,
            current,
            seed_flow,
            config.pyramid_scale,
            config.levels,
            config.window_size,
            config.iterations,
            config.polynomial_neighborhood,
            config.polynomial_sigma,
            0,
        )
        velocity = np.asarray(flow / dt_s, dtype=np.float32)
        if not np.all(np.isfinite(velocity)):
            raise RuntimeError("optical flow produced non-finite values")
        return OpticalFlowResult(velocity_px_per_s=velocity)


def _grayscale(frame: NDArray[np.generic]) -> NDArray[np.uint8]:
    array = np.asarray(frame)
    if array.ndim == 3 and array.shape[2] in {3, 4}:
        conversion = cv2.COLOR_BGRA2GRAY if array.shape[2] == 4 else cv2.COLOR_BGR2GRAY
        array = cv2.cvtColor(array, conversion)
    if array.ndim != 2:
        raise ValueError("frame must be grayscale, BGR or BGRA")
    if not np.all(np.isfinite(array)):
        raise ValueError("frame must be finite")
    if array.dtype != np.uint8:
        array = np.clip(array, 0, 255).astype(np.uint8)
    return array


@dataclass(frozen=True, slots=True)
class DensityModelManifest:
    schema_version: int
    model_sha256: str
    input_name: str
    output_name: str
    input_shape: tuple[int, ...]
    layout: str
    input_scale: float
    input_mean: tuple[float, ...]
    input_std: tuple[float, ...]
    output_units: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported density model manifest schema")
        if not re_full_sha256(self.model_sha256):
            raise ValueError("model_sha256 must be a lowercase SHA-256 digest")
        if self.layout not in {"NCHW", "NHWC"}:
            raise ValueError("layout must be NCHW or NHWC")
        if not self.input_shape or any(value <= 0 for value in self.input_shape):
            raise ValueError("input_shape must contain positive dimensions")
        if not self.input_name or not self.output_name:
            raise ValueError("model input and output names are required")
        if not math.isfinite(self.input_scale) or self.input_scale == 0:
            raise ValueError("input_scale must be finite and nonzero")
        if any(not math.isfinite(value) or value == 0 for value in self.input_std):
            raise ValueError("input_std must be finite and nonzero")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, path: Path | str) -> DensityModelManifest:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        for key in ("input_shape", "input_mean", "input_std"):
            if key in document:
                document[key] = tuple(document[key])
        return cls(**document)


class _Session(Protocol):
    def get_inputs(self) -> list[Any]: ...

    def get_outputs(self) -> list[Any]: ...

    def run(self, output_names: list[str], feed: dict[str, NDArray[np.float32]]) -> list[Any]: ...


class OnnxDensityAdapter:
    def __init__(
        self,
        *,
        model_path: Path | str,
        manifest: DensityModelManifest,
        session: _Session | None = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.manifest = manifest
        if not self.model_path.is_file():
            raise FileNotFoundError(self.model_path)
        digest = hashlib.sha256(self.model_path.read_bytes()).hexdigest()
        if digest != manifest.model_sha256:
            raise ValueError("model SHA-256 does not match its manifest")
        self.session: _Session = session or ort.InferenceSession(
            str(self.model_path),
            providers=["CPUExecutionProvider"],
        )
        self._validate_session_contract()

    def _validate_session_contract(self) -> None:
        inputs = self.session.get_inputs()
        outputs = self.session.get_outputs()
        if len(inputs) != 1 or len(outputs) != 1:
            raise ValueError("density model must have exactly one input and output")
        if inputs[0].name != self.manifest.input_name:
            raise ValueError("density model input name does not match manifest")
        if outputs[0].name != self.manifest.output_name:
            raise ValueError("density model output name does not match manifest")
        shape = tuple(value for value in inputs[0].shape if isinstance(value, int))
        if len(shape) == len(self.manifest.input_shape) and shape != self.manifest.input_shape:
            raise ValueError("density model input shape does not match manifest")

    def predict(self, input_tensor: NDArray[np.floating]) -> NDArray[np.float32]:
        tensor = np.asarray(input_tensor, dtype=np.float32)
        if tensor.shape != self.manifest.input_shape:
            raise ValueError("density input shape does not match manifest")
        if not np.all(np.isfinite(tensor)):
            raise ValueError("density input must be finite")
        normalized = np.asarray(tensor * self.manifest.input_scale, dtype=np.float32)
        feed: dict[str, NDArray[np.float32]] = {self.manifest.input_name: normalized}
        output = np.asarray(
            self.session.run([self.manifest.output_name], feed)[0],
            dtype=np.float32,
        )
        if not np.all(np.isfinite(output)):
            raise ValueError("density output must be finite")
        if np.any(output < 0):
            raise ValueError("density output must be nonnegative")
        return output


def re_full_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


__all__ = [
    "CROWD_PRESSURE_INDEX_UNITS",
    "CrowdPressureIndex",
    "DensityModelManifest",
    "HomographyCalibration",
    "OnnxDensityAdapter",
    "OpticalFlowAdapter",
    "OpticalFlowConfig",
    "OpticalFlowResult",
    "calibrate_homography",
    "compute_crowd_pressure_index",
    "crowd_flux",
]
