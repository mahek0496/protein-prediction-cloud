"""A small dependency-aware task scheduler built on concurrent.futures.

A task is submitted only when every task it depends on has finished. With max_workers=1 the same
graph runs strictly one task at a time (sequential mode); with max_workers>1 independent tasks run
concurrently (parallel mode).
"""
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

FINISHED = {"completed", "failed", "skipped"}


class TaskSkipped(Exception):
    """Raise inside a task to mark it 'skipped' with a reason (not an error)."""


@dataclass
class TaskSpec:
    id: str
    name: str
    func: Callable[[dict], dict]
    depends_on: list = field(default_factory=list)
    group: str = "sequential"          # "sequential" or "parallel" (for the UI graph)
    description: str = ""
    tolerate_failed_deps: bool = False  # True: run even if some dependencies failed/skipped


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_dag(specs: list, context: dict, max_workers: int, on_update: Optional[Callable] = None) -> dict:
    """Run the graph. Returns {"states": {...}, "outputs": {...}, "wall_seconds": float}."""
    by_id = {s.id: s for s in specs}
    states = {
        s.id: {"id": s.id, "name": s.name, "group": s.group, "description": s.description,
               "depends_on": s.depends_on, "status": "pending", "started_at": None, "finished_at": None,
               "start_offset": None, "end_offset": None, "duration_seconds": None, "error": None,
               "summary": None, "result_type": None}
        for s in specs
    }
    outputs: dict = {}
    lock = threading.Lock()
    t_start = time.perf_counter()

    def notify():
        if on_update:
            with lock:
                snapshot = {k: dict(v) for k, v in states.items()}
            on_update(snapshot)

    def execute(spec: TaskSpec):
        st = states[spec.id]
        with lock:
            st["status"], st["started_at"] = "running", now_iso()
            st["start_offset"] = round(time.perf_counter() - t_start, 4)
        notify()
        t0 = time.perf_counter()
        try:
            out = spec.func({**context, "outputs": outputs, "states": states})
            outputs[spec.id] = out
            status, error = "completed", None
        except TaskSkipped as exc:
            status, error = "skipped", str(exc)
        except Exception as exc:  # a failing task must not crash the workflow
            status, error = "failed", f"{type(exc).__name__}: {exc}"
        t1 = time.perf_counter()
        with lock:
            out = outputs.get(spec.id) or {}
            st.update(status=status, error=error, finished_at=now_iso(),
                      duration_seconds=round(t1 - t0, 4), end_offset=round(t1 - t_start, 4),
                      summary=out.get("summary") if isinstance(out, dict) else None,
                      result_type=out.get("result_type") if isinstance(out, dict) else None)
        notify()

    pending = [s.id for s in specs]
    running = {}
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="task") as pool:
        while pending or running:
            progressed = True
            while progressed:  # repeat so a skip can cascade to later tasks in the same pass
                progressed = False
                for tid in list(pending):
                    spec = by_id[tid]
                    if any(states[d]["status"] not in FINISHED for d in spec.depends_on):
                        continue  # inputs not ready yet
                    pending.remove(tid)
                    progressed = True
                    bad = [d for d in spec.depends_on if states[d]["status"] != "completed"]
                    if bad and (not spec.tolerate_failed_deps or len(bad) == len(spec.depends_on)):
                        with lock:
                            states[tid].update(status="skipped",
                                               error=f"Dependency not completed: {', '.join(bad)}")
                        notify()
                        continue
                    with lock:
                        states[tid]["status"] = "queued"
                    running[pool.submit(execute, spec)] = tid
            if not running:
                if pending:  # unreachable for a valid DAG; guards against a cycle
                    for tid in pending:
                        states[tid].update(status="skipped", error="Circular or missing dependency.")
                    pending.clear()
                    notify()
                break
            done, _ = wait(running, return_when=FIRST_COMPLETED)
            for f in done:
                running.pop(f)
    return {"states": states, "outputs": outputs, "wall_seconds": round(time.perf_counter() - t_start, 4)}
