"""Test fixtures for luplo-cloud.

Swaps the global ``keyring`` backend for an in-memory fake so tests never
touch the developer's real macOS Keychain / Windows Credential Store /
Secret Service.
"""
from __future__ import annotations

import pytest
from keyring.backend import KeyringBackend


class InMemoryKeyring(KeyringBackend):
    priority = 100  # type: ignore[assignment]

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], str] = {}

    def set_password(self, service: str, username: str, password: str) -> None:
        self._store[(service, username)] = password

    def get_password(self, service: str, username: str) -> str | None:
        return self._store.get((service, username))

    def delete_password(self, service: str, username: str) -> None:
        try:
            del self._store[(service, username)]
        except KeyError:
            import keyring.errors

            raise keyring.errors.PasswordDeleteError("not found") from None


@pytest.fixture(autouse=True)
def in_memory_keyring():
    import keyring

    original = keyring.get_keyring()
    mem = InMemoryKeyring()
    keyring.set_keyring(mem)
    yield mem
    keyring.set_keyring(original)
