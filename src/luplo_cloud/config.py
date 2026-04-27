"""Runtime configuration for ``lps``."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _server_url() -> str:
    return os.environ.get("LUPLO_CLOUD_SERVER_URL", "https://api.luplo.io")


def _app_url() -> str:
    return os.environ.get("LUPLO_CLOUD_APP_URL", "https://app.luplo.io")


def _api_key() -> str | None:
    return os.environ.get("LUPLO_CLOUD_API_KEY")


@dataclass(slots=True, frozen=True)
class CliConfig:
    server_url: str
    app_url: str
    api_key: str | None = None  # opaque lupk_... — when present, bypasses keyring path

    @classmethod
    def resolve(
        cls,
        server_url: str | None,
        app_url: str | None,
        api_key: str | None = None,
    ) -> CliConfig:
        # Resolve env vars at call time, not import time, so wrapper scripts
        # that exec `lps` after exporting LUPLO_CLOUD_* see the updated value.
        return cls(
            server_url=(server_url or _server_url()).rstrip("/"),
            app_url=(app_url or _app_url()).rstrip("/"),
            api_key=api_key or _api_key(),
        )
