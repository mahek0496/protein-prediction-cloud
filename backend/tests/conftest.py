"""Test setup: isolated temp database/storage, no real AWS, no real ESMFold calls."""
import os
import tempfile
import time

import pytest

_tmp = tempfile.mkdtemp(prefix="protein-tests-")
os.environ.update({
    "DATABASE_PATH": os.path.join(_tmp, "test.db"),
    "LOCAL_STORAGE_DIR": os.path.join(_tmp, "files"),
    "PREDICTION_ENGINE": "none",
    "STORAGE_BACKEND": "local",
    "S3_BUCKET_NAME": "",
    "DEMO_TASK_DELAY_SECONDS": "0",
    "AWS_REGION": "us-east-1",
})

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.services.storage import reset_storage  # noqa: E402

UBIQUITIN = ("MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG")


def fake_pdb(seq: str, plddt: float = 0.85) -> str:
    """Minimal CA-only PDB used ONLY in tests to stand in for an ESMFold response."""
    three = {"A": "ALA", "R": "ARG", "N": "ASN", "D": "ASP", "C": "CYS", "Q": "GLN", "E": "GLU", "G": "GLY",
             "H": "HIS", "I": "ILE", "L": "LEU", "K": "LYS", "M": "MET", "F": "PHE", "P": "PRO", "S": "SER",
             "T": "THR", "W": "TRP", "Y": "TYR", "V": "VAL"}
    lines = [f"ATOM  {i:5d}  CA  {three[a]} A{i:4d}    {3.8 * i:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00{plddt:6.2f}           C"
             for i, a in enumerate(seq, start=1)]
    return "\n".join(lines + ["END"]) + "\n"


@pytest.fixture
def client():
    reset_storage()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def restore_settings():
    saved = dict(vars(settings))
    yield settings
    vars(settings).update(saved)
    reset_storage()


def wait_for_job(client, job_id, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/tasks/{job_id}").json()
        if body["status"] in ("completed", "failed"):
            return body
        time.sleep(0.1)
    raise AssertionError(f"Job {job_id} did not finish in {timeout}s")
