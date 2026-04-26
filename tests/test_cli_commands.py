from __future__ import annotations

from typer.testing import CliRunner

from luplo_cloud import keyring_store
from luplo_cloud.main import app


def test_lps_help_lists_commands() -> None:
    runner = CliRunner()
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    out = r.stdout.lower()
    assert "login" in out
    assert "logout" in out
    assert "whoami" in out


def test_lps_logout_when_not_logged_in() -> None:
    runner = CliRunner()
    r = runner.invoke(app, ["logout"])
    assert r.exit_code == 0
    assert "Not logged in" in r.stdout


def test_lps_logout_clears_keyring() -> None:
    keyring_store.save("a", "b")
    runner = CliRunner()
    # point at an obviously-dead URL so logout_remote silently swallows the error
    r = runner.invoke(app, ["logout", "--server", "http://127.0.0.1:1"])
    assert r.exit_code == 0
    assert keyring_store.load() is None
