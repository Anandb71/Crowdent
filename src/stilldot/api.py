from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from stilldot.engine import run_live_samples, run_scenario
from stilldot.scenarios import list_scenarios
from stilldot.types import ImuSample, RunResult, ScenarioSpec, VehicleClass

app = FastAPI(title="StillDot", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:4173", "http://127.0.0.1:5173", "http://localhost:4173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class LiveRequest(BaseModel):
    samples: list[ImuSample] = Field(min_length=16)
    vehicle_class: VehicleClass = VehicleClass.PEDESTRIAN


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "ok": True,
        "name": "StillDot",
        "research_only": True,
        "offline": True,
        "hardware_actuation_available": False,
        "gnss_required": False,
    }


@app.get("/api/scenarios", response_model=list[ScenarioSpec])
def scenarios() -> list[ScenarioSpec]:
    return list_scenarios()


@app.get("/api/scenarios/{scenario_id}/run", response_model=RunResult)
def run(scenario_id: str, seed: int = 7) -> RunResult:
    try:
        return run_scenario(scenario_id, seed=seed)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/live", response_model=RunResult)
def live(body: LiveRequest) -> RunResult:
    try:
        return run_live_samples(body.samples, body.vehicle_class)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def mount_frontend(application: FastAPI) -> None:
    dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if dist.is_dir():
        application.mount("/", StaticFiles(directory=dist, html=True), name="spa")


mount_frontend(app)
