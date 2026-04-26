"""HTTP client for the hosted luplo-cloud API.

Thin wrapper over ``httpx.Client`` that:
- attaches the stored access token to every request
- transparently refreshes once on 401 using the refresh token, persists
  the new pair in keyring, and replays the original request
"""
from __future__ import annotations

import contextlib
from typing import Any

import httpx

from luplo_cloud import keyring_store
from luplo_cloud.config import CliConfig


class AuthError(Exception):
    """Raised when no valid credentials can be presented to the API."""


class ApiClient:
    def __init__(self, cfg: CliConfig):
        self.cfg = cfg
        self._http = httpx.Client(base_url=cfg.server_url, timeout=10.0)

    # ── token handling ───────────────────────────────────────────

    def _tokens(self) -> keyring_store.StoredTokens:
        t = keyring_store.load()
        if t is None:
            raise AuthError("not logged in — run `lps login`")
        return t

    def _refresh(self) -> keyring_store.StoredTokens:
        tokens = self._tokens()
        r = self._http.post(
            "/auth/refresh", json={"refresh_token": tokens.refresh_token}
        )
        if r.status_code != 200:
            raise AuthError(f"refresh failed: {r.status_code} {r.text}")
        data = r.json()
        new = keyring_store.StoredTokens(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
        )
        keyring_store.save(new.access_token, new.refresh_token)
        return new

    # ── request helpers ──────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        _retry: bool = True,
    ) -> httpx.Response:
        if self.cfg.api_key:
            headers = {"Authorization": f"Bearer {self.cfg.api_key}"}
            return self._http.request(method, path, headers=headers, json=json)
        tokens = self._tokens()
        headers = {"Authorization": f"Bearer {tokens.access_token}"}
        r = self._http.request(method, path, headers=headers, json=json)
        if r.status_code == 401 and _retry:
            self._refresh()
            return self._request(method, path, json=json, _retry=False)
        return r

    def get(self, path: str) -> httpx.Response:
        return self._request("GET", path)

    def post(self, path: str, json: Any = None) -> httpx.Response:
        return self._request("POST", path, json=json)

    # ── typed helpers ───────────────────────────────────────────

    def me(self) -> dict[str, Any]:
        r = self.get("/auth/me")
        r.raise_for_status()
        return r.json()

    def logout_remote(self) -> None:
        t = keyring_store.load()
        refresh = t.refresh_token if t else None
        # fire-and-forget: server-side revoke is best effort; local keyring
        # is the source of truth for "am I logged in on this machine"
        with contextlib.suppress(httpx.HTTPError):
            self._http.post("/auth/logout", json={"refresh_token": refresh})

    def close(self) -> None:
        self._http.close()
