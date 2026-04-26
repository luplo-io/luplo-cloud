from __future__ import annotations

import json

import typer

from luplo_cloud import keyring_store
from luplo_cloud.config import CliConfig


def run(
    server_url: str = typer.Option(None, "--server", help="API base URL."),
    pretty: bool = typer.Option(True, "--pretty/--compact", help="Indent output."),
) -> None:
    """Emit a Claude Desktop mcpServers entry wired to this machine.

    Copy/paste the result into ``claude_desktop_config.json``. The access
    token embedded in the output comes from the local keyring; rotate it
    by running ``lps login`` again.
    """
    cfg = CliConfig.resolve(server_url, None)
    tokens = keyring_store.load()
    if tokens is None:
        typer.secho("Not logged in — run `lps login` first.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    entry = {
        "mcpServers": {
            "luplo": {
                "url": f"{cfg.server_url}/mcp",
                "transport": "streamable-http",
                "authentication": {"bearer_token": tokens.access_token},
            }
        }
    }
    indent = 2 if pretty else None
    typer.echo(json.dumps(entry, indent=indent))
