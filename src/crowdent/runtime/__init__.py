"""Immutable runtime profiles and configuration loading."""

from __future__ import annotations

import hashlib
import ipaddress
import json
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from crowdent.contracts import RuntimeMode


class RuntimeProfile(StrEnum):
    DEMO = "demo"
    REPLAY = "replay"
    FIELD = "field"


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)


class NetworkSettings(FrozenModel):
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    allow_lan: bool = False
    cors_origins: tuple[str, ...] = ()
    docs_enabled: bool = True
    trusted_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "testserver")

    @model_validator(mode="after")
    def _validate_binding(self) -> Self:
        try:
            address = ipaddress.ip_address(self.host)
            loopback = address.is_loopback
        except ValueError:
            loopback = self.host.lower() == "localhost"
        if not loopback and not self.allow_lan:
            raise ValueError("non-loopback host requires explicit allow_lan=true")
        if self.allow_lan and "*" in self.trusted_hosts:
            raise ValueError("allow_lan cannot use a wildcard trusted host")
        return self


class StorageSettings(FrozenModel):
    root: Path = Path(".crowdent")
    database_name: str = "crowdent.db"
    raw_video_enabled: bool = False
    raw_video_retention_hours: int = Field(default=0, ge=0)
    chunk_retention_days: int = Field(default=7, ge=1)

    @model_validator(mode="after")
    def _raw_video_retention_requires_opt_in(self) -> Self:
        if not self.raw_video_enabled and self.raw_video_retention_hours:
            raise ValueError("raw-video retention requires raw_video_enabled=true")
        return self


class SafetySettings(FrozenModel):
    allowed_actions: tuple[str, ...] = ("PAUSE_INFLOW", "METER_INFLOW", "HOLD_ARRIVAL")
    require_signed_readiness_manifest: bool = True
    stale_after_seconds: float = Field(default=10.0, gt=0)
    instruction_ttl_seconds: int = Field(default=300, gt=0)


class RuntimeSettings(FrozenModel):
    mode: RuntimeMode
    network: NetworkSettings
    storage: StorageSettings
    safety: SafetySettings
    config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    profile_name: RuntimeProfile
    site_id: str = "unconfigured"

    @classmethod
    def for_profile(cls, profile: RuntimeProfile | str) -> RuntimeSettings:
        selected = RuntimeProfile(profile)
        raw = _profile_defaults(selected)
        return cls._from_unhashed(selected, raw)

    @classmethod
    def _from_unhashed(
        cls,
        profile: RuntimeProfile,
        raw: dict[str, Any],
    ) -> RuntimeSettings:
        canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"), default=str)
        config_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return cls(
            mode=RuntimeMode(raw["mode"]),
            network=NetworkSettings.model_validate(raw["network"]),
            storage=StorageSettings.model_validate(raw["storage"]),
            safety=SafetySettings.model_validate(raw["safety"]),
            config_hash=config_hash,
            profile_name=profile,
            site_id=str(raw.get("site_id", "unconfigured")),
        )


def _profile_defaults(profile: RuntimeProfile) -> dict[str, Any]:
    network: dict[str, Any] = {
        "host": "127.0.0.1",
        "port": 8000,
        "allow_lan": False,
        "cors_origins": (),
        "docs_enabled": profile is not RuntimeProfile.FIELD,
        "trusted_hosts": ("127.0.0.1", "localhost", "testserver"),
    }
    if profile is RuntimeProfile.DEMO:
        network["cors_origins"] = ("http://localhost:5173",)
    return {
        "mode": {
            RuntimeProfile.DEMO: RuntimeMode.DEMO_DETERMINISTIC,
            RuntimeProfile.REPLAY: RuntimeMode.REPLAY_RESEARCH,
            RuntimeProfile.FIELD: RuntimeMode.FIELD_RESEARCH,
        }[profile],
        "network": network,
        "storage": {
            "root": ".crowdent",
            "database_name": "crowdent.db",
            "raw_video_enabled": False,
            "raw_video_retention_hours": 0,
            "chunk_retention_days": 7,
        },
        "safety": {
            "allowed_actions": ("PAUSE_INFLOW", "METER_INFLOW", "HOLD_ARRIVAL"),
            "require_signed_readiness_manifest": True,
            "stale_after_seconds": 10.0,
            "instruction_ttl_seconds": 300,
        },
        "site_id": "demo-venue" if profile is RuntimeProfile.DEMO else "unconfigured",
    }


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_runtime_settings(
    path: Path | str,
    profile: RuntimeProfile | str,
) -> RuntimeSettings:
    """Load only the selected profile over its own safe defaults.

    A field profile can never inherit permissive demo settings.
    """

    selected = RuntimeProfile(profile)
    config_path = Path(path)
    document = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(document, dict):
        raise ValueError("runtime configuration root must be a mapping")
    profiles = document.get("profiles", {})
    if not isinstance(profiles, dict):
        raise ValueError("profiles must be a mapping")
    override = profiles.get(selected.value, {})
    if not isinstance(override, dict):
        raise ValueError(f"profile {selected.value!r} must be a mapping")
    merged = _deep_merge(_profile_defaults(selected), override)
    return RuntimeSettings._from_unhashed(selected, merged)


__all__ = [
    "NetworkSettings",
    "RuntimeProfile",
    "RuntimeSettings",
    "SafetySettings",
    "StorageSettings",
    "load_runtime_settings",
]
