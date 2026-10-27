"""S3 behaviour tested against moto's in-memory S3 emulator (no real AWS account is used)."""
import boto3
import pytest
from botocore.exceptions import ClientError, NoCredentialsError
from moto import mock_aws

from app.services import structure_engine
from app.services.storage import describe_aws_error, reset_storage
from tests.conftest import UBIQUITIN, fake_pdb, wait_for_job

BUCKET = "protein-app-test-bucket"


class FakeResp:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status


@pytest.fixture
def s3_settings(restore_settings, monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")       # moto fake credentials
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
        restore_settings.storage_backend = "s3"
        restore_settings.s3_bucket_name = BUCKET
        reset_storage()
        yield restore_settings


def test_s3_health_ok(client, s3_settings):
    body = client.get("/api/health").json()
    assert body["storage"]["backend"] == "s3" and body["storage"]["ok"] is True
    assert body["storage"]["credential_source"] == "env"   # on EC2 this shows "iam-role"


def test_job_uploads_report_and_structure_to_s3(client, s3_settings, monkeypatch):
    s3_settings.prediction_engine = "esmatlas"
    monkeypatch.setattr(structure_engine.requests, "post", lambda *a, **k: FakeResp(fake_pdb(UBIQUITIN)))
    job_id = client.post("/api/predict", json={"sequence": UBIQUITIN}).json()["job_id"]
    status = wait_for_job(client, job_id)
    assert status["status"] == "completed", status

    res = client.get(f"/api/results/{job_id}").json()
    names = {f["filename"]: f for f in res["files"]}
    assert set(names) == {"report.json", "report.md", "structure.pdb", "structure.cif"}
    assert all(f["backend"] == "s3" for f in res["files"])
    assert res["report"]["structure"]["mean_plddt"] == 85.0   # 0-1 scale converted to 0-100

    keys = [o["Key"] for o in boto3.client("s3", region_name="us-east-1")
            .list_objects_v2(Bucket=BUCKET)["Contents"]]
    assert f"jobs/{job_id}/structure.cif" in keys

    links = client.get(f"/api/results/{job_id}/downloads").json()["files"]
    assert all("X-Amz-Signature" in l["url"] and l["expires_in"] == 900 for l in links)
    assert BUCKET in links[0]["url"]

    pdb = client.get(f"/api/results/{job_id}/structure")
    assert pdb.status_code == 200 and pdb.text.startswith("ATOM")

    assert client.delete(f"/api/history/{job_id}").json()["storage_errors"] == []
    assert "Contents" not in boto3.client("s3", region_name="us-east-1").list_objects_v2(Bucket=BUCKET)


def test_missing_bucket_falls_back_to_local(client, s3_settings):
    s3_settings.s3_bucket_name = "bucket-that-does-not-exist-xyz"
    reset_storage()
    assert client.get("/api/health").json()["status"] == "degraded"
    job_id = client.post("/api/predict", json={"sequence": UBIQUITIN}).json()["job_id"]
    wait_for_job(client, job_id)
    res = client.get(f"/api/results/{job_id}").json()
    assert res["status"] == "completed"
    assert all(f["backend"] == "local" for f in res["files"])
    assert any("not found" in e for e in res["storage_errors"])


def test_engine_network_error_is_reported(client, restore_settings, monkeypatch):
    import requests
    restore_settings.prediction_engine = "esmatlas"

    def boom(*a, **k):
        raise requests.exceptions.ConnectionError("down")
    monkeypatch.setattr(structure_engine.requests, "post", boom)
    job_id = client.post("/api/predict", json={"sequence": UBIQUITIN}).json()["job_id"]
    status = wait_for_job(client, job_id)
    h = next(t for t in status["tasks"] if t["id"] == "H")
    assert h["status"] == "failed" and "Could not connect" in h["error"]
    assert status["status"] == "completed"  # rest of the report still produced


def test_engine_rejects_mismatched_structure(restore_settings, monkeypatch):
    restore_settings.prediction_engine = "esmatlas"
    monkeypatch.setattr(structure_engine.requests, "post", lambda *a, **k: FakeResp(fake_pdb("MQIFV")))
    with pytest.raises(structure_engine.PredictionError, match="residues"):
        structure_engine.predict_structure(UBIQUITIN)


def test_aws_error_messages():
    assert "IAM role" in describe_aws_error(NoCredentialsError())
    denied = ClientError({"Error": {"Code": "AccessDenied", "Message": "x"}}, "PutObject")
    assert "s3:PutObject" in describe_aws_error(denied)
