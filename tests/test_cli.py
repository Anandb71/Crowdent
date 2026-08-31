from typer.testing import CliRunner

from stilldot.cli import app

runner = CliRunner()


def test_doctor_mentions_research_and_scenarios() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "research" in result.stdout.lower()
    assert "room_walk" in result.stdout


def test_run_prints_drift_and_honesty() -> None:
    result = runner.invoke(app, ["run", "room_walk"])
    assert result.exit_code == 0
    assert "drift" in result.stdout.lower()
    assert "Synthetic" in result.stdout or "synthetic" in result.stdout.lower()


def test_demo_refuses_lan_bind() -> None:
    result = runner.invoke(app, ["demo", "--host", "0.0.0.0", "--no-browser"])
    assert result.exit_code != 0


def test_scenarios_table() -> None:
    result = runner.invoke(app, ["scenarios"])
    assert result.exit_code == 0
    assert "tunnel" in result.stdout


def test_export_json_to_stdout() -> None:
    result = runner.invoke(app, ["export-json", "--scenario", "room_walk"])
    assert result.exit_code == 0
    assert "room_walk" in result.stdout
    assert "drift_m" in result.stdout
