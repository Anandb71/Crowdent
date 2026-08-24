"""Verification must stay off the advisory path, structurally and not just by convention."""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2] / "src" / "crowdent" / "verification"

_FORBIDDEN_IMPORTS = (
    "crowdent.safety",
    "crowdent.core",
    "crowdent.api",
    "crowdent.contracts",
    "crowdent.runtime",
    "crowdent.auth",
    "torch",
)


def _sources() -> list[Path]:
    return sorted(_ROOT.rglob("*.py"))


def test_the_package_has_sources_to_check() -> None:
    assert _sources()


@pytest.mark.parametrize("module", _FORBIDDEN_IMPORTS)
def test_verification_does_not_import_the_advisory_stack(module: str) -> None:
    """Scoring may never reach into readiness, advice, or the countdown."""

    offenders = [
        path.name
        for path in _sources()
        if f"import {module}" in path.read_text(encoding="utf-8")
        or f"from {module}" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_verification_defines_no_actuation_surface() -> None:
    forbidden = ("actuate", "gate_open", "signage", "public_address", "plc")
    offenders = [
        f"{path.name}: {token}"
        for path in _sources()
        for token in forbidden
        if token in path.read_text(encoding="utf-8").lower()
    ]
    assert offenders == []
