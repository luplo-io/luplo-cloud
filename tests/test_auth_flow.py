from __future__ import annotations

import json
import threading

import httpx
import pytest

from luplo_cloud.auth_flow import LoginBridge, LoginError


def _post_tokens(url: str, body: dict) -> httpx.Response:
    return httpx.post(url, json=body, timeout=5.0)


def test_bridge_accepts_valid_callback() -> None:
    with LoginBridge(timeout_seconds=5.0) as bridge:
        t = threading.Thread(
            target=lambda: _post_tokens(
                bridge.callback_url,
                {
                    "access_token": "acc-x",
                    "refresh_token": "ref-x",
                    "state": bridge.state,
                },
            ),
            daemon=True,
        )
        t.start()
        received = bridge.wait()
    assert received.access_token == "acc-x"
    assert received.refresh_token == "ref-x"


def test_bridge_rejects_wrong_state() -> None:
    with LoginBridge(timeout_seconds=3.0) as bridge:
        r = _post_tokens(
            bridge.callback_url,
            {"access_token": "a", "refresh_token": "b", "state": "wrong"},
        )
        assert r.status_code == 400
        with pytest.raises(LoginError, match="state mismatch"):
            bridge.wait()


def test_bridge_rejects_missing_tokens() -> None:
    with LoginBridge(timeout_seconds=3.0) as bridge:
        r = _post_tokens(
            bridge.callback_url, {"state": bridge.state}
        )
        assert r.status_code == 400
        with pytest.raises(LoginError, match="missing tokens"):
            bridge.wait()


def test_bridge_times_out() -> None:
    with LoginBridge(timeout_seconds=0.5) as bridge, pytest.raises(LoginError, match="timeout"):
        bridge.wait()


def test_bridge_rejects_invalid_json() -> None:
    with LoginBridge(timeout_seconds=3.0) as bridge:
        r = httpx.post(
            bridge.callback_url,
            content=b"not-json",
            headers={"Content-Type": "application/json"},
            timeout=5.0,
        )
        assert r.status_code == 400
        with pytest.raises(LoginError, match="invalid JSON"):
            bridge.wait()


def test_build_app_url_includes_state_and_cb() -> None:
    with LoginBridge(timeout_seconds=1.0) as bridge:
        url = bridge.build_app_url("https://app.luplo.io")
        assert url.startswith("https://app.luplo.io/cli-login")
        assert f"state={bridge.state}" in url
        assert "cb=http%3A%2F%2F127.0.0.1" in url

    # JSON not relevant here — keep import used
    _ = json
