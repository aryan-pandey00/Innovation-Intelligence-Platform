"""Fixtures for the test suite."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import main as app_module                   # noqa: E402
from app.core import schema as schema_module          # noqa: E402
from app.core.config import settings                 # noqa: E402
from app.core.database import Base, get_db           # noqa: E402
from app.core.security import hash_password          # noqa: E402
from app.models.funding import FundingOpportunity    # noqa: E402
from app.models.research_profile import ResearchProfile  # noqa: E402
from app.models.user import User, UserRole           # noqa: E402

_SKIP_REASON = (
    "PostgreSQL is not reachable at the configured DATABASE_URL. The suite needs it: "
    "the schema uses JSONB and the code uses Postgres-only INSERT ... ON CONFLICT. "
    "Start Postgres, or set TEST_DATABASE_URL, then re-run."
)


def _render(url) -> str:
    """Serialise a URL with its password intact."""
    return url.render_as_string(hide_password=False)


def _test_database_url() -> str:
    """The test database URL: explicit if given, otherwise `<configured>_test`."""
    override = os.getenv("TEST_DATABASE_URL")
    if override:
        return override
    url = make_url(settings.DATABASE_URL)
    return _render(url.set(database=f"{url.database}_test"))


def _admin_url(url_str: str) -> str:
    """A URL for the maintenance database, since you cannot drop the one you are in."""
    return _render(make_url(url_str).set(database="postgres"))


def _drop(conn, name: str) -> None:
    """Drop the test database, evicting stragglers where the server can."""
    try:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    except ProgrammingError:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))


@pytest.fixture(scope="session")
def engine():
    """A freshly created test database with the current schema, dropped afterwards."""
    url = _test_database_url()
    name = make_url(url).database

    if name == make_url(settings.DATABASE_URL).database:
        pytest.fail("The test database must not be the configured application "
                    f"database ({name}). Set TEST_DATABASE_URL.")

    admin = create_engine(_admin_url(url), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            _drop(conn, name)
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    except OperationalError:
        pytest.skip(_SKIP_REASON)
    finally:
        admin.dispose()

    eng = create_engine(url, pool_pre_ping=True)
    schema_module.ensure_schema(eng)
    yield eng
    eng.dispose()

    admin = create_engine(_admin_url(url), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        _drop(conn, name)
    admin.dispose()


@pytest.fixture(scope="session")
def _sessionmaker(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _truncate(engine) -> None:
    tables = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture(autouse=True)
def _fresh_attempt_counters():
    """Forget the sign-in counters between tests."""
    from app.core import ratelimit

    ratelimit.reset_all()
    yield
    ratelimit.reset_all()


@pytest.fixture
def db(engine, _sessionmaker):
    session = _sessionmaker()
    try:
        yield session
    finally:
        session.close()
        _truncate(engine)


@pytest.fixture
def client(db):
    """A TestClient sharing the test's session, with the lifespan deliberately unused."""
    from fastapi.testclient import TestClient

    from app.main import app

    def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


def api_routes():
    """Every `APIRoute` the application actually serves."""
    seen = []
    for route in app_module.app.routes:
        if isinstance(route, APIRoute):
            seen.append(route)
        original = getattr(route, "original_router", None)
        if original is not None:
            seen.extend(r for r in original.routes if isinstance(r, APIRoute))
    return seen


def make_user(db, email: str, role: UserRole = UserRole.RESEARCHER, *,
              full_name: str | None = None, superuser: bool = False,
              password: str = "test-password-123") -> User:
    user = User(
        email=email,
        full_name=full_name or email.split("@")[0].replace(".", " ").title(),
        hashed_password=hash_password(password),
        role=role,
        original_role=role,
        is_superuser=superuser,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_profile(db, user: User, *, domains=None, keywords=None,
                 technology_areas=None, country: str = "United States",
                 organization: str = "Test University") -> ResearchProfile:
    profile = ResearchProfile(
        user_id=user.id,
        headline="Test profile",
        research_domains=domains if domains is not None else ["energy"],
        keywords=keywords if keywords is not None else ["battery", "storage"],
        technology_areas=(technology_areas if technology_areas is not None
                          else ["energy storage"]),
        organization=organization,
        organization_type="university",
        country=country,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def make_opportunity(db, *, title="Test Grant", agency="Test Agency",
                     source_type="government_grant", description="A grant for testing.",
                     domains=None, keywords=None, eligible_roles=None, countries=None,
                     amount_min=10_000, amount_max=100_000, deadline=None,
                     created_at=None) -> FundingOpportunity:
    opp = FundingOpportunity(
        title=title, agency=agency, source_type=source_type, description=description,
        domains=domains if domains is not None else ["energy"],
        keywords=keywords if keywords is not None else ["battery", "storage"],
        eligible_roles=(eligible_roles if eligible_roles is not None
                        else ["researcher", "startup_founder"]),
        countries=countries if countries is not None else [],
        amount_min=amount_min, amount_max=amount_max, currency="USD",
        deadline=deadline,
    )
    if created_at is not None:
        opp.created_at = created_at
    db.add(opp)
    db.commit()
    db.refresh(opp)
    return opp


SECURITY_QUESTIONS = [
    {"question": "What was the name of your first school?", "answer": "St Xavier"},
    {"question": "In what town or city were you born?", "answer": "Delhi"},
]


def registration(**overrides) -> dict:
    """A valid registration payload, with whatever the test wants changed."""
    return {
        "email": "new.person@example.org",
        "full_name": "New Person",
        "password": "a-good-password-1",
        "role": "researcher",
        "security_questions": SECURITY_QUESTIONS,
        **overrides,
    }


def auth_header(client, email: str, password: str = "test-password-123") -> dict:
    """Log in over HTTP rather than minting a token directly."""
    response = client.post("/api/auth/login",
                           data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def python_subprocess():
    """Run a snippet in a fresh interpreter with the backend importable."""
    def run(code: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
        env = {**os.environ, "PYTHONPATH": str(BACKEND_ROOT)}
        env.update(env_extra or {})
        return subprocess.run([sys.executable, "-c", code], capture_output=True,
                              text=True, cwd=str(BACKEND_ROOT), env=env, timeout=120)
    return run
