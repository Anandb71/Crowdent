from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from stilldot.engine import run_scenario
from stilldot.scenarios import list_scenarios

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


@app.command()
def doctor() -> None:
    """Confirm the demo engine is importable and scenarios exist."""
    names = [s.id for s in list_scenarios()]
    console.print("StillDot  ·  research demo  ·  not deployment-ready")
    console.print(f"scenarios: {', '.join(names)}")
    console.print("loopback only unless you pass --host yourself. do not bind LAN for a pitch.")


@app.command()
def scenarios() -> None:
    table = Table(title="StillDot scenarios")
    table.add_column("id")
    table.add_column("title")
    table.add_column("class")
    for spec in list_scenarios():
        table.add_row(spec.id, spec.title, spec.vehicle_class.value)
    console.print(table)


@app.command()
def run(
    scenario: Annotated[str, typer.Argument()] = "room_walk",
    json_out: bool = False,
) -> None:
    """Run one scenario and print the measured drift."""
    result = run_scenario(scenario)
    if json_out:
        console.print(result.model_dump_json())
        return
    m = result.metrics
    console.print(f"[bold]{result.scenario.title}[/bold]")
    console.print(f"distance  {m.distance_m:.1f} m   duration  {m.duration_s:.1f} s")
    console.print(f"drift     {m.drift_m:.2f} m   ({m.drift_pct:.2f} %)")
    console.print(f"naive     {m.naive_drift_m:.1f} m   ({m.naive_drift_pct:.1f} %)")
    console.print(f"bar       < {m.requirement_pct:.0f} %   met={m.requirement_met}   zupt={m.zupt_locked}")
    for line in result.scenario.honesty:
        console.print(f"  · {line}")


@app.command()
def demo(
    host: str = "127.0.0.1",
    port: int = 8000,
    no_browser: bool = False,
) -> None:
    """Serve the operator console on loopback."""
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise typer.BadParameter("refusing non-loopback bind. this demo stays on this machine.")
    if not no_browser:
        typer.launch(f"http://{host}:{port}")
    uvicorn.run("stilldot.api:app", host=host, port=port, log_level="info")


@app.command("export-json")
def export_json(
    scenario: str = "room_walk",
    out: Annotated[Path | None, typer.Option()] = None,
) -> None:
    result = run_scenario(scenario)
    payload = json.dumps(result.model_dump(), indent=2)
    if out is None:
        console.print(payload)
        return
    out.write_text(payload)
