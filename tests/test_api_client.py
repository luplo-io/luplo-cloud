from __future__ import annotations

import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from luplo_cloud import keyring_store
from luplo_cloud.api_client import ApiClient, AuthError
from luplo_cloud.config import CliConfig


class _FakeApi:
    """Tiny HTTP server that stands in for the real luplo-cloud API."""

    def __init__(self, handler_factory: Callable[[], type[BaseHTTPRequestHandler]]):
        self._handler_cls = handler_factory()
        self._server = HTTPServer(("127.0.0.1", 0), self._handler_cls)
        self.base_url = f"http://127.0.0.1:{self._server.server_port}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()


def _make_handler(route_responses: dict[str, Any]):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a: object) -> None:
            return

        def _send_json(self, status: int, body: dict) -> None:
            import json

            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:
            spec = route_responses.get(("GET", self.path))
            if not spec:
                self._send_json(404, {"detail": "not found"})
                return
            spec["hits"] = spec.get("hits", 0) + 1
            code, body = spec["resolver"](self, spec)
            self._send_json(code, body)

        def do_POST(self) -> None:
            spec = route_responses.get(("POST", self.path))
            if not spec:
                self._send_json(404, {"detail": "not found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            _ = self.rfile.read(length) if length else b""
            spec["hits"] = spec.get("hits", 0) + 1
            code, body = spec["resolver"](self, spec)
            self._send_json(code, body)

    return H


def test_me_returns_user_info() -> None:
    keyring_store.save("acc-good", "ref-1")

    def me_ok(_h, _spec):
        return 200, {
            "id": "u1",
            "email": "x@example.com",
            "actor_id": "a1",
            "created_at": "2026-04-21T00:00:00+00:00",
        }

    routes: dict[str, Any] = {
        ("GET", "/auth/me"): {"resolver": me_ok},
    }
    api = _FakeApi(lambda: _make_handler(routes))
    try:
        client = ApiClient(CliConfig(server_url=api.base_url, app_url=""))
        user = client.me()
        assert user["email"] == "x@example.com"
    finally:
        api.close()


def test_me_refreshes_on_401_and_retries() -> None:
    keyring_store.save("acc-old", "ref-rotatable")
    call_log: list[str] = []

    def me_resolver(h: BaseHTTPRequestHandler, _spec):
        auth = h.headers.get("Authorization", "")
        call_log.append(auth)
        if auth == "Bearer acc-old":
            return 401, {"detail": "expired"}
        return 200, {
            "id": "u2",
            "email": "y@example.com",
            "actor_id": "a2",
            "created_at": "2026-04-21T00:00:00+00:00",
        }

    def refresh_resolver(_h, _spec):
        return 200, {
            "access_token": "acc-new",
            "refresh_token": "ref-new",
            "token_type": "bearer",
            "expires_in": 900,
        }

    routes: dict[str, Any] = {
        ("GET", "/auth/me"): {"resolver": me_resolver},
        ("POST", "/auth/refresh"): {"resolver": refresh_resolver},
    }
    api = _FakeApi(lambda: _make_handler(routes))
    try:
        client = ApiClient(CliConfig(server_url=api.base_url, app_url=""))
        user = client.me()
        assert user["email"] == "y@example.com"
    finally:
        api.close()

    stored = keyring_store.load()
    assert stored is not None
    assert stored.access_token == "acc-new"
    assert stored.refresh_token == "ref-new"
    assert call_log == ["Bearer acc-old", "Bearer acc-new"]


def test_me_fails_without_login() -> None:
    client = ApiClient(CliConfig(server_url="http://unused", app_url=""))
    with pytest.raises(AuthError, match="not logged in"):
        client.me()
