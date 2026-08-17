"""Configuration: the URL rewriting and the refusals that keep a deployment honest."""
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import DEV_SECRET_KEY, Settings
from tests.conftest import BACKEND_ROOT

GOOD_KEY = "k" * 48


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


@pytest.mark.parametrize("given", [
    "postgres://u:p@h:5432/db",
    "postgresql://u:p@h:5432/db",
    "postgresql+psycopg://u:p@h:5432/db",
])

def test_every_postgres_url_form_reaches_the_installed_driver(given):
    assert _settings(DATABASE_URL=given).DATABASE_URL == "postgresql+psycopg://u:p@h:5432/db"


def test_a_non_postgres_url_is_left_untouched():
    """The rewrite is targeted, not a blanket string replacement."""
    url = "sqlite:///./local.db"
    assert _settings(DATABASE_URL=url).DATABASE_URL == url


def test_production_refuses_the_secret_key_that_ships_in_the_repository():
    with pytest.raises(ValidationError) as caught:
        _settings(ENVIRONMENT="production", SECRET_KEY=DEV_SECRET_KEY)
    assert "SECRET_KEY" in str(caught.value)
    assert "token_urlsafe" in str(caught.value)


def test_production_refuses_a_short_secret_key():
    with pytest.raises(ValidationError) as caught:
        _settings(ENVIRONMENT="production", SECRET_KEY="tooshort")
    assert "at least 32" in str(caught.value)


def test_production_accepts_a_real_key():
    assert _settings(ENVIRONMENT="production", SECRET_KEY=GOOD_KEY).is_production


def test_development_still_starts_with_the_repository_key():
    """Otherwise a fresh clone could not be run at all, which nobody would accept."""
    assert _settings(ENVIRONMENT="development", SECRET_KEY=DEV_SECRET_KEY).SECRET_KEY


@pytest.mark.parametrize("value,expected", [
    ("production", True), ("prod", True), ("PRODUCTION", True),
    ("development", False), ("staging", False), ("", False),
])

def test_production_is_recognised_however_it_is_spelled(value, expected):
    assert _settings(ENVIRONMENT=value, SECRET_KEY=GOOD_KEY).is_production is expected


def test_cors_origins_parse_from_a_plain_comma_list():
    """A list-typed setting would make pydantic demand JSON, which no dashboard emits."""
    settings = _settings(CORS_ORIGINS=" https://a.example , https://b.example ,, ")
    assert settings.cors_origins == ["https://a.example", "https://b.example"]


def test_unrelated_environment_variables_do_not_stop_startup():
    """compose passes the whole environment in, POSTGRES_PASSWORD included."""
    assert _settings(POSTGRES_PASSWORD="irrelevant").SECRET_KEY == DEV_SECRET_KEY


def test_the_env_file_is_found_from_any_working_directory(tmp_path):
    """Where the process was launched from must not decide what it is configured with."""
    import json
    import subprocess
    import sys

    env_file = Settings.model_config["env_file"]
    assert Path(env_file).is_absolute(), (
        f"env_file is {env_file!r}, which pydantic resolves against the working "
        "directory — so the settings depend on where the server was launched from."
    )

    probe = (
        "import json, sys;"
        f"sys.path.insert(0, {str(BACKEND_ROOT)!r});"
        "from app.core.config import Settings, DEV_SECRET_KEY;"
        "s = Settings();"
        "print(json.dumps({'dev_key': s.SECRET_KEY == DEV_SECRET_KEY,"
        " 'db': s.DATABASE_URL, 'env': s.ENVIRONMENT}))"
    )

    def load_from(cwd) -> dict:
        out = subprocess.run([sys.executable, "-c", probe], cwd=str(cwd),
                             capture_output=True, text=True, timeout=120)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout.strip().splitlines()[-1])

    assert load_from(BACKEND_ROOT) == load_from(tmp_path)
