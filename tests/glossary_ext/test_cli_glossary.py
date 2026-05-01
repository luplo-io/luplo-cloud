from typer.testing import CliRunner

from luplo_cloud.main import app

runner = CliRunner()


def test_glossary_help_shows_suggest():
    result = runner.invoke(app, ["glossary", "--help"])
    assert result.exit_code == 0
    assert "suggest" in result.output.lower()


def test_glossary_suggest_help():
    result = runner.invoke(app, ["glossary", "suggest", "--help"])
    assert result.exit_code == 0
    assert "--limit" in result.output
    assert "--threshold" in result.output
    assert "--type" in result.output
