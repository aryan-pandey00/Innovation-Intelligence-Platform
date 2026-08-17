"""Bring the database up to the current schema."""
from app.core.database import engine
from app.core.schema import ensure_schema


def main() -> None:
    applied = ensure_schema(engine)
    if applied:
        print("Added: " + ", ".join(applied))
    else:
        print("Schema already up to date.")


if __name__ == "__main__":
    main()
