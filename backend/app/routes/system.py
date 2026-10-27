"""Health check (including AWS status) and the sequential-vs-parallel benchmark."""
import platform

from fastapi import APIRouter, HTTPException

from ..config import settings
from ..models.schemas import BenchmarkRequest
from ..services.sequence import SequenceError, parse_sequence, validate_sequence
from ..services.storage import get_storage
from ..workflow.pipeline import run_benchmark

router = APIRouter(prefix="/api", tags=["system"])
ENGINE_LABELS = {"esmatlas": "ESMFold (Meta ESM Atlas API)", "nvidia": "ESMFold (NVIDIA hosted API)",
                 "none": "None - 3D prediction disabled"}


@router.get("/health", summary="Service health, storage (S3) status and configuration")
def health():
    storage = get_storage().health()
    engine = settings.prediction_engine
    return {
        "status": "ok" if storage.get("ok") else "degraded",
        "app_env": settings.app_env,
        "host": platform.node(),
        "storage": storage,
        "prediction_engine": {
            "id": engine,
            "label": ENGINE_LABELS.get(engine, f"Unknown ({engine})"),
            "genuine_prediction_available": engine in ("esmatlas", "nvidia")
            and (engine != "nvidia" or bool(settings.nvidia_api_key)),
        },
        "limits": {"min_length": settings.min_sequence_length, "max_length": settings.max_sequence_length,
                   "parallel_workers": settings.parallel_workers,
                   "default_demo_delay_seconds": settings.default_demo_delay_seconds,
                   "presigned_url_expiry_seconds": settings.presigned_url_expiry_seconds},
    }


@router.post("/benchmark", summary="Run tasks C-G sequentially and in parallel and compare times")
def benchmark(req: BenchmarkRequest):
    try:
        _, seq = parse_sequence(req.sequence)
        validate_sequence(seq, settings.min_sequence_length, settings.max_sequence_length)
    except SequenceError as exc:
        raise HTTPException(422, str(exc))
    return run_benchmark(seq, req.demo_delay_seconds)
