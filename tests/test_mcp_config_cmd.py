from __future__ import annotations

import json

from typer.testing import CliRunner

from luplo_cloud import keyring_store
from luplo_cloud.main import app


def test_mcp_config_requires_login() -> None:
    runner = CliRunner()
    r = runner.invoke(app, ["mcp-config"])
    assert r.exit_code == 1
    assert "not logged in" in (r.stdout + r.stderr).lower()


def test_mcp_config_emits_claude_desktop_entry() -> None:
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
    # no whitespace between keys in compact form
    assert "\n" not in r.stdout.strip()
    json.loads(r.stdout)  # parses
