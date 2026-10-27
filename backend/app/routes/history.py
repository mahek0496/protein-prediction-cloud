"""Prediction history stored in SQLite."""
from fastapi import APIRouter, HTTPException

from .. import database as db
from ..services.storage import get_storage

router = APIRouter(prefix="/api", tags=["history"])


@router.get("/history", summary="Previous prediction runs")
def history(limit: int = 50):
    rows = db.list_jobs(min(max(limit, 1), 200))
    for r in rows:
        files = r.pop("files", None) or []
        r["storage"] = sorted({f["backend"] for f in files})
        r["file_count"] = len(files)
    return {"items": rows}


@router.delete("/history/{job_id}", summary="Delete a run and its stored files")
def delete_history(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found.")
    if job["status"] in ("queued", "running"):
        raise HTTPException(409, "This job is still running; wait for it to finish before deleting.")
    errors = get_storage().delete_files(job_id, job["files"] or [])
    db.delete_job(job_id)
    return {"deleted": job_id, "storage_errors": errors}
