"""Deterministic, clearly labelled demo fixtures."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

from crowdent.contracts import (
    Forecast,
    Provenance,
    ReadinessState,
)
from crowdent.core import ResearchService
from crowdent.runtime import RuntimeProfile, RuntimeSettings


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_demo_service(*, now: datetime | None = None) -> ResearchService:
    base = now or datetime.now(UTC).replace(microsecond=0)
    settings = RuntimeSettings.for_profile(RuntimeProfile.DEMO)
    service = ResearchService(settings=settings, clock=lambda: base)
    provenance = Provenance(
        source_id="demo-fusion",
        observed_at=base,
        sequence=120,
        content_hash=_digest("crowdent-demo-observations-v1"),
        transformations=("seeded-synthetic-scenario", "localized-ensemble-fusion"),
    )
    service.set_latest_forecast(
        Forecast(
            timestamp=base,
            target_timestamp=base + timedelta(minutes=30),
            horizon_seconds=1800,
            source_id="demo-forecast-engine",
            run_id="demo-run-v1",
            site_id="demo-venue",
            sequence=121,
            config_hash=settings.config_hash,
            model_hash=_digest("demo-density-model-v1"),
            calibration_hash=_digest("demo-calibration-v1"),
            risk_probability=0.72,
            risk_interval=(0.61, 0.82),
            covariance=((0.025,),),
            readiness=ReadinessState.READY,
            countdown_seconds=780,
            advice=("METER_INFLOW",),
            units={
                "risk_probability": "1",
                "density": "people/m^2",
                "speed": "m/s",
                "crowd_pressure_index": "s^-2",
            },
            coordinate_frame="demo-ground-grid",
            provenance=(provenance,),
        )
    )
    return service


def demo_snapshot() -> dict[str, Any]:
    """Return deterministic UI data; every value is synthetic."""

    horizons = (0, 5, 10, 15, 30, 45, 60)
    baseline = (0.22, 0.31, 0.44, 0.58, 0.72, 0.84, 0.9)
    intervention = (0.22, 0.27, 0.31, 0.34, 0.29, 0.2, 0.14)
    return {
        "schema_version": 1,
        "mode": "DEMO_DETERMINISTIC",
        "research_only": True,
        "synthetic": True,
        "hardware_actuation_available": False,
        "venue": {
            "name": "Synthetic Transit Concourse",
            "zones": [
                {
                    "id": "platform",
                    "label": "Platform",
                    "risk_probability": 0.72,
                    "density_people_per_m2": 3.8,
                    "crowd_pressure_index_s2": 0.017,
                    "readiness": "READY",
                },
                {
                    "id": "footbridge",
                    "label": "Footbridge",
                    "risk_probability": 0.48,
                    "density_people_per_m2": 2.9,
                    "crowd_pressure_index_s2": 0.011,
                    "readiness": "READY",
                },
                {
                    "id": "forecourt",
                    "label": "Forecourt",
                    "risk_probability": 0.19,
                    "density_people_per_m2": 1.4,
                    "crowd_pressure_index_s2": 0.004,
                    "readiness": "READY",
                },
            ],
        },
        "sensor_health": [
            {"id": "camera-north", "kind": "CCTV", "age_s": 0.4, "state": "HEALTHY"},
            {"id": "gate-counter-a", "kind": "COUNTER", "age_s": 0.1, "state": "HEALTHY"},
            {"id": "schedule-feed", "kind": "SCHEDULE", "age_s": 2.0, "state": "HEALTHY"},
            {
                "id": "passive-count-west",
                "kind": "AGGREGATE",
                "age_s": 4.2,
                "state": "DEGRADED",
            },
        ],
        "forecast": [
            {
                "minutes": minute,
                "baseline": baseline[index],
                "intervention": intervention[index],
                "p10": max(0.0, baseline[index] - 0.11),
                "p90": min(1.0, baseline[index] + 0.1),
            }
            for index, minute in enumerate(horizons)
        ],
        "recommendation": {
            "action": "METER_INFLOW",
            "inflow_people_per_s": 1.8,
            "gate_equivalent": 2,
            "expires_in_s": 300,
            "reason_codes": ["PLATFORM_FORECAST_RISING", "ADJACENT_ZONE_CAPACITY_OK"],
            "assumptions": [
                "Synthetic schedule remains unchanged",
                "Gate A discharge capacity is 1.2 people/(m·s)",
            ],
            "hypothetical": True,
        },
    }


__all__ = ["build_demo_service", "demo_snapshot"]
