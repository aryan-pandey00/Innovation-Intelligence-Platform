from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine, Base
from app.routes import (
    auth, users, profiles, datasets, funding, trends, patents, technology,
    innovation, commercialization,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Research Funding & Innovation Intelligence Platform",
    description="AI-powered innovation intelligence platform",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:5173", "http://127.0.0.1:5173",
    ],
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


@app.get("/")
def root():
    return {
        "message": "Innovation Intelligence Platform API",
        "docs": "/docs",
        "status": "running",
    }
