from pathlib import Path


def test_runtime_package_does_not_import_torch() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "crowdent"
    offenders = [
        path.relative_to(root.parent.parent)
        for path in root.rglob("*.py")
        if "import torch" in path.read_text(encoding="utf-8")
        or "from torch" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_training_extra_is_isolated_from_runtime_package() -> None:
    training = Path(__file__).resolve().parents[2] / "training" / "density.py"
    assert "import torch" in training.read_text(encoding="utf-8")
