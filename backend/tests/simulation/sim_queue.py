"""Shared Redis queue protocol for distributed simulation.

Both the dispatcher (enqueue side) and worker (dequeue side) import this
module to ensure consistent key structure and serialization.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from redis.asyncio import Redis

from tests.simulation.call_runner import SimulationResult
from tests.simulation.judge import JudgeVerdict
from tests.simulation.personas import StudentPersona

# Redis key prefixes — separate namespace from production queue (cord:queue:*)
SIM_JOB_PREFIX = "cord:sim:job:"
SIM_RUN_PREFIX = "cord:sim:run:"
SIM_PENDING = "cord:sim:pending"
SIM_PROCESSING = "cord:sim:processing"

JOB_TTL = 3600  # 1 hour


async def create_run(redis: Redis, run_id: str, total: int) -> None:
    """Create a run tracking hash. Call BEFORE creating jobs."""
    key = f"{SIM_RUN_PREFIX}{run_id}"
    await redis.hset(
        key,
        mapping={
            "total": str(total),
            "completed": "0",
            "failed": "0",
            "job_ids": "[]",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    await redis.expire(key, JOB_TTL)


async def set_run_job_ids(redis: Redis, run_id: str, job_ids: list[str]) -> None:
    """Update run with job IDs after all jobs are created."""
    await redis.hset(f"{SIM_RUN_PREFIX}{run_id}", "job_ids", json.dumps(job_ids))


async def create_job(
    redis: Redis,
    run_id: str,
    persona: StudentPersona,
    target: dict,
) -> str:
    """Create a job hash and push ID to pending queue. Returns job_id."""
    job_id = uuid.uuid4().hex[:8]
    key = f"{SIM_JOB_PREFIX}{job_id}"
    now = datetime.now(timezone.utc).isoformat()
    async with redis.pipeline(transaction=True) as pipe:
        pipe.hset(
            key,
            mapping={
                "status": "pending",
                "run_id": run_id,
                "persona": json.dumps(asdict(persona)),
                "target": json.dumps(target),
                "result": "",
                "verdict": "",
                "error": "",
                "worker_id": "",
                "created_at": now,
            },
        )
        pipe.expire(key, JOB_TTL)
        pipe.lpush(SIM_PENDING, job_id)
        await pipe.execute()
    return job_id


async def pull_job(redis: Redis) -> dict | None:
    """RPOPLPUSH one job from pending to processing. Returns job dict or None."""
    job_id = await redis.rpoplpush(SIM_PENDING, SIM_PROCESSING)
    if job_id is None:
        return None
    key = f"{SIM_JOB_PREFIX}{job_id}"
    now = datetime.now(timezone.utc).isoformat()
    await redis.hset(key, mapping={"status": "processing", "started_at": now})
    data = await redis.hgetall(key)
    data["id"] = job_id
    data["persona_obj"] = StudentPersona(**json.loads(data["persona"]))
    data["target_obj"] = json.loads(data["target"])
    return data


async def store_result(
    redis: Redis,
    job_id: str,
    run_id: str,
    result: SimulationResult,
    verdict: JudgeVerdict,
    worker_id: str,
) -> None:
    """Save completed result and atomically increment run counter."""
    key = f"{SIM_JOB_PREFIX}{job_id}"
    now = datetime.now(timezone.utc).isoformat()
    async with redis.pipeline(transaction=True) as pipe:
        pipe.hset(
            key,
            mapping={
                "status": "completed",
                "result": json.dumps(asdict(result)),
                "verdict": json.dumps(asdict(verdict)),
                "worker_id": worker_id,
                "completed_at": now,
            },
        )
        pipe.lrem(SIM_PROCESSING, 1, job_id)
        pipe.hincrby(f"{SIM_RUN_PREFIX}{run_id}", "completed", 1)
        await pipe.execute()


async def mark_failed(
    redis: Redis,
    job_id: str,
    run_id: str,
    error: str,
) -> None:
    """Mark job as failed and atomically increment run failure counter."""
    key = f"{SIM_JOB_PREFIX}{job_id}"
    now = datetime.now(timezone.utc).isoformat()
    async with redis.pipeline(transaction=True) as pipe:
        pipe.hset(
            key,
            mapping={
                "status": "failed",
                "error": error,
                "completed_at": now,
            },
        )
        pipe.lrem(SIM_PROCESSING, 1, job_id)
        pipe.hincrby(f"{SIM_RUN_PREFIX}{run_id}", "failed", 1)
        await pipe.execute()


async def get_run_progress(redis: Redis, run_id: str) -> dict:
    """Read run-level counters: total, completed, failed."""
    data = await redis.hgetall(f"{SIM_RUN_PREFIX}{run_id}")
    return {
        "total": int(data.get("total", 0)),
        "completed": int(data.get("completed", 0)),
        "failed": int(data.get("failed", 0)),
    }


async def recover_stale_jobs(redis: Redis) -> int:
    """Move all jobs from processing back to pending. Call on worker startup.

    Handles crash recovery: if a worker died mid-job, those jobs are stuck
    in the processing list. This moves them back so another worker can retry.

    WARNING: Only use when no other workers are actively running — this moves
    ALL processing jobs, including ones another worker might be working on.
    Same pattern as TaskQueue._recover_processing() in app/services/task_queue.py.
    """
    count = 0
    while True:
        job_id = await redis.rpoplpush(SIM_PROCESSING, SIM_PENDING)
        if job_id is None:
            break
        key = f"{SIM_JOB_PREFIX}{job_id}"
        await redis.hset(key, mapping={"status": "pending", "worker_id": ""})
        count += 1
    return count


async def get_job_statuses(redis: Redis, job_ids: list[str]) -> dict[str, list[str]]:
    """Batch-fetch status of all jobs. Returns {status: [job_ids]}."""
    by_status: dict[str, list[str]] = {}
    for job_id in job_ids:
        data = await redis.hgetall(f"{SIM_JOB_PREFIX}{job_id}")
        status = data.get("status", "unknown")
        by_status.setdefault(status, []).append(job_id)
    return by_status


async def get_job_results(
    redis: Redis,
    job_ids: list[str],
) -> list[tuple[SimulationResult, JudgeVerdict] | None]:
    """Batch-fetch results for all jobs. Returns None for incomplete/failed jobs."""
    results: list[tuple[SimulationResult, JudgeVerdict] | None] = []
    for job_id in job_ids:
        data = await redis.hgetall(f"{SIM_JOB_PREFIX}{job_id}")
        if data.get("status") != "completed" or not data.get("result"):
            results.append(None)
            continue
        result_dict = json.loads(data["result"])
        verdict_dict = json.loads(data["verdict"])
        result = SimulationResult(**result_dict)
        verdict = JudgeVerdict.from_dict(verdict_dict)
        results.append((result, verdict))
    return results
