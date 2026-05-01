"""In-memory state for an interactive `lps glossary suggest` session.

Decisions are kept in a dict keyed by suggestion id. Pressing 1-4 (or
1-3 for term) advances the cursor; pressing `b` rewinds; pressing the
same number again overwrites the prior decision. Save / cancel are
external actions on top of this state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SuggestSession:
    suggestions: list[dict[str, Any]]
    cursor: int = 0
    decisions: dict[str, dict[str, Any]] = field(default_factory=dict)
    extra: dict[str, dict[str, Any]] = field(default_factory=dict)

    def current(self) -> dict[str, Any] | None:
        if 0 <= self.cursor < len(self.suggestions):
            return self.suggestions[self.cursor]
        return None

    def set_decision(self, decision: str, **extra: Any) -> None:
        cur = self.current()
        if cur is None:
            return
        sid = cur["id"]
        payload: dict[str, Any] = {"decision": decision}
        if extra:
            payload.update(extra)
        self.decisions[sid] = payload
        self.cursor += 1

    def go_back(self) -> None:
        if self.cursor > 0:
            self.cursor -= 1

    def go_forward(self) -> None:
        if self.cursor < len(self.suggestions):
            self.cursor += 1

    def summary(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for d in self.decisions.values():
            out[d["decision"]] = out.get(d["decision"], 0) + 1
        return out

    _PERSISTING_DECISIONS = frozenset(
        {"alias", "canonical_replace", "sibling", "create", "reject"}
    )

    def has_unsaved_decisions(self) -> bool:
        """True only if at least one decision will write to the DB on save.

        `skip` decisions persist nothing — they're free to abandon.
        """
        return any(
            d["decision"] in self._PERSISTING_DECISIONS
            for d in self.decisions.values()
        )

    def to_apply_payload(self) -> list[dict[str, Any]]:
        return [
            {"suggestion_id": sid, **data}
            for sid, data in self.decisions.items()
        ]
