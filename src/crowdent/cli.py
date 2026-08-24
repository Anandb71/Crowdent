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
from crowdent.datasets import (
    Dataset,
    DatasetAccess,
    DatasetTask,
    acquisition_plan,
    all_datasets,
    build_manifest,
    find_datasets,
    get_dataset,
    read_manifest,
    verify_manifest,
    write_manifest,
)
from crowdent.demo import build_demo_service
from crowdent.runtime import RuntimeProfile, RuntimeSettings, load_runtime_settings

app = typer.Typer(
    name="crowdent",
    help="Offline crowd-risk forecasting research platform.",
    no_args_is_help=True,
)
dataset_app = typer.Typer(
    name="dataset",
    help="Browse the public dataset registry and verify local copies. Never downloads.",
    no_args_is_help=True,
)
app.add_typer(dataset_app, name="dataset")


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


@dataset_app.command("list")
def dataset_list(
    task: Annotated[DatasetTask | None, typer.Option(help="Filter by annotation type.")] = None,
    access: Annotated[
        DatasetAccess | None,
        typer.Option(help="Filter by how a copy is obtained."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """List registered public datasets. This command contacts no network."""

    datasets = find_datasets(task=task, access=access)
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "research_only": True,
                    "downloads_performed": False,
                    "datasets": [
                        {
                            "identifier": item.identifier,
                            "name": item.name,
                            "year": item.year,
                            "task": item.task.value,
                            "access": item.access.value,
                            "license": item.license,
                            "homepage": item.homepage,
                            "samples": item.samples,
                            "annotations": item.annotations,
                            "size_band": item.size_band.value,
                            "needs_human_acceptance": item.needs_human_acceptance,
                            "terms_reviewed": item.terms_reviewed.isoformat(),
                        }
                        for item in datasets
                    ],
                },
                indent=2,
            )
        )
        return
    if not datasets:
        typer.echo("No dataset matches that filter.")
        return
    for item in datasets:
        flag = "human acceptance required" if item.needs_human_acceptance else "open licence"
        typer.echo(f"{item.identifier:<22} {item.task.value:<14} {item.size_band.value:<11} {flag}")
        typer.echo(f"{'':<22} {item.name}")
    typer.echo("")
    typer.echo(f"{len(datasets)} of {len(all_datasets())} datasets. Nothing was downloaded.")


@dataset_app.command("show")
def dataset_show(
    identifier: Annotated[str, typer.Argument(help="Registry identifier.")],
) -> None:
    """Print acquisition steps and caveats for one dataset."""

    try:
        dataset = get_dataset(identifier)
    except KeyError as error:
        raise typer.BadParameter(str(error).strip("'")) from error
    typer.echo(acquisition_plan(dataset, destination=f"data/{dataset.identifier}"))
    typer.echo("")
    typer.echo(f"Crowdent would use it for: {dataset.crowdent_use}")


@dataset_app.command("manifest")
def dataset_manifest(
    identifier: Annotated[str, typer.Argument(help="Registry identifier.")],
    path: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    output: Annotated[Path | None, typer.Option(help="Write JSON here.")] = None,
) -> None:
    """Hash a local dataset copy so a later run can prove it scored the same bytes."""

    dataset = _known_dataset(identifier)
    manifest = build_manifest(path, dataset=dataset.identifier)
    destination = output or path.parent / f"{dataset.identifier}.manifest.json"
    write_manifest(manifest, destination)
    typer.echo(
        f"Hashed {len(manifest.files)} files ({manifest.total_bytes} bytes) -> {destination}"
    )


@dataset_app.command("verify")
def dataset_verify(
    identifier: Annotated[str, typer.Argument(help="Registry identifier.")],
    path: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    manifest: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Re-hash a local copy and report drift from its manifest."""

    dataset = _known_dataset(identifier)
    recorded = read_manifest(manifest)
    if recorded.dataset != dataset.identifier:
        raise typer.BadParameter(
            f"manifest is for {recorded.dataset!r}, not {dataset.identifier!r}"
        )
    result = verify_manifest(path, recorded)
    if json_output:
        typer.echo(json.dumps(result.to_dict(), indent=2))
    else:
        typer.echo(f"{'PASS' if result.ok else 'FAIL'} {result.dataset}")
        typer.echo(f"  matched    {result.matched}")
        typer.echo(f"  missing    {len(result.missing)}")
        typer.echo(f"  changed    {len(result.changed)}")
        typer.echo(f"  unexpected {len(result.unexpected)}")
    if not result.ok:
        raise typer.Exit(code=1)


def _known_dataset(identifier: str) -> Dataset:
    try:
        return get_dataset(identifier)
    except KeyError as error:
        raise typer.BadParameter(str(error).strip("'")) from error


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
