import json

from typer.testing import CliRunner

from crowdent.cli import app

runner = CliRunner()


def test_doctor_reports_research_only_and_no_hardware() -> None:
    result = runner.invoke(app, ["doctor", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["research_only"] is True
    assert payload["deployment_certified"] is False
    assert payload["checks"]["hardware_actuation"]["value"] == "not implemented"
    assert payload["checks"]["loopback_default"]["ok"] is True
