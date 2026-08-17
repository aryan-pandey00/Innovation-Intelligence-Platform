"""Settings, and the checks that stop a misconfigured deployment from starting."""
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET_KEY = "change-this-secret-key-please"
_MIN_SECRET_LEN = 32

# Absolute on purpose: a relative env_file follows the working directory, so starting
# elsewhere silently falls back to every default here — including the signing key.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    # extra="ignore" is load-bearing: compose passes the whole environment in.
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    ENVIRONMENT: str = "development"

    DATABASE_URL: str = "postgresql+psycopg://postgres:password@localhost:5432/innovation_platform"
    SECRET_KEY: str = DEV_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    CORS_ORIGINS: str = ("http://localhost:3000,http://127.0.0.1:3000,"
                         "http://localhost:5173,http://127.0.0.1:5173")

    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False

    # 0 only when nothing proxies this. Behind one, raise it or every rate limit keys
    # on a header the caller writes. compose sets 1.
    TRUSTED_PROXY_HOPS: int = 0

    LOGIN_MAX_ATTEMPTS: int = 10
    LOGIN_WINDOW_SECONDS: int = 300
    REGISTER_MAX_ATTEMPTS: int = 20
    REGISTER_WINDOW_SECONDS: int = 3600

    DB_CONNECT_ATTEMPTS: int = 10
    DB_CONNECT_BACKOFF_SECONDS: float = 1.5
    DB_CONNECT_TIMEOUT_SECONDS: int = 10

    OPS_CONSUMER_KEY: str = ""
    OPS_CONSUMER_SECRET: str = ""

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() in {"production", "prod"}

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def _normalise_database_url(self) -> "Settings":
        url = self.DATABASE_URL.strip()
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        object.__setattr__(self, "DATABASE_URL", url)
        return self

    @model_validator(mode="after")
    def _refuse_insecure_production(self) -> "Settings":
        if not self.is_production:
            return self
        if self.SECRET_KEY == DEV_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY is still the development default. Generate one with "
                "`python -c \"import secrets; print(secrets.token_urlsafe(48))\"` "
                "and set it in the environment before starting in production."
            )
        if len(self.SECRET_KEY) < _MIN_SECRET_LEN:
            raise ValueError(
                f"SECRET_KEY is {len(self.SECRET_KEY)} characters; "
                f"production requires at least {_MIN_SECRET_LEN}."
            )
        return self


settings = Settings()
