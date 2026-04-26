"""Migration of tokens stored under the legacy service ID "luplo-saas"
into the new "luplo-cloud" namespace."""
from __future__ import annotations

import keyring

from luplo_cloud import keyring_store
from luplo_cloud.keyring_store import LEGACY_SERVICE, SERVICE


def test_migration_moves_legacy_tokens() -> None:
    keyring.set_password(LEGACY_SERVICE, "access", "old-access")
    keyring.set_password(LEGACY_SERVICE, "refresh", "old-refresh")

    tokens = keyring_store.load()

    assert tokens is not None
    assert tokens.access_token == "old-access"
    assert tokens.refresh_token == "old-refresh"
    # New namespace populated
    assert keyring.get_password(SERVICE, "access") == "old-access"
    assert keyring.get_password(SERVICE, "refresh") == "old-refresh"
    # Legacy namespace cleared
    assert keyring.get_password(LEGACY_SERVICE, "access") is None
    assert keyring.get_password(LEGACY_SERVICE, "refresh") is None


def test_no_legacy_no_migration() -> None:
    assert keyring_store.load() is None
    assert keyring.get_password(SERVICE, "access") is None
    assert keyring.get_password(LEGACY_SERVICE, "access") is None


def test_new_wins_over_legacy_when_both_present() -> None:
    keyring.set_password(LEGACY_SERVICE, "access", "old-access")
    keyring.set_password(LEGACY_SERVICE, "refresh", "old-refresh")
    keyring.set_password(SERVICE, "access", "new-access")
    keyring.set_password(SERVICE, "refresh", "new-refresh")

    tokens = keyring_store.load()

    assert tokens is not None
    assert tokens.access_token == "new-access"
    assert tokens.refresh_token == "new-refresh"
    # Legacy entries are left in place (no destructive reconciliation)
    assert keyring.get_password(LEGACY_SERVICE, "access") == "old-access"
