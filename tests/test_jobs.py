"""
Background job runner tests — offline.
Run:  python -m pytest tests/test_jobs.py   OR   python tests/test_jobs.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.jobs import JobRunner


def _wait(runner, jid, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = runner.get(jid)
        if job and job["status"] in ("done", "error"):
            return job
        time.sleep(0.02)
    return runner.get(jid)


def test_job_completes_with_result():
    r = JobRunner()
    jid = r.submit(lambda: {"embedded": 7}, kind="test")
    job = _wait(r, jid)
    assert job["status"] == "done"
    assert job["result"] == {"embedded": 7}
    assert job["error"] is None


def test_job_captures_error():
    r = JobRunner()
    def boom():
        raise RuntimeError("quota exceeded")
    jid = r.submit(boom)
    job = _wait(r, jid)
    assert job["status"] == "error"
    assert "quota exceeded" in job["error"]


def test_submit_returns_immediately():
    r = JobRunner()
    def slow():
        time.sleep(0.5)
        return {"ok": True}
    t0 = time.time()
    jid = r.submit(slow)
    # submit must not block on the work
    assert time.time() - t0 < 0.2
    assert r.get(jid)["status"] in ("queued", "running")
    assert _wait(r, jid, timeout=2)["status"] == "done"


def test_unknown_job_is_none():
    assert JobRunner().get("nope") is None


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} job tests passed")


if __name__ == "__main__":
    _run()
