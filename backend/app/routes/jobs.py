"""Prediction job endpoints: submit, poll task status, read results, download files."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, Response

from .. import database as db
from ..config import settings
from ..models.schemas import PredictRequest
from ..services.sequence import SequenceError, parse_sequence, validate_sequence
from ..services.storage import CONTENT_TYPES, StorageError, get_storage
from ..workflow.pipeline import create_and_submit

router = APIRouter(prefix="/api", tags=["prediction"])
TASK_ORDER = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "UPLOAD"]


def _job_or_404(job_id: str) -> dict:
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found.")
    return job


def _ordered_tasks(tasks: dict) -> list:
    return [tasks[t] for t in TASK_ORDER if t in tasks]


@router.post("/predict", status_code=202, summary="Submit a protein sequence; returns a job ID")
def predict(req: PredictRequest):
    try:
        name, seq = parse_sequence(req.sequence)
        validate_sequence(seq, settings.min_sequence_length, settings.max_sequence_length)
    except SequenceError as exc:
        raise HTTPException(422, str(exc))
    delay = settings.default_demo_delay_seconds if req.demo_delay_seconds is None else req.demo_delay_seconds
    job_id = create_and_submit(req.name or name, seq, req.execution_mode, delay)
    return {"job_id": job_id, "status": "queued", "execution_mode": req.execution_mode,
            "demo_delay_seconds": delay}


@router.get("/tasks/{job_id}", summary="Task statuses and progress for a job")
def tasks(job_id: str):
    job = _job_or_404(job_id)
    task_list = _ordered_tasks(job["tasks"] or {})
    done = sum(t["status"] in ("completed", "failed", "skipped") for t in task_list)
    return {"job_id": job_id, "name": job["name"], "status": job["status"], "error": job["error"],
            "execution_mode": job["execution_mode"], "demo_delay_seconds": job["demo_delay_seconds"],
            "progress_percent": round(100 * done / len(task_list)) if task_list else 0,
            "tasks": task_list, "total_seconds": job["total_seconds"], "metrics": job["metrics"]}


@router.get("/results/{job_id}", summary="Final report, metrics and stored files")
def results(job_id: str):
    job = _job_or_404(job_id)
    return {"job_id": job_id, "name": job["name"], "status": job["status"], "error": job["error"],
            "execution_mode": job["execution_mode"], "created_at": job["created_at"],
            "finished_at": job["finished_at"], "total_seconds": job["total_seconds"],
            "tasks": _ordered_tasks(job["tasks"] or {}), "metrics": job["metrics"],
            "report": job["result"], "files": job["files"] or [], "storage_errors": job["storage_errors"] or []}


@router.get("/results/{job_id}/downloads", summary="Fresh download links (S3 presigned URLs)")
def downloads(job_id: str):
    job = _job_or_404(job_id)
    links = []
    for rec in job["files"] or []:
        item = {"filename": rec["filename"], "backend": rec["backend"], "size_bytes": rec.get("size_bytes")}
        try:
            item.update(get_storage().download_url(job_id, rec))
        except StorageError as exc:
            item["error"] = str(exc)
        links.append(item)
    return {"job_id": job_id, "files": links}


@router.get("/results/{job_id}/structure", response_class=PlainTextResponse,
            summary="Predicted structure text for the 3D viewer")
def structure(job_id: str, format: str = "pdb"):
    job = _job_or_404(job_id)
    filename = "structure.cif" if format == "cif" else "structure.pdb"
    rec = next((f for f in job["files"] or [] if f["filename"] == filename), None)
    if not rec:
        raise HTTPException(404, "No predicted 3D structure exists for this job.")
    try:
        return PlainTextResponse(get_storage().read(job_id, rec).decode("utf-8"))
    except StorageError as exc:
        raise HTTPException(503, f"Could not read structure from storage: {exc}")


@router.get("/files/{job_id}/{filename}", summary="Download a locally stored file (local mode only)")
def local_file(job_id: str, filename: str):
    job = _job_or_404(job_id)
    rec = next((f for f in job["files"] or [] if f["filename"] == filename and f["backend"] == "local"), None)
    if not rec:
        raise HTTPException(404, "File not found in local storage.")
    try:
        data = get_storage().local.read(job_id, filename)
    except StorageError as exc:
        raise HTTPException(404, str(exc))
    ctype = CONTENT_TYPES.get("." + filename.rsplit(".", 1)[-1], "application/octet-stream")
    return Response(data, media_type=ctype,
                    headers={"Content-Disposition": f'attachment; filename="{job_id[:8]}_{filename}"'})
