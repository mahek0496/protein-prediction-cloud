import time

from app.workflow.dag import TaskSkipped, TaskSpec, run_dag
from app.workflow.pipeline import run_benchmark
from tests.conftest import UBIQUITIN


def _sleep(sec, fail=False, skip=False):
    def f(ctx):
        time.sleep(sec)
        if fail:
            raise RuntimeError("boom")
        if skip:
            raise TaskSkipped("not configured")
        return {"summary": "ok"}
    return f


def _graph(h_fail=False):
    return [
        TaskSpec("A", "A", _sleep(0.05)),
        TaskSpec("B", "B", _sleep(0.05), ["A"]),
        *[TaskSpec(t, t, _sleep(0.3, fail=(t == "H" and h_fail)), ["B"], "parallel") for t in "CDEFGH"],
        TaskSpec("I", "I", _sleep(0.01), list("CDEFGH"), tolerate_failed_deps=True),
    ]


def test_dependencies_respected_in_parallel():
    s = run_dag(_graph(), {}, max_workers=6)["states"]
    assert s["B"]["start_offset"] >= s["A"]["end_offset"]
    for t in "CDEFGH":
        assert s[t]["start_offset"] >= s["B"]["end_offset"]
        assert s["I"]["start_offset"] >= s[t]["end_offset"]
    assert all(v["status"] == "completed" for v in s.values())


def test_parallel_faster_than_sequential():
    seq = run_dag(_graph(), {}, max_workers=1)["wall_seconds"]
    par = run_dag(_graph(), {}, max_workers=6)["wall_seconds"]
    assert seq > 1.8 and par < 0.8, (seq, par)


def test_failed_parallel_task_does_not_stop_final_report():
    s = run_dag(_graph(h_fail=True), {}, max_workers=6)["states"]
    assert s["H"]["status"] == "failed" and "boom" in s["H"]["error"]
    assert s["I"]["status"] == "completed"


def test_failure_in_A_skips_everything_downstream():
    g = _graph()
    g[0] = TaskSpec("A", "A", _sleep(0, fail=True))
    s = run_dag(g, {}, max_workers=6)["states"]
    assert s["A"]["status"] == "failed"
    assert all(s[t]["status"] == "skipped" for t in "BCDEFGHI")


def test_benchmark_with_artificial_delay_shows_speedup():
    r = run_benchmark(UBIQUITIN, 0.3)
    assert r["runs"]["sequential"]["wall_seconds"] > 1.4
    assert r["speedup"] > 2.5
