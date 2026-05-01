from luplo_cloud.glossary_ext.suggest_cli.session import SuggestSession


def test_session_records_decision_and_overwrites_on_back():
    suggestions = [
        {"id": "s1", "kind": "pair", "candidate_surface": "QPS 제한"},
        {"id": "s2", "kind": "pair", "candidate_surface": "throttling"},
    ]
    sess = SuggestSession(suggestions)
    sess.set_decision("alias")
    assert sess.cursor == 1  # auto-advanced
    sess.set_decision("skip")
    assert sess.cursor == 2  # past the end
    sess.go_back()
    assert sess.cursor == 1
    sess.set_decision("alias")  # overwrite skip
    assert sess.decisions["s2"]["decision"] == "alias"
    summary = sess.summary()
    assert summary["alias"] == 2


def test_session_skip_keeps_no_consumed_state():
    suggestions = [{"id": "s1", "kind": "term", "candidate_surface": "x"}]
    sess = SuggestSession(suggestions)
    sess.set_decision("skip")
    assert sess.decisions["s1"]["decision"] == "skip"
    assert sess.summary()["skip"] == 1
