import logging
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

log = logging.getLogger("app.database")

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args={"connect_timeout": settings.DB_CONNECT_TIMEOUT_SECONDS},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def wait_for_database(
    attempts: int | None = None,
    backoff: float | None = None,
) -> None:
    """Block until the database answers, or raise after the last attempt."""
    attempts = attempts if attempts is not None else settings.DB_CONNECT_ATTEMPTS
    backoff = backoff if backoff is not None else settings.DB_CONNECT_BACKOFF_SECONDS

    last: Exception | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            if attempt > 1:
                log.info("Database reachable after %s attempts.", attempt)
            return
        except OperationalError as exc:
            last = exc
            if attempt == attempts:
                break
            log.warning("Database not ready (attempt %s/%s); retrying in %.1fs.",
                        attempt, attempts, backoff)
            time.sleep(backoff)
    raise RuntimeError(
        f"Database unreachable after {attempts} attempts: {last}"
    ) from last
