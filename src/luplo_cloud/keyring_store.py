"""Keyring storage for luplo-cloud CLI tokens.

One service namespace ("luplo-cloud") holds two entries:

- "access"  → access JWT
- "refresh" → refresh token

Legacy migration: tokens stored under the old service ID "luplo-saas"
(used before the package was renamed) are transparently moved into the
new namespace on first read. The legacy entries are then deleted.
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass

import keyring

SERVICE = "luplo-cloud"
LEGACY_SERVICE = "luplo-saas"


@dataclass(slots=True, frozen=True)
class StoredTokens:
    access_token: str
    refresh_token: str


def _load_from_service(service: str) -> StoredTokens | None:
    access = keyring.get_password(service, "access")
    refresh = keyring.get_password(service, "refresh")
    if access and refresh:
        return StoredTokens(access_token=access, refresh_token=refresh)
    return None


def _delete_service(service: str) -> None:
    """Best-effort delete of both slots; platform delete errors are swallowed."""
    for slot in ("access", "refresh"):
        with contextlib.suppress(Exception):
            keyring.delete_password(service, slot)


def save(access_token: str, refresh_token: str) -> None:
    keyring.set_password(SERVICE, "access", access_token)
    keyring.set_password(SERVICE, "refresh", refresh_token)


def load() -> StoredTokens | None:
    """Return tokens stored under :data:`SERVICE`, migrating from
    :data:`LEGACY_SERVICE` on first call if necessary."""
    tokens = _load_from_service(SERVICE)
    if tokens is not None:
        return tokens
    legacy = _load_from_service(LEGACY_SERVICE)
    if legacy is not None:
        save(legacy.access_token, legacy.refresh_token)
        _delete_service(LEGACY_SERVICE)
        return legacy
    return None


def clear() -> None:
    """Remove tokens from the new service namespace.

    Legacy entries (if any) are also cleaned up to keep the system tidy.
    """
    _delete_service(SERVICE)
    _delete_service(LEGACY_SERVICE)
