from luplo_cloud.glossary_ext.suggest_cli.session import SuggestSession
from luplo_cloud.glossary_ext.suggest_cli.ui import (
    render_pair_panel,
    render_save_summary,
    render_term_panel,
)


def test_render_pair_panel_includes_options():
    sess = SuggestSession([{
        "id": "s1", "kind": "pair", "candidate_surface": "QPS 제한",
        "candidate_normalized": "qps 제한", "target_group_id": "g1",
        "similarity": 0.91, "source_item_id": "item-1", "context_snippet": None,
    }])
    text = render_pair_panel(sess, group_canonical="rate limit", group_aliases=[])
    assert "[1] alias" in text
    assert "[2] canonical" in text
    assert "[3] sibling" in text
    assert "[4] skip" in text
    assert "[b] 이전" in text
    assert "[s] 저장" in text
    assert "QPS 제한" in text
    assert "0.91" in text


def test_render_term_panel_includes_3_options():
    sess = SuggestSession([{
        "id": "s2", "kind": "term", "candidate_surface": "디폴트 방향",
        "candidate_normalized": "디폴트 방향", "target_group_id": None,
        "similarity": None, "source_item_id": None, "context_snippet": None,
    }])
    text = render_term_panel(sess)
    assert "[1] 생성" in text
    assert "[2] 버림" in text
    assert "[3] 영구 차단" in text
    assert "디폴트 방향" in text


def test_render_save_summary_lists_counts():
    summary = {"alias": 7, "canonical_replace": 1, "sibling": 2, "skip": 2}
    text = render_save_summary(summary, total=12)
    assert "alias 추가" in text
    assert " 7" in text
    assert "총 12" in text
