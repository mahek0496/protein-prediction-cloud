"""SQLite persistence for prediction jobs (history, task statuses, results)."""
import json
import sqlite3
import threading

from .config import settings

_lock = threading.Lock()
_conn = None
JSON_FIELDS = {"tasks", "result", "files", "storage_errors", "metrics"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    name TEXT,
    sequence TEXT NOT NULL,
    status TEXT NOT NULL,
    execution_mode TEXT NOT NULL,
    demo_delay_seconds REAL DEFAULT 0,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    total_seconds REAL,
    tasks TEXT,
    result TEXT,
    files TEXT,
    storage_errors TEXT,
    metrics TEXT,
    error TEXT
)
"""


def _connect():
    global _conn
    if _conn is None:
        settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(settings.database_path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute(SCHEMA)
        _conn.commit()
    return _conn


def init_db():
    with _lock:
        _connect()


def close_db():
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None


def _encode(fields: dict) -> dict:
    return {k: (json.dumps(v) if k in JSON_FIELDS and v is not None else v) for k, v in fields.items()}


def _decode(row) -> dict:
    d = dict(row)
    for k in JSON_FIELDS:
        if d.get(k):
            d[k] = json.loads(d[k])
    return d


def create_job(job: dict):
    data = _encode(job)
    cols = ", ".join(data)
    marks = ", ".join("?" for _ in data)
    with _lock:
        c = _connect()
        c.execute(f"INSERT INTO jobs ({cols}) VALUES ({marks})", list(data.values()))
        c.commit()


def update_job(job_id: str, **fields):
    data = _encode(fields)
    sets = ", ".join(f"{k} = ?" for k in data)
    with _lock:
        c = _connect()
        c.execute(f"UPDATE jobs SET {sets} WHERE id = ?", [*data.values(), job_id])
        c.commit()


def get_job(job_id: str):
    with _lock:
        row = _connect().execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _decode(row) if row else None


def list_jobs(limit: int = 50) -> list:
    with _lock:
        rows = _connect().execute(
            "SELECT id, name, status, execution_mode, created_at, finished_at, total_seconds, "
            "length(sequence) AS length, substr(sequence, 1, 30) AS sequence_preview, files "
            "FROM jobs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_decode(r) for r in rows]


def delete_job(job_id: str) -> bool:
    with _lock:
        c = _connect()
        cur = c.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        c.commit()
    return cur.rowcount > 0


def mark_interrupted_jobs():
    """Jobs left 'running' when the server stopped can never finish; mark them failed."""
    with _lock:
        c = _connect()
        c.execute("UPDATE jobs SET status = 'failed', error = 'Server restarted before the job finished.' "
                  "WHERE status IN ('queued', 'running')")
        c.commit()
