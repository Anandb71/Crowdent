"""Optional PyTorch training and ONNX export tooling.

This package is never imported by the Crowdent runtime.
"""

from training.density import (
    TinyDensityModel,
    check_onnx_parity,
    export_density_model,
    quantize_density_model,
)

__all__ = [
    "TinyDensityModel",
    "check_onnx_parity",
    "export_density_model",
    "quantize_density_model",
]
