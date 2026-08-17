import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import DEV_SECRET_KEY, settings
from app.core.database import engine, wait_for_database
from app.core.logging import RequestLogMiddleware, configure_logging
from app.core.schema import ensure_schema
from app.routes import (
    admin, auth, users, profiles, datasets, funding, trends, patents, technology,
    innovation, commercialization, notifications, reports,
)

log = logging.getLogger("app.startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Prepare the database at startup — not at import."""
    configure_logging()
    log.info("Starting in %s mode.", settings.ENVIRONMENT)
    if settings.SECRET_KEY == DEV_SECRET_KEY:
        log.warning(
            "SECRET_KEY is the development default from the repository. Anyone can "
            "forge a token for any account, including an administrator. Fine on a "
            "laptop; if this is a deployment, set SECRET_KEY and ENVIRONMENT=production."
        )
    if settings.is_production and settings.TRUSTED_PROXY_HOPS == 0:
        log.warning(
            "TRUSTED_PROXY_HOPS is 0 in production. If anything proxies this service "
            "— nginx, Render, a load balancer — every rate limit is keyed on an "
            "address the caller can set in a header, which switches them all off. "
            "Set it to the number of proxies in front of this process."
        )
    wait_for_database()
    applied = ensure_schema(engine)
    if applied:
        log.info("Schema updated: %s", ", ".join(applied))
    else:
        log.info("Schema already current.")
    yield
    engine.dispose()
    log.info("Shut down.")


app = FastAPI(
    title="Research Funding & Innovation Intelligence Platform",
    description="AI-powered innovation intelligence platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(RequestLogMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(profiles.router)
app.include_router(datasets.router)
app.include_router(funding.router)
app.include_router(trends.router)
app.include_router(patents.router)
app.include_router(technology.router)
app.include_router(innovation.router)
app.include_router(commercialization.router)
app.include_router(admin.router)
app.include_router(notifications.router)
app.include_router(reports.router)


@app.get("/")
def root():
    return {
        "message": "Innovation Intelligence Platform API",
        "docs": "/docs",
        "status": "running",
    }


@app.get("/health", tags=["health"])
def health():
    """Liveness: is this process answering?"""
    return {"status": "ok", "version": app.version}


@app.get("/health/ready", tags=["health"])
def readiness():
    """Readiness: can this process serve traffic?"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - the reason is reported, not swallowed
        log.warning("Readiness check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": "unreachable"},
        )
    return {"status": "ready", "database": "ok"}
