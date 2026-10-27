from tests.conftest import UBIQUITIN, wait_for_job


def test_health_local(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["storage"]["backend"] == "local"
    assert body["prediction_engine"]["genuine_prediction_available"] is False


def test_invalid_sequence_returns_422(client):
    r = client.post("/api/predict", json={"sequence": "HELLO WORLD 123"})
    assert r.status_code == 422
    assert "Invalid character" in r.json()["detail"]


def test_full_job_local_without_engine(client):
    r = client.post("/api/predict", json={"sequence": ">ubiquitin\n" + UBIQUITIN, "execution_mode": "parallel"})
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    status = wait_for_job(client, job_id)
    assert status["status"] == "completed", status
    by_id = {t["id"]: t for t in status["tasks"]}
    assert all(by_id[t]["status"] == "completed" for t in "ABCDEFGI")
    assert by_id["H"]["status"] == "skipped"            # no engine -> clearly skipped, no fake structure
    assert by_id["UPLOAD"]["status"] == "completed"

    res = client.get(f"/api/results/{job_id}").json()
    assert res["report"]["structure"]["available"] is False
    assert {f["filename"] for f in res["files"]} == {"report.json", "report.md"}
    assert res["metrics"]["execution_mode"] == "parallel"

    links = client.get(f"/api/results/{job_id}/downloads").json()["files"]
    md = client.get(links[1]["url"] if links[1]["filename"] == "report.md" else links[0]["url"])
    assert md.status_code == 200
    assert client.get(f"/api/results/{job_id}/structure").status_code == 404

    hist = client.get("/api/history").json()["items"]
    assert any(h["id"] == job_id for h in hist)
    assert client.delete(f"/api/history/{job_id}").status_code == 200
    assert client.get(f"/api/results/{job_id}").status_code == 404


def test_sequential_mode_records_mode(client):
    job_id = client.post("/api/predict", json={"sequence": UBIQUITIN, "execution_mode": "sequential"}).json()["job_id"]
    status = wait_for_job(client, job_id)
    assert status["metrics"]["workers"] == 1


def test_cors_allows_frontend_origin(client):
    r = client.options("/api/health", headers={"Origin": "http://localhost:5173",
                                               "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    r = client.options("/api/health", headers={"Origin": "http://evil.example",
                                               "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in r.headers
