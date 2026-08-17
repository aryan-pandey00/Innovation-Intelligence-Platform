"""Security properties that are cheap to assert and expensive to lose."""
import json
import re

import pytest

from app.core.config import settings
from app.models.user import UserRole
from app.services import data_health
from tests.conftest import api_routes, auth_header, make_user

PUBLIC = {
    ("/", "GET"),
    ("/health", "GET"),
    ("/health/ready", "GET"),
    ("/api/auth/register", "POST"),
    ("/api/auth/login", "POST"),
    ("/api/auth/password/forgot", "POST"),
    ("/api/auth/password/answers", "POST"),
    ("/api/auth/password/appeal", "POST"),
    ("/api/auth/password/status", "GET"),
    ("/api/auth/password/reset", "POST"),
    ("/docs", "GET"), ("/redoc", "GET"), ("/openapi.json", "GET"),
    ("/docs/oauth2-redirect", "GET"),
}

_PARAM_VALUES = {"kind": "funding"}

_ANY_PARAM = re.compile(r"\{[^}]+\}")


def _callable_routes():
    for route in api_routes():
        path = route.path
        for name, value in _PARAM_VALUES.items():
            path = path.replace("{" + name + "}", value)
        path = _ANY_PARAM.sub("1", path)
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            yield route.path, path, method


def test_the_route_census_is_not_empty(client):
    """The census has to be able to fail before it means anything."""
    census = {(declared, method) for declared, _, method in _callable_routes()}
    assert len(census) >= 50, (
        f"the census found only {len(census)} routes — it is not walking the "
        "application's real surface")
    for expected in (("/api/users/all", "GET"), ("/api/admin/data-health", "GET")):
        assert expected in census, f"{expected} is served but absent from the census"


def test_every_api_route_requires_a_token_unless_it_is_listed_as_public(client):
    """A census, not a spot check."""
    open_routes = []
    for declared, path, method in _callable_routes():
        if (declared, method) in PUBLIC:
            continue
        response = client.request(method, path)
        if response.status_code != 401:
            open_routes.append(f"{method} {declared} -> {response.status_code}")
    assert not open_routes, ("these routes answered an unauthenticated caller:\n"
                            + "\n".join(open_routes))


def test_the_public_surface_is_actually_public(client):
    """The other direction: a login page that needs a token cannot be logged into."""
    for path, method in [("/", "GET"), ("/health", "GET"), ("/openapi.json", "GET")]:
        assert client.request(method, path).status_code == 200, path


def test_the_data_health_report_never_exposes_the_api_credentials(client, db,
                                                                  monkeypatch):
    """Configured is a boolean."""
    monkeypatch.setattr(settings, "OPS_CONSUMER_KEY", "AbCdEfGhIjKlMnOpQrSt")
    monkeypatch.setattr(settings, "OPS_CONSUMER_SECRET", "ZyXwVuTsRqPoNmLkJiHg")

    payload = json.dumps(data_health.data_health(db))
    for secret in (settings.OPS_CONSUMER_KEY, settings.OPS_CONSUMER_SECRET):
        assert secret not in payload
        for length in (4, 6, 8):
            assert secret[:length] not in payload, (
                f"the first {length} characters of a credential appear in the payload")

    make_user(db, "admin@example.org", UserRole.ADMIN)
    response = client.get("/api/admin/data-health",
                          headers=auth_header(client, "admin@example.org"))
    assert response.status_code == 200
    for source in response.json()["sources"]:
        assert isinstance(source["configured"], bool)


@pytest.mark.parametrize("role", [UserRole.RESEARCHER, UserRole.STARTUP_FOUNDER,
                                  UserRole.INNOVATION_MANAGER])

def test_data_health_is_for_administrators_only(client, db, role):
    make_user(db, "caller@example.org", role)
    assert client.get("/api/admin/data-health",
                      headers=auth_header(client, "caller@example.org")
                      ).status_code == 403


def test_data_health_makes_no_network_call(client, db, monkeypatch):
    """The endpoint exists so a rate-limited source cannot take a dashboard down."""
    import httpx

    def refuse(*args, **kwargs):
        raise AssertionError("data_health attempted a network request")

    monkeypatch.setattr(httpx.Client, "request", refuse)
    monkeypatch.setattr(httpx.AsyncClient, "request", refuse)
    assert data_health.data_health(db)["sources"]


def test_an_error_response_does_not_describe_the_error(client, db):
    """Details belong in the log, which has the request id to find them by."""
    make_user(db, "owner@example.org", UserRole.RESEARCHER)
    response = client.get("/api/funding/recommendations",
                          headers=auth_header(client, "owner@example.org"))
    assert response.status_code == 400
    body = response.text.lower()
    for leak in ("traceback", "sqlalchemy", "psycopg", "select ", "app/"):
        assert leak not in body


def test_no_route_under_api_admin_answers_an_ordinary_account(client, db):
    """The other half of the census."""
    make_user(db, "ordinary@example.org", UserRole.RESEARCHER)
    headers = auth_header(client, "ordinary@example.org")

    reached, checked = [], 0
    for declared, path, method in _callable_routes():
        if not declared.startswith("/api/admin"):
            continue
        checked += 1
        response = client.request(method, path, headers=headers, json={})
        if response.status_code not in (403, 404):
            reached.append(f"{method} {declared} -> {response.status_code}")

    assert checked >= 5, (
        f"only {checked} admin routes were walked — the census is not seeing them")
    assert not reached, ("a researcher reached these administrator routes:\n"
                         + "\n".join(reached))


def test_cors_grants_only_the_configured_origins(client):
    allowed = settings.cors_origins[0]
    response = client.get("/health", headers={"Origin": allowed})
    assert response.headers.get("access-control-allow-origin") == allowed

    hostile = client.get("/health", headers={"Origin": "https://attacker.example"})
    assert "access-control-allow-origin" not in hostile.headers
