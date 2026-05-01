"""Bridge from the lps Typer app to the glossary_ext suggest CLI."""
from __future__ import annotations

import typer

from luplo_cloud.glossary_ext.suggest_cli.cli import register


def attach(app: typer.Typer) -> None:
    register(app)
