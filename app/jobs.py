"""
Background job runner
=====================
Runs long operations (embedding ingestion) off the request thread so endpoints
like /ingest/upload return immediately with a job_id the caller can poll.

In-process + thread-based: jobs do NOT survive a restart and do NOT span multiple
workers. That's the modular-monolith stance — the `submit()` / `get()` interface
is what matters; swap the backend for Celery / RQ / Cloud Tasks later without
changing callers. Until then run a single worker (or accept per-worker job state).
"""

from __future__ import annotations

import threading
import traceback
import uuid
from dataclasses import asdict, dataclass
from typing import Callable


@dataclass
class Job:
    id: str
    kind: str
    status: str = "queued"  # queued | running | done | error
    result: dict | None = None
    error: str | None = None


class JobRunner:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def submit(self, fn: Callable[[], dict], kind: str = "job") -> str:
        job_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._jobs[job_id] = Job(id=job_id, kind=kind)

        def _run() -> None:
            with self._lock:
                self._jobs[job_id].status = "running"
            try:
                result = fn()
                with self._lock:
                    self._jobs[job_id].status = "done"
                    self._jobs[job_id].result = result
            except Exception as e:  # noqa: BLE001 — capture any failure into the job
                with self._lock:
                    self._jobs[job_id].status = "error"
                    self._jobs[job_id].error = str(e)
                traceback.print_exc()

        threading.Thread(target=_run, name=f"job-{job_id}", daemon=True).start()
        return job_id

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return asdict(job) if job else None


# Module-level singleton.
runner = JobRunner()
