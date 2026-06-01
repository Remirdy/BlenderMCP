"""Job system for long-running professional workflows.

Supports progress tracking, status messages, and proper lifecycle for
ambitious features like terrain generation, video reconstruction, etc.
"""
from __future__ import annotations

import time
import uuid
from typing import Any


_JOBS: dict[str, dict[str, Any]] = {}


def create_job(provider: str, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    job_id = uuid.uuid4().hex
    job = {
        "job_id": job_id,
        "provider": provider,
        "kind": kind,
        "state": "created",           # created | running | completed | failed | cancelled
        "progress": 0.0,              # 0.0 - 100.0
        "status_message": "Job created",
        "created_at": time.time(),
        "updated_at": time.time(),
        "payload": payload,
        "result": None,
        "error": None,
    }
    _JOBS[job_id] = job
    return job


def update_job(job_id: str, **fields) -> dict[str, Any]:
    if job_id not in _JOBS:
        return None
    job = _JOBS[job_id]
    job.update(fields)
    job["updated_at"] = time.time()
    return job


def set_job_progress(job_id: str, progress: float, message: str = "") -> dict[str, Any] | None:
    """Convenience function to update progress + status message together."""
    if job_id not in _JOBS:
        return None
    job = _JOBS[job_id]
    job["progress"] = max(0.0, min(100.0, progress))
    if message:
        job["status_message"] = message
    job["updated_at"] = time.time()
    return job


def finish_job(job_id: str, result: Any = None, error: str | None = None) -> dict[str, Any] | None:
    if job_id not in _JOBS:
        return None
    job = _JOBS[job_id]
    job["updated_at"] = time.time()
    if error:
        job["state"] = "failed"
        job["error"] = error
        job["status_message"] = f"Failed: {error}"
    else:
        job["state"] = "completed"
        job["result"] = result
        job["progress"] = 100.0
        job["status_message"] = "Completed successfully"
    return job


def get_job(job_id: str) -> dict[str, Any] | None:
    return _JOBS.get(job_id)


def list_jobs() -> list[dict[str, Any]]:
    return sorted(_JOBS.values(), key=lambda item: item["created_at"], reverse=True)


def cancel_job(job_id: str) -> bool:
    if job_id not in _JOBS:
        return False
    job = _JOBS[job_id]
    if job["state"] in ("completed", "failed"):
        return False
    job["state"] = "cancelled"
    job["status_message"] = "Job cancelled by user"
    job["updated_at"] = time.time()
    return True
