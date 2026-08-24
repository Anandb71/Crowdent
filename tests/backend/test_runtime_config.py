from pathlib import Path

import pytest
from pydantic import ValidationError

from crowdent.contracts import RuntimeMode
from crowdent.runtime import RuntimeProfile, RuntimeSettings, load_runtime_settings


def test_field_profile_does_not_inherit_demo_values(tmp_path: Path) -> None:
    config_path = tmp_path / "crowdent.yaml"
    config_path.write_text(
        """
profiles:
  demo:
    mode: DEMO_DETERMINISTIC
    network:
      port: 9999
      cors_origins:
        - http://localhost:5173
  field:
    mode: FIELD_RESEARCH
""".strip(),
        encoding="utf-8",
    )

    settings = load_runtime_settings(config_path, RuntimeProfile.FIELD)

    assert settings.mode is RuntimeMode.FIELD_RESEARCH
    assert settings.network.port == 8000
    assert settings.network.cors_origins == ()
    assert settings.network.docs_enabled is False
    assert settings.storage.raw_video_enabled is False
    assert len(settings.config_hash) == 64


def test_runtime_settings_are_frozen() -> None:
    settings = RuntimeSettings.for_profile(RuntimeProfile.DEMO)
    with pytest.raises(ValidationError):
        settings.network.port = 9000


def test_non_loopback_binding_requires_explicit_lan_opt_in(tmp_path: Path) -> None:
    config_path = tmp_path / "unsafe.yaml"
    config_path.write_text(
        """
profiles:
  field:
    mode: FIELD_RESEARCH
    network:
      host: 0.0.0.0
      allow_lan: false
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="allow_lan"):
        load_runtime_settings(config_path, "field")
