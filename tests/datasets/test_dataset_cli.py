"""The dataset CLI must stay a reference desk, never a download client."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from crowdent.cli import app

runner = CliRunner()


def test_list_reports_that_nothing_was_downloaded() -> None:
    result = runner.invoke(app, ["dataset", "list", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["research_only"] is True
    assert payload["downloads_performed"] is False
    assert len(payload["datasets"]) >= 10


def test_list_filters_by_access() -> None:
    result = runner.invoke(app, ["dataset", "list", "--access", "open", "--json"])

    assert result.exit_code == 0
    datasets = json.loads(result.stdout)["datasets"]
    assert datasets
    assert all(item["access"] == "open" for item in datasets)
    assert all(item["needs_human_acceptance"] is False for item in datasets)


def test_list_filters_by_task() -> None:
    result = runner.invoke(app, ["dataset", "list", "--task", "trajectory", "--json"])

    assert result.exit_code == 0
    datasets = json.loads(result.stdout)["datasets"]
    assert datasets
    assert all(item["task"] == "trajectory" for item in datasets)


def test_show_prints_the_terms_and_refuses_to_act_for_the_operator() -> None:
    result = runner.invoke(app, ["dataset", "show", "nwpu-crowd"])

    assert result.exit_code == 0
    assert "read the current terms yourself" in result.stdout
    assert "will not submit forms or accept terms on your behalf" in result.stdout


def test_show_rejects_an_unknown_identifier() -> None:
    result = runner.invoke(app, ["dataset", "show", "not-a-dataset"])

    assert result.exit_code != 0


def test_manifest_then_verify_round_trip(tmp_path: Path) -> None:
    copy = tmp_path / "shanghaitech-a"
    copy.mkdir()
    (copy / "part_A.txt").write_text("images", encoding="utf-8")
    destination = tmp_path / "manifest.json"

    built = runner.invoke(
        app,
        ["dataset", "manifest", "shanghaitech-a", "--path", str(copy),
         "--output", str(destination)],
    )
    assert built.exit_code == 0
    assert destination.is_file()

    verified = runner.invoke(
        app,
        ["dataset", "verify", "shanghaitech-a", "--path", str(copy),
         "--manifest", str(destination), "--json"],
    )
    assert verified.exit_code == 0
    assert json.loads(verified.stdout)["ok"] is True


def test_verify_exits_nonzero_when_the_copy_drifted(tmp_path: Path) -> None:
    copy = tmp_path / "shanghaitech-a"
    copy.mkdir()
    (copy / "part_A.txt").write_text("images", encoding="utf-8")
    destination = tmp_path / "manifest.json"
    runner.invoke(
        app,
        ["dataset", "manifest", "shanghaitech-a", "--path", str(copy),
         "--output", str(destination)],
    )
    (copy / "part_A.txt").write_text("edited", encoding="utf-8")

    result = runner.invoke(
        app,
        ["dataset", "verify", "shanghaitech-a", "--path", str(copy),
         "--manifest", str(destination)],
    )
    assert result.exit_code == 1
    assert "FAIL" in result.stdout


def test_verify_refuses_a_manifest_belonging_to_another_dataset(tmp_path: Path) -> None:
    copy = tmp_path / "copy"
    copy.mkdir()
    (copy / "file.txt").write_text("x", encoding="utf-8")
    destination = tmp_path / "manifest.json"
    runner.invoke(
        app,
        ["dataset", "manifest", "shanghaitech-a", "--path", str(copy),
         "--output", str(destination)],
    )

    result = runner.invoke(
        app,
        ["dataset", "verify", "ucf-qnrf", "--path", str(copy),
         "--manifest", str(destination)],
    )
    assert result.exit_code != 0
