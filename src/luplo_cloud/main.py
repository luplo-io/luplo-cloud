"""``lps`` — luplo-cloud CLI adapter.

A thin Typer app exposing the user-visible commands needed to connect a
developer machine to the hosted luplo service:

    lps login [--server URL] [--app URL]
    lps logout
    lps whoami
    lps init      # create .luplo workspace file in cwd
    lps mcp-config

Tokens are stored in the OS keyring (Keychain / Windows Credential /
Secret Service). No config files, no long-lived secrets on disk.
"""
from __future__ import annotations

import typer

from luplo_cloud.commands import init as init_cmd
from luplo_cloud.commands import login as login_cmd
from luplo_cloud.commands import logout as logout_cmd
from luplo_cloud.commands import mcp_config as mcp_config_cmd
from luplo_cloud.commands import whoami as whoami_cmd

app = typer.Typer(
    name="lps",
    help="luplo-cloud CLI adapter.",
    no_args_is_help=True,
    add_completion=False,
)

app.command("login")(login_cmd.run)
app.command("logout")(logout_cmd.run)
app.command("whoami")(whoami_cmd.run)
app.command("init")(init_cmd.run)
app.command("mcp-config")(mcp_config_cmd.run)


if __name__ == "__main__":  # pragma: no cover
    app()
