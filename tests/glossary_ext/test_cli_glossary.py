import re

from typer.testing import CliRunner

from luplo_cloud.main import app

runner = CliRunner()

_ANSI = re.compile(r"\x1b\[[\d;]*m")


def _plain(s: str) -> str:
    # CI's narrower terminal wraps rich-styled help across lines and
    # interleaves ANSI escapes — strip both so substring assertions hold.
    return re.sub(r"\s+", " ", _ANSI.sub("", s))


def test_glossary_help_shows_suggest():
    result = runner.invoke(app, ["glossary", "--help"])
    assert result.exit_code == 0
    assert "suggest" in _plain(result.output).lower()


def test_glossary_suggest_help():
    result = runner.invoke(app, ["glossary", "suggest", "--help"])
    assert result.exit_code == 0
    plain = _plain(result.output)
    assert "--limit" in plain
    assert "--threshold" in plain
    assert "--type" in plain
