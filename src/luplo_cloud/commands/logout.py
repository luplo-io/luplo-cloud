from __future__ import annotations

import typer

from luplo_cloud import keyring_store
from luplo_cloud.api_client import ApiClient
from luplo_cloud.config import CliConfig


def run(
    server_url: str = typer.Option(None, "--server", help="API base URL."),
) -> None:
    """Revoke the local refresh token on the server and clear the keyring."""
    cfg = CliConfig.resolve(server_url, None)
    if keyring_store.load() is None:
        typer.echo("Not logged in.")
        return
    client = ApiClient(cfg)
    try:
        client.logout_remote()
    finally:
        client.close()
    keyring_store.clear()
    typer.secho("✓ Logged out.", fg=typer.colors.GREEN)
