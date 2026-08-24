"""Application service coordinating advisory research workflows."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from threading import RLock
from typing import Any
from uuid import uuid4

from crowdent.auth import Role, role_allows
from crowdent.contracts import (
    Forecast,
    InstructionDraft,
    InstructionLifecycle,
    ReadinessState,
)
from crowdent.runtime import RuntimeSettings
from crowdent.safety import (
    ReadinessAssessment,
    RecommendationPolicy,
)


class InvalidLifecycleTransition(ValueError):
    pass


class AuthorizationDenied(PermissionError):
    pass


class ResearchService:
    """In-process domain service.

    It creates and records human advisories. It intentionally has no hardware
    client, actuator interface, or automatic execution path.
    """

    def __init__(
        self,
        *,
        settings: RuntimeSettings,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self._clock = clock or (lambda: datetime.now(UTC))
        self._latest_forecast: Forecast | None = None
        self._instructions: dict[str, InstructionDraft] = {}
        self._audit: list[dict[str, Any]] = []
        self._lock = RLock()
        self._policy = RecommendationPolicy(
            allowed_actions=frozenset(settings.safety.allowed_actions)
        )

    def set_latest_forecast(self, forecast: Forecast) -> None:
        with self._lock:
            self._latest_forecast = forecast

    @property
    def latest_forecast(self) -> Forecast | None:
        return self._latest_forecast

    def status(self) -> dict[str, Any]:
        forecast = self._latest_forecast
        readiness = forecast.readiness if forecast else ReadinessState.UNKNOWN
        return {
            "mode": self.settings.mode.value,
            "profile": self.settings.profile_name.value,
            "site_id": self.settings.site_id,
            "readiness": readiness.value,
            "research_only": True,
            "deployment_certified": False,
            "hardware_actuation_available": False,
            "config_hash": self.settings.config_hash,
            "timestamp": self._clock().isoformat(),
        }

    def safe_forecast_payload(self) -> dict[str, Any]:
        if self._latest_forecast is not None:
            return self._latest_forecast.model_dump(mode="json")
        return {
            "readiness": ReadinessState.UNKNOWN.value,
            "quality_flags": ["MISSING_INPUT"],
            "risk_probability": None,
            "risk_interval": None,
            "countdown_seconds": None,
            "advice": [],
            "research_only": True,
            "hardware_actuation_available": False,
        }

    def evaluate_intervention(
        self,
        *,
        scenario_id: str,
        action: str,
        parameters: dict[str, object],
    ) -> dict[str, Any]:
        forecast = self._latest_forecast
        if forecast is None:
            assessment = ReadinessAssessment(
                state=ReadinessState.UNKNOWN,
                quality_flags=(),
                reasons=("no forecast is available",),
            )
        else:
            assessment = ReadinessAssessment(
                state=forecast.readiness,
                quality_flags=forecast.quality_flags,
                reasons=(
                    ("forecast is ready")
                    if forecast.readiness is ReadinessState.READY
                    else ("forecast readiness suppresses intervention advice")
                ,),
            )
        decision = self._policy.evaluate(
            action=action,
            assessment=assessment,
            parameters=parameters,
        )
        return {
            "scenario_id": scenario_id,
            "action": action,
            "parameters": parameters,
            "permitted": decision.permitted,
            "recommendations": list(decision.recommendations),
            "countdown_seconds": decision.countdown_seconds,
            "reason_codes": list(decision.reason_codes),
            "hypothetical": True,
            "research_only": True,
            "hardware_actuation_available": False,
        }

    def create_instruction(
        self,
        *,
        scenario_id: str,
        recommendation: str,
        text: str,
        expires_at: datetime,
        actor_id: str,
        role: Role,
    ) -> InstructionDraft:
        self._require_role(role, Role.SUPERVISOR)
        now = self._clock()
        if expires_at.tzinfo is None or expires_at.utcoffset() is None:
            raise ValueError("expires_at must be timezone-aware")
        assessment = self.evaluate_intervention(
            scenario_id=scenario_id,
            action=recommendation,
            parameters={},
        )
        if not assessment["permitted"]:
            raise ValueError("recommendation is suppressed by readiness or policy")
        instruction = InstructionDraft(
            instruction_id=str(uuid4()),
            scenario_id=scenario_id,
            recommendation=recommendation,
            text=text,
            created_at=now,
            expires_at=expires_at,
            actor_id=actor_id,
        )
        with self._lock:
            self._instructions[instruction.instruction_id] = instruction
            self._append_audit(
                "instruction.created",
                actor_id,
                role,
                instruction.model_dump(mode="json"),
            )
        return instruction

    def transition_instruction(
        self,
        *,
        instruction_id: str,
        target: InstructionLifecycle,
        actor_id: str,
        role: Role,
        reason: str,
    ) -> InstructionDraft:
        with self._lock:
            try:
                current = self._instructions[instruction_id]
            except KeyError as error:
                raise KeyError("instruction not found") from error
            now = self._clock()
            if current.expires_at <= now and current.lifecycle not in {
                InstructionLifecycle.REJECTED,
                InstructionLifecycle.PHYSICAL_ACTION_CONFIRMED,
            }:
                current = current.model_copy(
                    update={"lifecycle": InstructionLifecycle.EXPIRED, "reason": "expired"}
                )
                self._instructions[instruction_id] = current
                raise InvalidLifecycleTransition("instruction has expired")
            self._authorize_transition(target, role)
            allowed = {
                InstructionLifecycle.DRAFT: {
                    InstructionLifecycle.ACKNOWLEDGED,
                    InstructionLifecycle.REJECTED,
                },
                InstructionLifecycle.ACKNOWLEDGED: {
                    InstructionLifecycle.ACCEPTED,
                    InstructionLifecycle.REJECTED,
                },
                InstructionLifecycle.ACCEPTED: {
                    InstructionLifecycle.PHYSICAL_ACTION_CONFIRMED,
                },
            }
            if target not in allowed.get(current.lifecycle, set()):
                raise InvalidLifecycleTransition(
                    f"cannot transition {current.lifecycle.value} to {target.value}"
                )
            updated = current.model_copy(update={"lifecycle": target, "reason": reason})
            self._instructions[instruction_id] = updated
            self._append_audit(
                f"instruction.{target.value}",
                actor_id,
                role,
                {
                    "instruction_id": instruction_id,
                    "previous_lifecycle": current.lifecycle.value,
                    "lifecycle": target.value,
                    "reason": reason,
                    "hardware_actuation_available": False,
                },
            )
            return updated

    def get_instruction(self, instruction_id: str) -> InstructionDraft:
        try:
            return self._instructions[instruction_id]
        except KeyError as error:
            raise KeyError("instruction not found") from error

    def list_audit(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._audit)

    def _append_audit(
        self,
        event_type: str,
        actor_id: str,
        role: Role,
        payload: dict[str, Any],
    ) -> None:
        self._audit.append(
            {
                "sequence": len(self._audit) + 1,
                "timestamp": self._clock().isoformat(),
                "event_type": event_type,
                "actor_id": actor_id,
                "actor_role": role.value,
                "payload": payload,
                "research_only": True,
            }
        )

    @staticmethod
    def _require_role(actual: Role, required: Role) -> None:
        if not role_allows(actual, required):
            raise AuthorizationDenied(f"{required.value} role is required")

    def _authorize_transition(self, target: InstructionLifecycle, role: Role) -> None:
        required = (
            Role.OPERATOR
            if target is InstructionLifecycle.ACKNOWLEDGED
            else Role.SUPERVISOR
        )
        self._require_role(role, required)


__all__ = [
    "AuthorizationDenied",
    "InvalidLifecycleTransition",
    "ResearchService",
]
