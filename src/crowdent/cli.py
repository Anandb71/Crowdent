"""Crowdent command-line entry point."""

from __future__ import annotations

import json
import platform
import sys
import webbrowser
import zipfile
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from crowdent.api import create_app
from crowdent.core import ResearchService
from crowdent.demo import build_demo_service
from crowdent.runtime import RuntimeProfile, RuntimeSettings, load_runtime_settings

app = typer.Typer(
    name="crowdent",
    help="Offline crowd-risk forecasting research platform.",
    no_args_is_help=True,
)


@app.command()
def demo(
    host: Annotated[str, typer.Option(help="Loopback interface to bind.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(min=1, max=65535)] = 8000,
    browser: Annotated[
        bool,
        typer.Option("--browser/--no-browser", help="Open the local console."),
    ] = True,
) -> None:
    """Run the deterministic synthetic demo."""

    settings = RuntimeSettings.for_profile(RuntimeProfile.DEMO)
    service = build_demo_service()
    typer.echo("RESEARCH ONLY — NOT DEPLOYMENT CERTIFIED")
    typer.echo(f"Deterministic demo API: http://{host}:{port}")
    if browser:
        webbrowser.open(f"http://{host}:{port}")
    uvicorn.run(
        create_app(settings=settings, engine=service, static_directory=_frontend_dist()),
        host=host,
        port=port,
    )


@app.command()
def replay(
    bundle: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    verify_only: Annotated[
        bool,
        typer.Option("--verify-only/--serve", help="Verify without starting the API."),
    ] = True,
    port: Annotated[int, typer.Option(min=1, max=65535)] = 8000,
) -> None:
    """Verify an immutable replay bundle, optionally serving research replay mode."""

    _verify_bundle(bundle)
    typer.echo(f"Verified replay bundle: {bundle}")
    if verify_only:
        return
    settings = RuntimeSettings.for_profile(RuntimeProfile.REPLAY)
    service = ResearchService(settings=settings)
    uvicorn.run(
        create_app(settings=settings, engine=service),
        host=settings.network.host,
        port=port,
    )


@app.command()
def serve(
    config: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    profile: Annotated[RuntimeProfile, typer.Option()] = RuntimeProfile.FIELD,
) -> None:
    """Serve a validated replay or field-research profile."""

    settings = load_runtime_settings(config, profile)
    typer.echo("RESEARCH ONLY — NOT DEPLOYMENT CERTIFIED")
    typer.echo(f"Mode: {settings.mode.value}; site: {settings.site_id}")
    service = ResearchService(settings=settings)
    uvicorn.run(
        create_app(settings=settings, engine=service),
        host=settings.network.host,
        port=settings.network.port,
    )


@app.command()
def doctor(
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Check the local offline runtime without contacting the network."""

    checks = {
        "python": {
            "ok": sys.version_info >= (3, 13),
            "value": platform.python_version(),
        },
        "runtime_imports": {"ok": _runtime_imports_available(), "value": "local"},
        "frontend_bundle": {
            "ok": (Path.cwd() / "frontend" / "dist" / "index.html").exists(),
            "value": str(Path.cwd() / "frontend" / "dist"),
        },
        "loopback_default": {
            "ok": RuntimeSettings.for_profile(RuntimeProfile.FIELD).network.host
            == "127.0.0.1",
            "value": "127.0.0.1",
        },
        "hardware_actuation": {"ok": True, "value": "not implemented"},
    }
    overall = all(item["ok"] for key, item in checks.items() if key != "frontend_bundle")
    output = {
        "ok": overall,
        "research_only": True,
        "deployment_certified": False,
        "checks": checks,
    }
    if json_output:
        typer.echo(json.dumps(output, indent=2))
    else:
        for name, result in checks.items():
            typer.echo(f"{'PASS' if result['ok'] else 'WARN'} {name}: {result['value']}")
    if not overall:
        raise typer.Exit(code=1)


def _runtime_imports_available() -> bool:
    try:
        import cv2  # noqa: F401
        import numba  # noqa: F401
        import numpy  # noqa: F401
        import onnxruntime  # noqa: F401
    except ImportError:
        return False
    return True


def _frontend_dist() -> Path | None:
    candidate = Path.cwd() / "frontend" / "dist"
    return candidate if (candidate / "index.html").is_file() else None


def _verify_bundle(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        required = {"database/crowdent.db", "chunks/manifest.json", "bundle.json"}
        missing = required - names
        if missing:
            raise typer.BadParameter(f"bundle is missing: {', '.join(sorted(missing))}")
        bundle = json.loads(archive.read("bundle.json"))
        if bundle.get("research_only") is not True:
            raise typer.BadParameter("bundle lacks the research-only safety claim")
        import hashlib

        for entry in bundle.get("files", []):
            member = str(entry["path"])
            if member not in names:
                raise typer.BadParameter(f"bundle member missing: {member}")
            digest = hashlib.sha256(archive.read(member)).hexdigest()
            if digest != entry["sha256"]:
                raise typer.BadParameter(f"bundle hash mismatch: {member}")


if __name__ == "__main__":
    app()
