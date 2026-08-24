"""FastAPI application exposing Crowdent's advisory research surface."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from crowdent.auth import Role, role_allows
from crowdent.contracts import InstructionLifecycle, ReadinessState, RuntimeMode
from crowdent.core import (
    AuthorizationDenied,
    InvalidLifecycleTransition,
    ResearchService,
)
from crowdent.runtime import RuntimeProfile, RuntimeSettings


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InterventionRequest(ApiModel):
    scenario_id: str = Field(min_length=1, max_length=128)
    action: str = Field(min_length=1, max_length=128)
    parameters: dict[str, str | int | float | bool] = {}


class InstructionRequest(ApiModel):
    scenario_id: str = Field(min_length=1, max_length=128)
    recommendation: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=2000)
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def _aware_expiry(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("expires_at must be timezone-aware")
        return value


class TransitionRequest(ApiModel):
    reason: str = Field(min_length=1, max_length=1000)


class Actor(BaseModel):
    actor_id: str
    role: Role


def create_app(
    *,
    settings: RuntimeSettings | None = None,
    engine: ResearchService | None = None,
    static_directory: Path | str | None = None,
) -> FastAPI:
    active_settings = settings or RuntimeSettings.for_profile(RuntimeProfile.DEMO)
    service = engine or ResearchService(settings=active_settings)
    docs_enabled = active_settings.network.docs_enabled
    app = FastAPI(
        title="Crowdent Research API",
        version="0.1.0",
        description=(
            "Offline crowd-risk research API. Human advisory only; "
            "not deployment certified; no hardware actuation."
        ),
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.state.settings = active_settings
    app.state.engine = service
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=list(active_settings.network.trusted_hosts),
    )
    if active_settings.network.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(active_settings.network.cors_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=[
                "Content-Type",
                "Authorization",
                "X-Crowdent-Actor",
                "X-Crowdent-Role",
            ],
        )

    @app.middleware("http")
    async def security_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self' ws: wss:; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

    def actor(
        x_crowdent_actor: str | None = Header(default=None),
        x_crowdent_role: str | None = Header(default=None),
    ) -> Actor:
        field_mode = active_settings.mode is RuntimeMode.FIELD_RESEARCH
        if not x_crowdent_actor or not x_crowdent_role:
            if field_mode:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="authenticated local session required",
                )
            return Actor(actor_id="demo-operator", role=Role.ADMIN)
        try:
            parsed_role = Role(x_crowdent_role.lower())
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid actor role",
            ) from error
        return Actor(actor_id=x_crowdent_actor, role=parsed_role)

    def require(required: Role) -> Callable[[Actor], Actor]:
        def dependency(principal: Actor = Depends(actor)) -> Actor:  # noqa: B008
            if not role_allows(principal.role, required):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"{required.value} role required",
                )
            return principal

        return dependency

    @app.get("/health/live")
    def health_live() -> dict[str, Any]:
        return {
            "status": "alive",
            "research_only": True,
            "deployment_certified": False,
            "hardware_actuation_available": False,
        }

    @app.get("/health/ready")
    def health_ready() -> JSONResponse:
        payload = service.status()
        is_ready = payload["readiness"] == ReadinessState.READY.value
        return JSONResponse(
            status_code=status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE,
            content=payload,
        )

    @app.get("/api/v1/status")
    def api_status() -> dict[str, Any]:
        return service.status()

    @app.get("/api/v1/forecasts/latest")
    def latest_forecast() -> dict[str, Any]:
        return service.safe_forecast_payload()

    @app.get("/api/v1/demo/snapshot")
    def demo_snapshot() -> dict[str, Any]:
        if active_settings.mode is not RuntimeMode.DEMO_DETERMINISTIC:
            raise HTTPException(status_code=404, detail="demo data is unavailable")
        from crowdent.demo import demo_snapshot as build_snapshot

        return build_snapshot()

    @app.post("/api/v1/interventions/evaluate")
    def evaluate_intervention(
        request: InterventionRequest,
        _: Actor = Depends(require(Role.OPERATOR)),  # noqa: B008
    ) -> dict[str, Any]:
        return service.evaluate_intervention(
            scenario_id=request.scenario_id,
            action=request.action,
            parameters=dict(request.parameters),
        )

    @app.post("/api/v1/instructions", status_code=status.HTTP_201_CREATED)
    def create_instruction(
        request: InstructionRequest,
        principal: Actor = Depends(require(Role.SUPERVISOR)),  # noqa: B008
    ) -> dict[str, Any]:
        try:
            instruction = service.create_instruction(
                scenario_id=request.scenario_id,
                recommendation=request.recommendation,
                text=request.text,
                expires_at=request.expires_at,
                actor_id=principal.actor_id,
                role=principal.role,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return instruction.model_dump(mode="json")

    def transition(
        instruction_id: str,
        target: InstructionLifecycle,
        request: TransitionRequest,
        principal: Actor,
    ) -> dict[str, Any]:
        try:
            instruction = service.transition_instruction(
                instruction_id=instruction_id,
                target=target,
                actor_id=principal.actor_id,
                role=principal.role,
                reason=request.reason,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except AuthorizationDenied as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except InvalidLifecycleTransition as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return instruction.model_dump(mode="json")

    @app.post("/api/v1/instructions/{instruction_id}/acknowledge")
    def acknowledge(
        instruction_id: str,
        request: TransitionRequest,
        principal: Actor = Depends(require(Role.OPERATOR)),  # noqa: B008
    ) -> dict[str, Any]:
        return transition(
            instruction_id,
            InstructionLifecycle.ACKNOWLEDGED,
            request,
            principal,
        )

    @app.post("/api/v1/instructions/{instruction_id}/accept")
    def accept(
        instruction_id: str,
        request: TransitionRequest,
        principal: Actor = Depends(require(Role.SUPERVISOR)),  # noqa: B008
    ) -> dict[str, Any]:
        return transition(
            instruction_id,
            InstructionLifecycle.ACCEPTED,
            request,
            principal,
        )

    @app.post("/api/v1/instructions/{instruction_id}/reject")
    def reject(
        instruction_id: str,
        request: TransitionRequest,
        principal: Actor = Depends(require(Role.SUPERVISOR)),  # noqa: B008
    ) -> dict[str, Any]:
        return transition(
            instruction_id,
            InstructionLifecycle.REJECTED,
            request,
            principal,
        )

    @app.post("/api/v1/instructions/{instruction_id}/physical-action-confirmed")
    def physical_action_confirmed(
        instruction_id: str,
        request: TransitionRequest,
        principal: Actor = Depends(require(Role.SUPERVISOR)),  # noqa: B008
    ) -> dict[str, Any]:
        return transition(
            instruction_id,
            InstructionLifecycle.PHYSICAL_ACTION_CONFIRMED,
            request,
            principal,
        )

    @app.get("/api/v1/audit")
    def audit(
        _: Actor = Depends(require(Role.SUPERVISOR)),  # noqa: B008
    ) -> dict[str, Any]:
        return {
            "records": list(service.list_audit()),
            "research_only": True,
            "hardware_actuation_available": False,
        }

    @app.websocket("/api/v1/ws/status")
    async def websocket_status(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_json(service.status())
        await websocket.close(code=1000)

    console_directory = Path(static_directory) if static_directory is not None else None
    if console_directory is not None and (console_directory / "index.html").is_file():
        app.mount(
            "/",
            StaticFiles(directory=console_directory, html=True, check_dir=True),
            name="operator-console",
        )

    return app


__all__ = ["create_app"]
