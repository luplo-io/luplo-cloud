"""Browser-mediated CLI login flow.

The CLI spins up a short-lived localhost HTTP server on a random port,
opens the web app's ``/cli-login`` page with the callback URL + a CSRF
``state`` token, and waits for the page to POST the issued access +
refresh tokens back. First request wins — the server shuts down once
a matching state arrives or a timeout elapses.
"""
from __future__ import annotations

import json
import secrets
import socket
import threading
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer


@dataclass(slots=True, frozen=True)
class ReceivedTokens:
    access_token: str
    refresh_token: str


class _LoginError(Exception):
    pass


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Handler(BaseHTTPRequestHandler):
    expected_state: str = ""
    received: ReceivedTokens | None = None
    error: str | None = None
    done: threading.Event = threading.Event()

    # silence default stderr access log
    def log_message(self, format: str, *args: object) -> None:
        return

    def _respond(self, code: int, body: str, content_type: str = "text/plain") -> None:
        self.send_response(code)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        # permissive CORS so the browser app.luplo.io page can POST here
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        body_bytes = body.encode("utf-8")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def do_OPTIONS(self) -> None:
        self._respond(204, "")

    def do_POST(self) -> None:
        cls = type(self)
        if cls.received is not None or cls.error is not None:
            self._respond(409, "already handled")
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as e:
            cls.error = f"invalid JSON body: {e}"
            self._respond(400, cls.error)
            cls.done.set()
            return
        if payload.get("state") != cls.expected_state:
            cls.error = "state mismatch"
            self._respond(400, cls.error)
            cls.done.set()
            return
        access = payload.get("access_token")
        refresh = payload.get("refresh_token")
        if not access or not refresh:
            cls.error = "missing tokens"
            self._respond(400, cls.error)
            cls.done.set()
            return
        cls.received = ReceivedTokens(access_token=access, refresh_token=refresh)
        self._respond(200, "ok")
        cls.done.set()


class LoginBridge:
    """Context-manager style helper used by both the real CLI and tests."""

    def __init__(self, *, timeout_seconds: float = 180.0):
        self.timeout_seconds = timeout_seconds
        self.state = secrets.token_urlsafe(24)
        self.port = _pick_free_port()
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def callback_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    def __enter__(self) -> LoginBridge:
        handler = type("H", (_Handler,), {
            "expected_state": self.state,
            "received": None,
            "error": None,
            "done": threading.Event(),
        })
        self._handler_cls = handler  # type: ignore[attr-defined]
        self._server = HTTPServer(("127.0.0.1", self.port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def build_app_url(self, app_url: str) -> str:
        from urllib.parse import quote

        return (
            f"{app_url.rstrip('/')}/cli-login"
            f"?cb={quote(self.callback_url, safe='')}&state={self.state}"
        )

    def open_browser(self, app_url: str) -> str:
        url = self.build_app_url(app_url)
        webbrowser.open_new(url)
        return url

    def wait(self) -> ReceivedTokens:
        h = self._handler_cls
        got = h.done.wait(timeout=self.timeout_seconds)  # type: ignore[attr-defined]
        if not got:
            raise _LoginError("timeout waiting for browser callback")
        if h.error:  # type: ignore[attr-defined]
            raise _LoginError(h.error)  # type: ignore[attr-defined]
        if h.received is None:  # type: ignore[attr-defined]
            raise _LoginError("callback completed with no tokens")
        return h.received  # type: ignore[attr-defined]


LoginError = _LoginError
