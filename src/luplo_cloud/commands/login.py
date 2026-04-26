from __future__ import annotations

import typer

from luplo_cloud import keyring_store
from luplo_cloud.auth_flow import LoginBridge, LoginError
from luplo_cloud.config import CliConfig


def run(
    server_url: str = typer.Option(None, "--server", help="API base URL."),
    app_url: str = typer.Option(None, "--app", help="Web app base URL."),
    timeout: int = typer.Option(180, "--timeout", help="Seconds to wait for browser."),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't auto-open the browser."),
) -> None:
    """Authenticate via browser and store tokens in the OS keyring."""
    cfg = CliConfig.resolve(server_url, app_url)
    try:
        with LoginBridge(timeout_seconds=timeout) as bridge:
            if no_browser:
                typer.echo(f"Open this URL in a browser:\n  {bridge.build_app_url(cfg.app_url)}")
            else:
                url = bridge.open_browser(cfg.app_url)
                typer.echo(f"Opened browser: {url}")
                typer.echo("Waiting for callback… (ctrl-c to abort)")
            tokens = bridge.wait()
    except LoginError as e:
        typer.secho(f"Login failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from None

    keyring_store.save(tokens.access_token, tokens.refresh_token)
    typer.secho("✓ Logged in. Tokens saved in system keyring.", fg=typer.colors.GREEN)
