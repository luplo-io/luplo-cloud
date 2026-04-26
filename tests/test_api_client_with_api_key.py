from __future__ import annotations

from unittest.mock import patch

import httpx
import respx

from luplo_cloud.api_client import ApiClient
from luplo_cloud.config import CliConfig


def test_api_key_short_circuits_keyring():
    cfg = CliConfig(server_url="https://api.test", app_url="https://app.test", api_key="lupk_deadbeef")
    client = ApiClient(cfg)
    with respx.mock(base_url="https://api.test") as mock:
        route = mock.get("/auth/me").mock(return_value=httpx.Response(200, json={"id": "u"}))
        with patch("luplo_cloud.keyring_store.load") as load:
            r = client.get("/auth/me")
            load.assert_not_called()
        assert r.status_code == 200
        assert route.calls.last.request.headers["authorization"] == "Bearer lupk_deadbeef"
