from __future__ import annotations

import json

import typer
from keyring.errors import NoKeyringError

from luplo_cloud import keyring_store
from luplo_cloud.config import CliConfig

_HEADLESS_HINT = (
    "Issue an API key at https://app.luplo.io/settings/api-keys "
    "and `export LUPLO_CLOUD_API_KEY=lupk_...`."
)


def run(
    server_url: str = typer.Option(None, "--server", help="API base URL."),
    pretty: bool = typer.Option(True, "--pretty/--compact", help="Indent output."),
) -> None:
    """Emit a Claude Desktop / Claude Code mcpServers entry.

    The bearer token is selected by priority:
      1. ``$LUPLO_CLOUD_API_KEY``  (server / CI / IaC)
      2. tokens stored by ``lps login``  (desktop OAuth)
    """
    cfg = CliConfig.resolve(server_url, None)

    if cfg.api_key:
        bearer = cfg.api_key
    else:
        try:
            tokens = keyring_store.load()
        except NoKeyringError:
            typer.secho(
                "No OS keyring backend available on this system, "
                "and LUPLO_CLOUD_API_KEY is not set.\n"
                f"  → {_HEADLESS_HINT}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1) from None
        if tokens is None:
            typer.secho(
                "Not logged in. Either run `lps login` (interactive, desktop) "
                "or set LUPLO_CLOUD_API_KEY (server / CI).\n"
                f"  → {_HEADLESS_HINT}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        bearer = tokens.access_token

    entry = {
        "mcpServers": {
            "luplo": {
                "url": f"{cfg.server_url}/mcp",
                "transport": "streamable-http",
                "authentication": {"bearer_token": bearer},
            }
        }
    }
    indent = 2 if pretty else None
    typer.echo(json.dumps(entry, indent=indent))
