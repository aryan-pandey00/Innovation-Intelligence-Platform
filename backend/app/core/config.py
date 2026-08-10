from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg://postgres:password@localhost:5432/innovation_platform"
    SECRET_KEY: str = "change-this-secret-key-please"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # EPO Open Patent Services (developers.epo.org, non-paying tier).
    # Empty means "not configured" — patent code must degrade, never crash.
    OPS_CONSUMER_KEY: str = ""
    OPS_CONSUMER_SECRET: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
