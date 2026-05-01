def test_models_define_all_tables():
    from luplo_cloud.glossary_ext.models import (
        GlossaryGroupRelation,
        GlossaryHistory,
        GlossarySuggestion,
        GlossaryTermEmbedding,
        Job,
    )
    assert Job.__tablename__ == "jobs"
    assert GlossaryTermEmbedding.__tablename__ == "glossary_term_embeddings"
    assert GlossarySuggestion.__tablename__ == "glossary_suggestions"
    assert GlossaryGroupRelation.__tablename__ == "glossary_group_relations"
    assert GlossaryHistory.__tablename__ == "glossary_history"
