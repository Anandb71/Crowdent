"""Minimal density-model contract, ONNX export and parity utilities.

The architecture is intentionally small and untrained. A field model must be
trained on approved data, independently validated, documented and signed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
import torch
from torch import nn


class TinyDensityModel(nn.Module):
    """Small fully-convolutional model used to prove the export pipeline."""

    def __init__(self, channels: int = 16) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Conv2d(1, channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv2d(channels, channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv2d(channels, 1, kernel_size=1),
            nn.Softplus(),
        )

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        return self.network(image)


def export_density_model(
    model: nn.Module,
    destination: Path | str,
    *,
    height: int,
    width: int,
    seed: int = 404,
) -> Path:
    if height <= 0 or width <= 0:
        raise ValueError("height and width must be positive")
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(seed)
    model = model.cpu().eval()
    example = torch.zeros((1, 1, height, width), dtype=torch.float32)
    torch.onnx.export(
        model,
        (example,),
        output,
        input_names=["image"],
        output_names=["density"],
        dynamic_axes=None,
        opset_version=18,
        do_constant_folding=True,
        dynamo=False,
    )
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 1,
        "model_sha256": digest,
        "input_name": "image",
        "output_name": "density",
        "input_shape": [1, 1, height, width],
        "layout": "NCHW",
        "input_scale": 1.0,
        "input_mean": [0.0],
        "input_std": [1.0],
        "output_units": "people_per_square_metre",
        "training_status": "UNTRAINED_EXPORT_PIPELINE_FIXTURE",
        "research_only": True,
    }
    output.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output.with_suffix(".model-card.md").write_text(_model_card(digest), encoding="utf-8")
    return output


def check_onnx_parity(
    model: nn.Module,
    onnx_path: Path | str,
    sample: np.ndarray,
    *,
    atol: float = 1e-5,
    rtol: float = 1e-4,
) -> dict[str, float | bool]:
    tensor = torch.from_numpy(np.asarray(sample, dtype=np.float32))
    with torch.inference_mode():
        torch_output = model.cpu().eval()(tensor).numpy()
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    onnx_output = np.asarray(session.run(["density"], {"image": sample})[0])
    difference = np.abs(torch_output - onnx_output)
    return {
        "passed": bool(np.allclose(torch_output, onnx_output, atol=atol, rtol=rtol)),
        "max_absolute_error": float(difference.max(initial=0.0)),
        "mean_absolute_error": float(difference.mean()),
    }


def quantize_density_model(source: Path | str, destination: Path | str) -> Path:
    """Quantize weights without introducing a runtime PyTorch dependency."""

    from onnxruntime.quantization import QuantType, quantize_dynamic

    source_path = Path(source)
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    quantize_dynamic(source_path, output, weight_type=QuantType.QInt8)
    return output


def _model_card(digest: str) -> str:
    return f"""# Density model card

Status: **UNTRAINED EXPORT PIPELINE FIXTURE — NOT FOR FIELD USE**

SHA-256: `{digest}`

This artifact only proves PyTorch → ONNX → ONNX Runtime parity. It has no
validated accuracy, calibration, operating domain or safety claim. Field use
requires approved training data, venue holdouts, calibration by density regime,
failure-case reporting, privacy review and an independently approved readiness
manifest.
"""


def manifest_for(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).with_suffix(".manifest.json").read_text(encoding="utf-8"))


__all__ = [
    "TinyDensityModel",
    "check_onnx_parity",
    "export_density_model",
    "manifest_for",
    "quantize_density_model",
]
