def test_can_import_glossary_ext_deps():
    import alembic  # noqa: F401
    import pgvector  # noqa: F401
    import prompt_toolkit  # noqa: F401
    import psycopg  # noqa: F401
    import rich  # noqa: F401
    import sqlalchemy  # noqa: F401
