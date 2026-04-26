"""Runtime configuration for ``lps``."""
from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_SERVER_URL = os.environ.get("LUPLO_CLOUD_SERVER_URL", "https://api.luplo.io")
DEFAULT_APP_URL = os.environ.get("LUPLO_CLOUD_APP_URL", "https://app.luplo.io")
DEFAULT_API_KEY = os.environ.get("LUPLO_CLOUD_API_KEY")


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
        return cls(
            server_url=(server_url or DEFAULT_SERVER_URL).rstrip("/"),
            app_url=(app_url or DEFAULT_APP_URL).rstrip("/"),
            api_key=api_key or DEFAULT_API_KEY,
        )
