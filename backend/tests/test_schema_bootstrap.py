"""The schema bootstrap, which is what stands in for a migration tool."""
from sqlalchemy import inspect, text

from app.core.schema import _ADDED_COLUMNS, ensure_schema

EXPECTED_TABLES = {
    "users", "research_profiles", "publications", "patents",
    "funding_opportunities", "audit_events", "notifications", "topic_readings",
}


def test_the_whole_schema_appears_in_one_pass(engine):
    """The session fixture created this database from nothing but `ensure_schema`."""
    present = set(inspect(engine).get_table_names())
    missing = EXPECTED_TABLES - present
    assert not missing, f"tables absent after bootstrap: {sorted(missing)}"


def test_running_it_again_changes_nothing(engine):
    """Idempotence, stated as a return value rather than as an absence of errors."""
    assert ensure_schema(engine) == []
    assert ensure_schema(engine) == []


def test_the_columns_added_after_their_table_shipped_are_present(engine):
    """`create_all` would have skipped every one of these on an existing database."""
    inspector = inspect(engine)
    for table, column, _spec in _ADDED_COLUMNS:
        names = {c["name"] for c in inspector.get_columns(table)}
        assert column in names, f"{table}.{column} missing"


def test_a_dropped_column_is_restored_rather_than_reported_absent(engine):
    """The case the function exists for, reproduced directly."""
    table, column, _ = _ADDED_COLUMNS[0]
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} DROP COLUMN {column}"))

    assert f"{table}.{column}" in ensure_schema(engine)
    names = {c["name"] for c in inspect(engine).get_columns(table)}
    assert column in names


def test_the_notification_deduplication_constraint_exists_by_name(engine):
    """`emit()` names this constraint in an ON CONFLICT clause."""
    names = {c["name"] for c in inspect(engine).get_unique_constraints("notifications")}
    assert "uq_notification_user_key" in names
