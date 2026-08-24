from __future__ import annotations

import hashlib
import json

import cv2
import numpy as np
import pytest

from crowdent.perception import (
    DensityModelManifest,
    OnnxDensityAdapter,
    OpticalFlowAdapter,
    OpticalFlowConfig,
)


class _FakeInput:
    name = "image"
    shape = [1, 1, 8, 8]
    type = "tensor(float)"


class _FakeOutput:
    name = "density"
    shape = [1, 1, 8, 8]
    type = "tensor(float)"


class _FakeSession:
    def get_inputs(self) -> list[_FakeInput]:
        return [_FakeInput()]

    def get_outputs(self) -> list[_FakeOutput]:
        return [_FakeOutput()]

    def run(self, output_names: list[str], feed: dict[str, np.ndarray]) -> list[np.ndarray]:
        assert output_names == ["density"]
        image = feed["image"]
        return [image * 2.0]


def test_optical_flow_recovers_synthetic_translation() -> None:
    rng = np.random.default_rng(7)
    previous = (rng.random((64, 64)) * 255).astype(np.uint8)
    transform = np.float32([[1.0, 0.0, 2.0], [0.0, 1.0, -1.0]])
    current = cv2.warpAffine(
        previous,
        transform,
        (64, 64),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT,
    )
    adapter = OpticalFlowAdapter(
        OpticalFlowConfig(
            pyramid_scale=0.5,
            levels=4,
            window_size=21,
            iterations=5,
            polynomial_neighborhood=7,
            polynomial_sigma=1.5,
        )
    )

    result = adapter.estimate(previous, current, dt_s=0.5)
    centre = result.velocity_px_per_s[12:-12, 12:-12]

    np.testing.assert_allclose(np.median(centre, axis=(0, 1)), np.array([4.0, -2.0]), atol=0.6)
    assert result.velocity_px_per_s.shape == (64, 64, 2)
    assert result.units == "pixels_per_second"


def test_optical_flow_rejects_invalid_frames_and_time() -> None:
    adapter = OpticalFlowAdapter()
    frame = np.zeros((8, 8), dtype=np.uint8)
    with pytest.raises(ValueError, match="dt_s"):
        adapter.estimate(frame, frame, dt_s=0.0)
    with pytest.raises(ValueError, match="shape"):
        adapter.estimate(frame, np.zeros((9, 8), dtype=np.uint8), dt_s=1.0)


def _manifest(model_hash: str) -> DensityModelManifest:
    return DensityModelManifest(
        schema_version=1,
        model_sha256=model_hash,
        input_name="image",
        output_name="density",
        input_shape=(1, 1, 8, 8),
        layout="NCHW",
        input_scale=1.0,
        input_mean=(0.0,),
        input_std=(1.0,),
        output_units="people_per_square_metre",
    )


def test_density_manifest_hash_and_session_contract_are_validated(tmp_path) -> None:
    model = tmp_path / "density.onnx"
    model.write_bytes(b"deterministic-placeholder")
    digest = hashlib.sha256(model.read_bytes()).hexdigest()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest(digest).to_dict()), encoding="utf-8")

    adapter = OnnxDensityAdapter(
        model_path=model,
        manifest=DensityModelManifest.from_json(manifest_path),
        session=_FakeSession(),
    )
    output = adapter.predict(np.ones((1, 1, 8, 8), dtype=np.float32))

    np.testing.assert_array_equal(output, np.full((1, 1, 8, 8), 2.0, dtype=np.float32))

    with pytest.raises(ValueError, match="shape"):
        adapter.predict(np.ones((1, 1, 7, 8), dtype=np.float32))
    with pytest.raises(ValueError, match="finite"):
        invalid = np.ones((1, 1, 8, 8), dtype=np.float32)
        invalid[0, 0, 0, 0] = np.nan
        adapter.predict(invalid)


def test_density_adapter_rejects_hash_mismatch_before_loading_runtime(tmp_path) -> None:
    model = tmp_path / "density.onnx"
    model.write_bytes(b"bytes")

    with pytest.raises(ValueError, match="SHA-256"):
        OnnxDensityAdapter(
            model_path=model,
            manifest=_manifest("0" * 64),
            session=_FakeSession(),
        )


def test_density_adapter_rejects_negative_model_output(tmp_path) -> None:
    class NegativeSession(_FakeSession):
        def run(
            self,
            output_names: list[str],
            feed: dict[str, np.ndarray],
        ) -> list[np.ndarray]:
            return [-np.ones((1, 1, 8, 8), dtype=np.float32)]

    model = tmp_path / "density.onnx"
    model.write_bytes(b"bytes")
    digest = hashlib.sha256(model.read_bytes()).hexdigest()
    adapter = OnnxDensityAdapter(
        model_path=model,
        manifest=_manifest(digest),
        session=NegativeSession(),
    )

    with pytest.raises(ValueError, match="nonnegative"):
        adapter.predict(np.ones((1, 1, 8, 8), dtype=np.float32))
