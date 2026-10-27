"""FastAPI entry point.

Run locally:   uvicorn app.main:app --reload --port 8000
API docs:      http://localhost:8000/docs
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import database as db
from .config import settings
from .routes import history, jobs, system
from .services.storage import get_storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    db.mark_interrupted_jobs()
    s = get_storage().health()
    log.info("Storage backend: %s | ok=%s | %s", s.get("backend"), s.get("ok"), s.get("message"))
    log.info("Prediction engine: %s | CORS origins: %s", settings.prediction_engine, settings.cors_origins)
    yield
    db.close_db()


app = FastAPI(
    title="Cloud Protein Structure Prediction API",
    description="Protein sequence workflow (A -> B -> C..H in parallel -> I) with results stored in Amazon S3.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # exact frontend origins only, never "*" with credentials
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

app.include_router(jobs.router)
app.include_router(history.router)
app.include_router(system.router)


@app.get("/", include_in_schema=False)
def root():
    return {"message": "Protein prediction API is running. See /docs and /api/health."}
