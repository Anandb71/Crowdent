from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest


def test_untrained_export_pipeline_writes_research_only_manifest(tmp_path: Path) -> None:
    pytest.importorskip("torch")
    from training.density import TinyDensityModel, check_onnx_parity, export_density_model

    model = TinyDensityModel(channels=4)
    onnx_path = export_density_model(model, tmp_path / "density.onnx", height=8, width=8)
    manifest = (tmp_path / "density.manifest.json").read_text(encoding="utf-8")
    sample = np.zeros((1, 1, 8, 8), dtype=np.float32)

    parity = check_onnx_parity(model, onnx_path, sample)

    assert onnx_path.is_file()
    assert "UNTRAINED_EXPORT_PIPELINE_FIXTURE" in manifest
    assert "research_only" in manifest
    assert parity["passed"] is True
