"""`lps glossary suggest` interactive command.

Three navigation keys (b/n/s) plus 1-4 (pair) or 1-3 (term) for decisions.
Save (`s`) shows a summary and asks once before committing the batch.
Ctrl+C with unsaved decisions warns then releases the lease.

Defaults: project from `.luplo` workspace, actor from `lps whoami`
(keyring-backed) — never require the user to paste UUIDs.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Literal

import psycopg
import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console

from luplo_cloud.glossary_ext.dao_suggestions import (
    lease_suggestions,
    release_lease,
)
from luplo_cloud.glossary_ext.suggest_cli.save import save_decisions
from luplo_cloud.glossary_ext.suggest_cli.session import SuggestSession
from luplo_cloud.glossary_ext.suggest_cli.ui import (
    render_pair_panel,
    render_save_summary,
    render_term_panel,
)

console = Console()
PAIR_KEYS = {"1": "alias", "2": "canonical_replace", "3": "sibling", "4": "skip"}
TERM_KEYS = {"1": "create", "2": "skip", "3": "reject"}

SuggestType = Literal["all", "pair", "term"]


def _resolve_db_url() -> str:
    url = os.environ.get("LUPLO_DB_URL") or os.environ.get("LUPLO_EXT_DB_URL")
    if not url:
        raise typer.BadParameter(
            "LUPLO_DB_URL or LUPLO_EXT_DB_URL must be set for glossary suggest"
        )
    from sqlalchemy.engine.url import make_url
    u = make_url(url).set(query={})
    if u.drivername.startswith("postgresql+"):
        u = u.set(drivername="postgresql")
    return u.render_as_string(hide_password=False)


def _resolve_default_project() -> str | None:
    """Read project_id from `.luplo` workspace file in cwd or any ancestor."""
    import tomllib
    cur = Path.cwd().resolve()
    for d in [cur, *cur.parents]:
        fp = d / ".luplo"
        if fp.exists():
            try:
                data = tomllib.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                return None
            return data.get("project_id") or data.get("project", {}).get("id")
    return None


def _resolve_default_actor() -> str | None:
    """Decode the actor_id from the access JWT stored in keyring by `lps login`.

    `keyring_store.load()` returns `StoredTokens(access_token, refresh_token)`;
    the access JWT's `sub` claim is the actor id. Decode WITHOUT verification
    — this CLI runs locally on a machine the user already trusts; signature
    validation happens server-side on every API call.
    """
    try:
        from luplo_cloud.keyring_store import load
    except ImportError:
        return None
    try:
        tokens = load()
        if tokens is None:
            return None
        # JWT payload is base64url-encoded JSON: header.payload.signature
        import base64
        import json
        parts = tokens.access_token.split(".")
        if len(parts) < 2:
            return None
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        return payload.get("sub")
    except Exception:
        return None


async def _fetch_group_context(
    conn: psycopg.AsyncConnection[Any], group_id: str | None,
) -> tuple[str, list[str]]:
    if not group_id:
        return ("", [])
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT canonical FROM glossary_groups WHERE id = %s", (group_id,)
        )
        row = await cur.fetchone()
        canonical = row[0] if row else ""
        await cur.execute(
            "SELECT surface FROM glossary_terms"
            " WHERE group_id = %s AND status = 'alias' ORDER BY created_at",
            (group_id,),
        )
        aliases = [r[0] for r in await cur.fetchall()]
    return (canonical, aliases)


async def _run(
    project_id: str,
    actor_id: str,
    suggest_type: SuggestType,
    limit: int,
    threshold: float,
) -> None:
    conn = await psycopg.AsyncConnection.connect(_resolve_db_url())
    try:
        # Filters pushed into the lease query (S4) so other sessions can
        # still see rows that don't match this caller's filters.
        kind_filter = None if suggest_type == "all" else suggest_type
        leased = await lease_suggestions(
            conn,
            project_id=project_id,
            leased_by=actor_id,
            limit=limit,
            stale_after_minutes=30,
            kind=kind_filter,
            min_similarity=threshold if threshold else None,
        )
        await conn.commit()

        if not leased:
            console.print("[yellow]No pending suggestions.[/yellow]")
            return

        sess = SuggestSession(leased)
        kb = KeyBindings()
        decision_keys = {"pair": PAIR_KEYS, "term": TERM_KEYS}

        @kb.add("b")
        def _(event):
            sess.go_back()
            event.app.exit(result="redraw")

        @kb.add("n")
        def _(event):
            sess.go_forward()
            event.app.exit(result="redraw")

        @kb.add("s")
        def _(event):
            event.app.exit(result="save")

        for ch in "1234":
            def _make(c=ch):
                def _h(event):
                    cur = sess.current()
                    if cur is None:
                        event.app.exit(result="redraw")
                        return
                    keymap = decision_keys[cur["kind"]]
                    if c not in keymap:
                        # Term suggestions only have 1-3; pressing 4 is a no-op.
                        event.app.exit(result="redraw")
                        return
                    sess.set_decision(keymap[c])
                    event.app.exit(result="redraw")
                return _h
            kb.add(ch)(_make())

        # Two distinct PromptSession instances:
        #   - `prompt_session`: holds the b/n/s/1-4 keybindings for the
        #     decision loop.
        #   - `confirm_session`: NO keybindings — for [y/N] confirmations
        #     where pressing 1/2/3/b would otherwise fire a stray decision
        #     handler against an unrelated suggestion (NEW-3 from review).
        prompt_session: PromptSession[str] = PromptSession(key_bindings=kb)
        confirm_session: PromptSession[str] = PromptSession()

        async def _confirm(message: str) -> str:
            console.print(message)
            try:
                return (await confirm_session.prompt_async("> ")).strip().lower()
            except (KeyboardInterrupt, EOFError):
                # Treat Ctrl+C inside a confirm prompt as a "no" to the
                # specific question (caller decides what that means).
                return ""

        while True:
            cur = sess.current()
            if cur is None:
                console.print("\n[cyan]All suggestions reviewed.[/cyan]")
                console.print("[s] 저장   [b] 이전 항목으로\n")
            else:
                if cur["kind"] == "pair":
                    canonical, aliases = await _fetch_group_context(
                        conn, cur.get("target_group_id")
                    )
                    panel = render_pair_panel(
                        sess, group_canonical=canonical, group_aliases=aliases,
                    )
                else:
                    panel = render_term_panel(sess)
                console.print(panel)

            try:
                action = await prompt_session.prompt_async("> ")
            except (KeyboardInterrupt, EOFError):
                # Treat Ctrl+C as a discard-with-confirm gesture.
                if sess.has_unsaved_decisions():
                    answer = await _confirm(
                        f"\n저장 안 한 결정 {len(sess.decisions)}개. 정말 버릴까? [y/N]"
                    )
                    if answer != "y":
                        # User declined to discard — keep going.
                        continue
                # Roll back any uncommitted writes (none expected, but
                # belt-and-suspenders) before releasing the lease.
                await conn.rollback()
                await release_lease(conn, leased_by=actor_id)
                await conn.commit()
                console.print("[yellow]Lease released.[/yellow]")
                return

            if action == "save":
                summary = sess.summary()
                console.print(render_save_summary(summary, total=len(leased)))
                # Use confirm_session (no keybindings) so '1' or 'b' here
                # does not fire a stray decision against the visible item.
                confirm = await _confirm("")
                if confirm == "y":
                    # save_decisions handles its own commit/rollback (B5).
                    # Wrap in BaseException catch so Ctrl+C mid-apply still
                    # releases the lease (SIG-1 from review).
                    try:
                        await save_decisions(conn, session=sess, actor_id=actor_id)
                    except BaseException:
                        await conn.rollback()
                        await release_lease(conn, leased_by=actor_id)
                        await conn.commit()
                        raise
                    console.print("[green]Saved.[/green]")
                    return
                console.print("[yellow]Save cancelled — continue editing.[/yellow]")
                continue
            # else: "redraw" — loop and re-render
    finally:
        await conn.close()


def register(app: typer.Typer) -> None:
    glossary_app = typer.Typer(name="glossary", help="Glossary recommendation queue")
    app.add_typer(glossary_app)

    @glossary_app.command("suggest")
    def suggest(
        project_id: str = typer.Option(
            None, "--project",
            help="Project id (default: project_id from .luplo workspace)",
        ),
        actor_id: str = typer.Option(
            None, "--actor",
            help="Actor id (default: actor_id from `lps login` keyring)",
        ),
        suggest_type: SuggestType = typer.Option(
            "all", "--type", help="all|pair|term",
        ),
        limit: int = typer.Option(20, "--limit"),
        threshold: float = typer.Option(0.85, "--threshold"),
    ) -> None:
        """Interactively review and persist glossary suggestions."""
        resolved_project = project_id or _resolve_default_project()
        if not resolved_project:
            raise typer.BadParameter(
                "--project not given and no .luplo workspace found in cwd or ancestors"
            )
        resolved_actor = actor_id or _resolve_default_actor()
        if not resolved_actor:
            raise typer.BadParameter(
                "--actor not given and no actor_id in keyring (run `lps login` first)"
            )
        asyncio.run(_run(resolved_project, resolved_actor, suggest_type, limit, threshold))
