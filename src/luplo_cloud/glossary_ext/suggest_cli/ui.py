"""Rendering helpers for `lps glossary suggest`.

Pure-string functions so tests can assert without a TTY. The interactive
loop (key handling) is in cli.py; these functions just produce the panel
text shown above the prompt.
"""
from __future__ import annotations

from luplo_cloud.glossary_ext.suggest_cli.session import SuggestSession

_KEY_HINT = "[b] 이전   [n] 다음   [s] 저장"


def _decision_label(s: SuggestSession, sid: str) -> str:
    d = s.decisions.get(sid)
    if not d:
        return "—"
    label = {
        "alias": "1 alias",
        "canonical_replace": "2 canonical 교체",
        "sibling": "3 sibling",
        "skip": "4 skip",
        "create": "1 생성",
        "reject": "3 영구 차단",
    }.get(d["decision"], d["decision"])
    return label


def render_pair_panel(
    session: SuggestSession,
    *,
    group_canonical: str,
    group_aliases: list[str],
) -> str:
    cur = session.current()
    if cur is None:
        return "(no current suggestion)"
    sid = cur["id"]
    pos = f"{session.cursor + 1}/{len(session.suggestions)}"
    sim = cur.get("similarity")
    sim_str = f"{sim:.2f}" if sim is not None else "—"
    src = cur.get("source_item_id") or "—"
    aliases_str = "\n".join(f"            ├ alias: {a}" for a in group_aliases) or ""
    decision_marker = _decision_label(session, sid)
    return (
        f"[Pair {pos}]                              [Decision: {decision_marker}]\n"
        f" 새 term:    {cur['candidate_surface']}\n"
        f" 기존 group: {group_canonical}  (canonical)\n"
        f"{aliases_str}\n"
        f" 유사도:     {sim_str}\n"
        f" 발견:       {src}\n"
        f"\n"
        f" [1] alias  [2] canonical 교체  [3] sibling  [4] skip\n"
        f" {_KEY_HINT}\n"
    )


def render_term_panel(session: SuggestSession) -> str:
    cur = session.current()
    if cur is None:
        return "(no current suggestion)"
    sid = cur["id"]
    pos = f"{session.cursor + 1}/{len(session.suggestions)}"
    src = cur.get("source_item_id") or "—"
    decision_marker = _decision_label(session, sid)
    return (
        f"[Term {pos}]                              [Decision: {decision_marker}]\n"
        f" term:       {cur['candidate_surface']}\n"
        f" 발견:       {src}\n"
        f"\n"
        f" [1] 생성  [2] 버림  [3] 영구 차단\n"
        f" {_KEY_HINT}\n"
    )


def render_save_summary(summary: dict[str, int], *, total: int) -> str:
    lines = ["저장 요약", "─" * 40]
    label_map = {
        "alias": "alias 추가",
        "canonical_replace": "canonical 교체",
        "sibling": "sibling 추가",
        "create": "신규 group 생성",
        "reject": "영구 차단",
        "skip": "skip (보류, DB 미반영)",
    }
    for key, label in label_map.items():
        n = summary.get(key, 0)
        if n:
            lines.append(f" {label:<24}  {n}")
    lines.append("─" * 40)
    lines.append(f"총 {total}개 항목 처리. 저장할까? [y/N]")
    return "\n".join(lines)
