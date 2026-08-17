"""Schema convergence, for a project with no migration tool."""
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core.database import Base

from app.models import (  # noqa: F401
    audit, funding, notification, password_reset, research_profile, user,
)

_ADDED_COLUMNS: list[tuple[str, str, str]] = [
    ("users", "is_superuser", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("notifications", "occurred_at", "TIMESTAMPTZ"),
    ("notifications", "dismissed_at", "TIMESTAMPTZ"),
    ("users", "password_changed_at", "TIMESTAMPTZ"),
    ("password_reset_requests", "claim_hash", "TEXT"),
    ("password_reset_requests", "approved_at", "TIMESTAMPTZ"),
    ("password_reset_requests", "answered_at", "TIMESTAMPTZ"),
    ("password_reset_requests", "answer_summary", "TEXT"),
    ("password_reset_requests", "answers_matched", "INTEGER"),
    ("password_reset_requests", "had_questions", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("password_reset_requests", "appeal_message", "TEXT"),
]

_DROPPED_COLUMNS: list[tuple[str, str, str]] = [
    ("password_reset_requests", "code_hash",
     "replaced by claim_hash; the code flow it served was never released"),
]


def ensure_schema(engine: Engine) -> list[str]:
    """Create missing tables, then add missing columns."""
    Base.metadata.create_all(bind=engine)

    applied: list[str] = []
    with engine.begin() as conn:
        for table, column, spec in _ADDED_COLUMNS:
            present = conn.execute(text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ), {"t": table, "c": column}).first()
            if present:
                continue
            conn.execute(text(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {spec}"))
            applied.append(f"{table}.{column}")

        for table, column, _why in _DROPPED_COLUMNS:
            present = conn.execute(text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ), {"t": table, "c": column}).first()
            if not present:
                continue
            conn.execute(text(
                f"ALTER TABLE {table} DROP COLUMN IF EXISTS {column}"))
            applied.append(f"-{table}.{column}")
    return applied
