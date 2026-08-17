"""Startup, health probes and request correlation."""
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.logging import REQUEST_ID_HEADER, RequestLogMiddleware

DEAD_DB = "postgresql+psycopg://nobody:nothing@127.0.0.1:1/absent?connect_timeout=2"


def test_importing_the_app_does_not_touch_the_database(python_subprocess):
    result = python_subprocess(
        "import app.main; print('OK', app.main.app.version)",
        {"DATABASE_URL": DEAD_DB},
    )
    assert result.returncode == 0, (
        "Importing app.main required a database.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "OK" in result.stdout


def test_liveness_answers_without_a_database(python_subprocess):
    """`/health` must not depend on the database, or a blip gets the pod killed."""
    result = python_subprocess(
        "from fastapi.testclient import TestClient\n"
        "from app.main import app\n"
        "c = TestClient(app)\n"
        "live = c.get('/health')\n"
        "ready = c.get('/health/ready')\n"
        "print('LIVE', live.status_code, live.json()['status'])\n"
        "print('READY', ready.status_code, ready.json()['status'])\n",
        {"DATABASE_URL": DEAD_DB},
    )
    assert result.returncode == 0, result.stderr
    assert "LIVE 200 ok" in result.stdout, result.stdout
    assert "READY 503 unavailable" in result.stdout, result.stdout


def test_wait_for_database_gives_up_with_a_readable_error(python_subprocess):
    result = python_subprocess(
        "from app.core.database import wait_for_database\n"
        "try:\n"
        "    wait_for_database(attempts=2, backoff=0)\n"
        "except RuntimeError as exc:\n"
        "    print('RAISED', 'unreachable after 2 attempts' in str(exc))\n",
        {"DATABASE_URL": DEAD_DB},
    )
    assert result.returncode == 0, result.stderr
    assert "RAISED True" in result.stdout, result.stdout


def test_health_reports_the_running_version(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["version"], "the probe should name the build it is answering for"


def test_readiness_confirms_the_database(client):
    body = client.get("/health/ready").json()
    assert body == {"status": "ready", "database": "ok"}


def test_every_response_carries_a_request_id(client):
    response = client.get("/health")
    assert response.headers.get(REQUEST_ID_HEADER)


def test_an_inbound_request_id_is_kept(client):
    """So a trace started by nginx or a load balancer survives into these logs."""
    response = client.get("/health", headers={REQUEST_ID_HEADER: "edge-trace-1"})
    assert response.headers[REQUEST_ID_HEADER] == "edge-trace-1"


@pytest.fixture
def failing_app():
    """A minimal app with the real middleware and one route that raises."""
    app = FastAPI()
    app.add_middleware(RequestLogMiddleware)

    @app.get("/boom")
    def boom():
        raise RuntimeError("a deliberate fault")

    return TestClient(app, raise_server_exceptions=False)


def test_an_unhandled_error_returns_a_traceable_id_and_nothing_else(failing_app, caplog):
    with caplog.at_level(logging.ERROR):
        response = failing_app.get("/boom")

    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "Internal server error."
    assert body["request_id"] == response.headers[REQUEST_ID_HEADER]
    assert "deliberate fault" not in response.text
    assert "RuntimeError" not in response.text

    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "/boom" in logged, "the failure has to be recorded somewhere"
    assert any(r.exc_info for r in caplog.records), "with its traceback"


def test_handled_refusals_are_not_logged_as_failures(client, caplog):
    """A 401 is the application working."""
    with caplog.at_level(logging.ERROR):
        assert client.get("/api/auth/me").status_code == 401
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []
