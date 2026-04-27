from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from luplo_cloud import keyring_store
from luplo_cloud.main import app


def test_mcp_config_requires_login() -> None:
    """No env key, no keyring entry → friendly error pointing at both paths."""
    runner = CliRunner()
    r = runner.invoke(app, ["mcp-config"])
    assert r.exit_code == 1
    combined = (r.stdout + r.stderr).lower()
    assert "not logged in" in combined
    # The hint covers BOTH escape hatches: lps login and the env var.
    assert "lps login" in combined
    assert "luplo_cloud_api_key" in combined


def test_mcp_config_emits_claude_desktop_entry() -> None:
    """OAuth (keyring) path: tokens.access_token becomes the bearer."""
    keyring_store.save("acc-xyz", "ref-xyz")
    runner = CliRunner()
    r = runner.invoke(app, ["mcp-config", "--server", "https://api.example.com"])
    assert r.exit_code == 0
    payload = json.loads(r.stdout)
    luplo = payload["mcpServers"]["luplo"]
    assert luplo["url"] == "https://api.example.com/mcp"
    assert luplo["transport"] == "streamable-http"
    assert luplo["authentication"]["bearer_token"] == "acc-xyz"


def test_mcp_config_compact_is_valid_json() -> None:
    keyring_store.save("a", "b")
    runner = CliRunner()
    r = runner.invoke(app, ["mcp-config", "--compact"])
    assert r.exit_code == 0
    assert "\n" not in r.stdout.strip()
    json.loads(r.stdout)


def test_mcp_config_emits_api_key_when_env_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Env-var API key takes priority over keyring (D1 spec)."""
    monkeypatch.setenv("LUPLO_CLOUD_API_KEY", "lupk_envkey1234")
    runner = CliRunner()
    r = runner.invoke(app, ["mcp-config", "--server", "https://api.example.com"])
    assert r.exit_code == 0
    payload = json.loads(r.stdout)
    assert payload["mcpServers"]["luplo"]["authentication"]["bearer_token"] == "lupk_envkey1234"


def test_mcp_config_env_key_wins_over_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both env and keyring populated → env wins, keyring is not consulted."""
    keyring_store.save("oauth-token", "oauth-refresh")
    monkeypatch.setenv("LUPLO_CLOUD_API_KEY", "lupk_envkey1234")
    runner = CliRunner()
    r = runner.invoke(app, ["mcp-config"])
    assert r.exit_code == 0
    payload = json.loads(r.stdout)
    assert payload["mcpServers"]["luplo"]["authentication"]["bearer_token"] == "lupk_envkey1234"


def test_mcp_config_friendly_error_on_no_keyring_no_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Headless Linux (no keyring backend) and no env key → exit 1, no
    raw NoKeyringError traceback."""
    from keyring.errors import NoKeyringError

    def _raises(*_: object, **__: object) -> None:
        raise NoKeyringError("no backend")

    monkeypatch.setattr(keyring_store, "load", _raises)
    monkeypatch.delenv("LUPLO_CLOUD_API_KEY", raising=False)
    runner = CliRunner()
    r = runner.invoke(app, ["mcp-config"])
    assert r.exit_code == 1
    combined = (r.stdout + r.stderr).lower()
    assert "no os keyring" in combined
    assert "luplo_cloud_api_key" in combined
    # No raw Python traceback — friendly error swallowed it via `from None`.
    assert "traceback" not in combined
    assert "nokeyringerror" not in combined
