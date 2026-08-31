import ast
from pathlib import Path


def test_runtime_never_imports_torch() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "stilldot"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "torch" or alias.name.startswith("torch."):
                        offenders.append(str(path))
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("torch"):
                offenders.append(str(path))
    assert offenders == []
