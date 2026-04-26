from __future__ import annotations

from luplo_cloud import keyring_store


def test_save_load_round_trip() -> None:
    keyring_store.save("acc-1", "ref-1")
    t = keyring_store.load()
    assert t is not None
    assert t.access_token == "acc-1"
    assert t.refresh_token == "ref-1"


def test_load_returns_none_when_absent() -> None:
    assert keyring_store.load() is None


def test_clear_is_idempotent() -> None:
    keyring_store.clear()  # empty keyring — must not raise
    keyring_store.save("a", "b")
    keyring_store.clear()
    assert keyring_store.load() is None
    keyring_store.clear()  # already cleared — still fine


def test_load_returns_none_if_only_access_saved() -> None:
    import keyring

    keyring.set_password(keyring_store.SERVICE, "access", "only-access")
    assert keyring_store.load() is None
