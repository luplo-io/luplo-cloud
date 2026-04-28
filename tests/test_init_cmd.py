"""Tests for ``lps init``.

Covers the four flows:
- interactive picker (org single + project picker, "create new" branch)
- ``--project`` (non-interactive bind to existing)
- ``--new-project`` (non-interactive create)
- guard rails (existing .luplo without --force, mutually exclusive flags)
"""
from __future__ import annotations

import json
import tomllib
from pathlib import Path

import httpx
import respx
from typer.testing import CliRunner

from luplo_cloud import keyring_store
from luplo_cloud.main import app

_BASE = "https://api.test"
_ORG_ID = "11111111-1111-1111-1111-111111111111"
_OTHER_ORG = "22222222-2222-2222-2222-222222222222"


def _stub_orgs(mock: respx.MockRouter, orgs: list[dict]) -> None:
    mock.get("/orgs").mock(return_value=httpx.Response(200, json=orgs))


def _org_row(org_id: str = _ORG_ID, name: str = "Acme", slug: str = "acme") -> dict:
    return {
        "org": {
            "id": org_id,
            "slug": slug,
            "name": name,
            "plan": "free",
            "max_members": 10,
            "max_storage_bytes": 1,
            "created_at": "2026-04-27T00:00:00+00:00",
        },
        "role": "owner",
    }


def _project_row(project_id: str, name: str | None = None) -> dict:
    return {
        "project_id": project_id,
        "org_id": _ORG_ID,
        "display_name": name or project_id,
        "name": name or project_id,
        "description": None,
        "project_image": None,
        "is_default": False,
        "archived_at": None,
        "created_at": "2026-04-27T00:00:00+00:00",
    }


def _login() -> None:
    keyring_store.save("acc", "ref")


def test_init_interactive_single_org_pick_existing(tmp_path: Path, monkeypatch) -> None:
    _login()
    monkeypatch.chdir(tmp_path)
    with respx.mock(base_url=_BASE) as mock:
        _stub_orgs(mock, [_org_row()])
        mock.get(f"/projects?org_id={_ORG_ID}").mock(
            return_value=httpx.Response(
                200, json=[_project_row("proj-a", "Alpha"), _project_row("proj-b", "Beta")]
            )
        )
        r = CliRunner().invoke(app, ["init", "--server", _BASE], input="2\n")
    assert r.exit_code == 0, r.stdout + (r.stderr or "")
    written = (tmp_path / ".luplo").read_text()
    parsed = tomllib.loads(written)
    assert parsed["backend"]["type"] == "remote"
    assert parsed["backend"]["server_url"] == _BASE
    assert parsed["project"]["id"] == "proj-b"
    assert parsed["project"]["name"] == "Beta"


def test_init_interactive_create_new_branch(tmp_path: Path, monkeypatch) -> None:
    _login()
    monkeypatch.chdir(tmp_path)
    with respx.mock(base_url=_BASE) as mock:
        _stub_orgs(mock, [_org_row()])
        mock.get(f"/projects?org_id={_ORG_ID}").mock(
            return_value=httpx.Response(200, json=[_project_row("proj-a", "Alpha")])
        )
        create_route = mock.post("/projects").mock(
            return_value=httpx.Response(
                201, json=_project_row("proj-new", "Bravo")
            )
        )
        # 2 = "+ Create new project" (one project listed → create option is index 2)
        r = CliRunner().invoke(app, ["init", "--server", _BASE], input="2\nBravo\n")
    assert r.exit_code == 0, r.stdout + (r.stderr or "")
    body = json.loads(create_route.calls.last.request.content)
    assert body == {"org_id": _ORG_ID, "name": "Bravo"}
    parsed = tomllib.loads((tmp_path / ".luplo").read_text())
    assert parsed["project"]["id"] == "proj-new"
    assert parsed["project"]["name"] == "Bravo"


def test_init_org_flag_skips_picker(tmp_path: Path, monkeypatch) -> None:
    _login()
    monkeypatch.chdir(tmp_path)
    with respx.mock(base_url=_BASE) as mock:
        _stub_orgs(mock, [_org_row(), _org_row(_OTHER_ORG, "Other", "other")])
        mock.get(f"/projects?org_id={_OTHER_ORG}").mock(
            return_value=httpx.Response(200, json=[_project_row("o1", "OneOnly")])
        )
        r = CliRunner().invoke(
            app, ["init", "--server", _BASE, "--org", _OTHER_ORG], input="1\n"
        )
    assert r.exit_code == 0, r.stdout + (r.stderr or "")
    parsed = tomllib.loads((tmp_path / ".luplo").read_text())
    assert parsed["project"]["id"] == "o1"


def test_init_project_flag_non_interactive(tmp_path: Path, monkeypatch) -> None:
    _login()
    monkeypatch.chdir(tmp_path)
    with respx.mock(base_url=_BASE) as mock:
        _stub_orgs(mock, [_org_row()])
        mock.get(f"/projects?org_id={_ORG_ID}").mock(
            return_value=httpx.Response(200, json=[_project_row("proj-a", "Alpha")])
        )
        r = CliRunner().invoke(
            app, ["init", "--server", _BASE, "--project", "proj-a"]
        )
    assert r.exit_code == 0, r.stdout + (r.stderr or "")
    parsed = tomllib.loads((tmp_path / ".luplo").read_text())
    assert parsed["project"]["id"] == "proj-a"
    assert parsed["project"]["name"] == "Alpha"


def test_init_project_flag_unknown_id_fails(tmp_path: Path, monkeypatch) -> None:
    _login()
    monkeypatch.chdir(tmp_path)
    with respx.mock(base_url=_BASE) as mock:
        _stub_orgs(mock, [_org_row()])
        mock.get(f"/projects?org_id={_ORG_ID}").mock(
            return_value=httpx.Response(200, json=[_project_row("proj-a", "Alpha")])
        )
        r = CliRunner().invoke(
            app, ["init", "--server", _BASE, "--project", "nope"]
        )
    assert r.exit_code == 2
    assert not (tmp_path / ".luplo").exists()


def test_init_new_project_flag_non_interactive(tmp_path: Path, monkeypatch) -> None:
    _login()
    monkeypatch.chdir(tmp_path)
    with respx.mock(base_url=_BASE) as mock:
        _stub_orgs(mock, [_org_row()])
        mock.post("/projects").mock(
            return_value=httpx.Response(201, json=_project_row("proj-new", "New One"))
        )
        r = CliRunner().invoke(
            app, ["init", "--server", _BASE, "--new-project", "New One"]
        )
    assert r.exit_code == 0, r.stdout + (r.stderr or "")
    parsed = tomllib.loads((tmp_path / ".luplo").read_text())
    assert parsed["project"]["id"] == "proj-new"
    assert parsed["project"]["name"] == "New One"


def test_init_project_and_new_project_mutually_exclusive(tmp_path: Path, monkeypatch) -> None:
    _login()
    monkeypatch.chdir(tmp_path)
    r = CliRunner().invoke(
        app, ["init", "--project", "x", "--new-project", "y"]
    )
    assert r.exit_code == 2
    assert "mutually exclusive" in (r.stdout + (r.stderr or "")).lower()
    assert not (tmp_path / ".luplo").exists()


def test_init_refuses_to_overwrite_without_force(tmp_path: Path, monkeypatch) -> None:
    _login()
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".luplo").write_text("old content")
    r = CliRunner().invoke(app, ["init"])
    assert r.exit_code == 1
    combined = (r.stdout + (r.stderr or "")).lower()
    assert "already exists" in combined and "--force" in combined
    assert (tmp_path / ".luplo").read_text() == "old content"


def test_init_force_overwrites(tmp_path: Path, monkeypatch) -> None:
    _login()
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".luplo").write_text("old content")
    with respx.mock(base_url=_BASE) as mock:
        _stub_orgs(mock, [_org_row()])
        mock.get(f"/projects?org_id={_ORG_ID}").mock(
            return_value=httpx.Response(200, json=[_project_row("proj-a", "Alpha")])
        )
        r = CliRunner().invoke(
            app,
            ["init", "--server", _BASE, "--project", "proj-a", "--force"],
        )
    assert r.exit_code == 0, r.stdout + (r.stderr or "")
    parsed = tomllib.loads((tmp_path / ".luplo").read_text())
    assert parsed["project"]["id"] == "proj-a"


def test_init_requires_login(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    r = CliRunner().invoke(app, ["init", "--server", _BASE])
    assert r.exit_code == 1
    assert "not logged in" in (r.stdout + (r.stderr or "")).lower()


def test_init_org_flag_unknown_id_fails(tmp_path: Path, monkeypatch) -> None:
    _login()
    monkeypatch.chdir(tmp_path)
    with respx.mock(base_url=_BASE) as mock:
        _stub_orgs(mock, [_org_row()])
        r = CliRunner().invoke(
            app, ["init", "--server", _BASE, "--org", _OTHER_ORG]
        )
    assert r.exit_code == 2
    assert not (tmp_path / ".luplo").exists()


def test_init_no_orgs_exits_with_message(tmp_path: Path, monkeypatch) -> None:
    _login()
    monkeypatch.chdir(tmp_path)
    with respx.mock(base_url=_BASE) as mock:
        _stub_orgs(mock, [])
        r = CliRunner().invoke(app, ["init", "--server", _BASE])
    assert r.exit_code == 1
    assert "any organization" in (r.stdout + (r.stderr or "")).lower()


def test_init_escapes_quotes_in_project_name(tmp_path: Path, monkeypatch) -> None:
    _login()
    monkeypatch.chdir(tmp_path)
    with respx.mock(base_url=_BASE) as mock:
        _stub_orgs(mock, [_org_row()])
        mock.get(f"/projects?org_id={_ORG_ID}").mock(
            return_value=httpx.Response(
                200, json=[_project_row("p", 'has "quotes" and \\ slash')]
            )
        )
        r = CliRunner().invoke(
            app, ["init", "--server", _BASE, "--project", "p"]
        )
    assert r.exit_code == 0, r.stdout + (r.stderr or "")
    parsed = tomllib.loads((tmp_path / ".luplo").read_text())
    assert parsed["project"]["name"] == 'has "quotes" and \\ slash'
