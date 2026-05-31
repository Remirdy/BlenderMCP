"""Tiny in-process job registry for async provider work."""
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
        "state": "created",
        "created_at": time.time(),
        "updated_at": time.time(),
        "payload": payload,
        "result": None,
        "error": None,
    }
    _JOBS[job_id] = job
    return job


def update_job(job_id: str, **fields) -> dict[str, Any]:
    job = _JOBS[job_id]
    job.update(fields)
    job["updated_at"] = time.time()
    return job


def get_job(job_id: str) -> dict[str, Any] | None:
    return _JOBS.get(job_id)


def list_jobs() -> list[dict[str, Any]]:
    return sorted(_JOBS.values(), key=lambda item: item["created_at"], reverse=True)
