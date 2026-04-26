from __future__ import annotations

import typer

from luplo_cloud.api_client import ApiClient, AuthError
from luplo_cloud.config import CliConfig


def run(
    server_url: str = typer.Option(None, "--server", help="API base URL."),
) -> None:
    """Print the email and actor_id of the currently logged-in user."""
    cfg = CliConfig.resolve(server_url, None)
    client = ApiClient(cfg)
    try:
        me = client.me()
    except AuthError as e:
        typer.secho(f"{e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from None
    finally:
        client.close()

    typer.echo(f"email    : {me['email']}")
    typer.echo(f"user_id  : {me['id']}")
    typer.echo(f"actor_id : {me['actor_id']}")
