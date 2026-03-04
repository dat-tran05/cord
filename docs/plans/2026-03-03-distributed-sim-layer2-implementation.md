# Layer 2: Distributed Simulation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract simulation execution into standalone worker processes communicating via Redis, with a CLI dispatcher for orchestration.

**Architecture:** Three independent processes — CLI dispatcher enqueues jobs to Redis, async worker(s) pull and execute them concurrently, dispatcher polls progress and aggregates results. All simulation logic (CallRunner, Judge, Personas, Metrics) reused unchanged from Layer 1.

**Tech Stack:** Python 3.12, asyncio, redis-py async, OpenAI API, existing Layer 1 simulation modules.

---

## File Layout

```
backend/tests/simulation/
├── sim_queue.py       # NEW — Shared Redis queue protocol
├── worker.py          # NEW — Standalone async worker process
├── dispatch.py        # NEW — CLI dispatcher (enqueue + wait + collect)
├── call_runner.py     # EXISTING — unchanged
├── simulator.py       # EXISTING — unchanged
├── judge.py           # EXISTING — unchanged
├── personas.py        # EXISTING — unchanged
├── metrics.py         # EXISTING — unchanged
├── conftest.py        # EXISTING — unchanged
└── test_simulated_call.py  # EXISTING — unchanged
```

## Key References

Before starting, read these files to understand the existing codebase:
- `backend/tests/simulation/call_runner.py` — `CallRunner.run()`, `SimulationResult` dataclass
- `backend/tests/simulation/judge.py` — `ConversationJudge.evaluate()`, `JudgeVerdict` dataclass, `JudgeVerdict.from_dict()`
- `backend/tests/simulation/personas.py` — `StudentPersona` frozen dataclass, `PRESETS`, `generate_random_personas()`
- `backend/tests/simulation/metrics.py` — `aggregate_results()`, `SimulationReport`
- `backend/tests/simulation/conftest.py` — `SAMPLE_TARGET_ENRICHED`
- `backend/app/services/task_queue.py` — Reference for Redis queue patterns (RPOPLPUSH, pipeline transactions)
- `backend/app/config.py` — `settings.redis_url`, `settings.openai_api_key`

---

### Task 1: Shared Redis Queue Protocol

**Files:**
- Create: `tests/simulation/sim_queue.py`

**Step 1: Write sim_queue.py**

This module defines the Redis key structure and all operations shared between dispatcher and worker.

```python
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
```

**Step 2: Verify it imports correctly**

Run: `cd backend && python -c "from tests.simulation.sim_queue import create_job, pull_job, store_result; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add tests/simulation/sim_queue.py
git commit -m "feat(sim): Redis queue protocol for distributed simulation"
```

---

### Task 2: Async Worker Process

**Files:**
- Create: `tests/simulation/worker.py`

**Step 1: Write worker.py**

This is a standalone process that pulls simulation jobs from Redis and executes them concurrently.

```python
"""Standalone simulation worker process.

Pulls simulation jobs from Redis and executes them concurrently
using asyncio.Semaphore for backpressure.

Run:
    cd backend
    python -m tests.simulation.worker --concurrency 10
    python -m tests.simulation.worker --concurrency 5 --redis-url redis://localhost:6379/0
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import uuid

from openai import AsyncOpenAI
from redis.asyncio import Redis

from app.config import settings
from tests.simulation.call_runner import CallRunner
from tests.simulation.judge import ConversationJudge
from tests.simulation.sim_queue import mark_failed, pull_job, store_result

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
logger = logging.getLogger("sim_worker")


class SimWorker:
    def __init__(self, redis_url: str, concurrency: int = 10):
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.concurrency = concurrency
        self.semaphore = asyncio.Semaphore(concurrency)
        self.active_tasks: set[asyncio.Task] = set()
        self._shutdown = asyncio.Event()
        self.worker_id = f"worker-{uuid.uuid4().hex[:6]}"
        self.jobs_completed = 0
        self.jobs_failed = 0

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.runner = CallRunner(client=client)
        self.judge = ConversationJudge(client=client)

    def request_shutdown(self) -> None:
        """Signal the worker to stop pulling new jobs. Synchronous — safe for signal handlers."""
        logger.info("Shutdown requested")
        self._shutdown.set()

    async def run(self) -> None:
        """Main loop: pull jobs and execute concurrently. Returns when shutdown is requested."""
        logger.info("%s started (concurrency=%d)", self.worker_id, self.concurrency)

        while not self._shutdown.is_set():
            # Acquire semaphore with timeout so we can check shutdown periodically
            try:
                await asyncio.wait_for(self.semaphore.acquire(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            if self._shutdown.is_set():
                self.semaphore.release()
                break

            job = await pull_job(self.redis)
            if job is None:
                self.semaphore.release()
                # No work available — back off
                try:
                    await asyncio.wait_for(self._shutdown.wait(), timeout=0.5)
                except asyncio.TimeoutError:
                    pass
                continue

            task = asyncio.create_task(self._execute(job))
            self.active_tasks.add(task)
            task.add_done_callback(self.active_tasks.discard)

    async def _execute(self, job: dict) -> None:
        """Run one simulation: CallRunner -> Judge -> store result."""
        job_id = job["id"]
        run_id = job["run_id"]
        persona = job["persona_obj"]
        target = job["target_obj"]

        try:
            logger.info("Job %s: starting (%s, goal=%s)", job_id, persona.name, persona.hidden_goal)
            result = await self.runner.run(target_profile=target, persona=persona)
            verdict = await self.judge.evaluate(result.transcript, persona)
            await store_result(self.redis, job_id, run_id, result, verdict, self.worker_id)
            self.jobs_completed += 1
            logger.info(
                "Job %s: done (%s → %s in %d turns, %.1fs)",
                job_id,
                persona.name,
                result.outcome,
                result.turns,
                result.duration_seconds,
            )
        except Exception as e:
            logger.error("Job %s: failed — %s", job_id, e)
            await mark_failed(self.redis, job_id, run_id, str(e))
            self.jobs_failed += 1
        finally:
            self.semaphore.release()

    async def drain(self, timeout: float = 120) -> None:
        """Wait for in-flight jobs to complete, then close Redis."""
        if self.active_tasks:
            logger.info("Draining %d in-flight jobs...", len(self.active_tasks))
            done, pending = await asyncio.wait(self.active_tasks, timeout=timeout)
            if pending:
                logger.warning("%d jobs didn't finish within timeout", len(pending))
        await self.redis.aclose()
        logger.info(
            "%s stopped (completed=%d, failed=%d)",
            self.worker_id,
            self.jobs_completed,
            self.jobs_failed,
        )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Simulation worker")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Max concurrent simulations (default: 10)",
    )
    parser.add_argument("--redis-url", default=settings.redis_url)
    args = parser.parse_args()

    worker = SimWorker(redis_url=args.redis_url, concurrency=args.concurrency)

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, worker.request_shutdown)

    await worker.run()
    await worker.drain()


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: Verify it imports correctly**

Run: `cd backend && python -c "from tests.simulation.worker import SimWorker; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add tests/simulation/worker.py
git commit -m "feat(sim): async simulation worker with semaphore concurrency"
```

---

### Task 3: CLI Dispatcher

**Files:**
- Create: `tests/simulation/dispatch.py`

**Step 1: Write dispatch.py**

The dispatcher generates personas, enqueues jobs, polls progress, and aggregates results.

```python
"""CLI dispatcher for distributed simulation runs.

Enqueues simulation jobs to Redis, shows live progress, then
aggregates and prints the final report.

Run:
    cd backend
    python -m tests.simulation.dispatch --presets
    python -m tests.simulation.dispatch --random 50 --seed 42
    python -m tests.simulation.dispatch --random 20 --timeout 300
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
import uuid
from pathlib import Path

from redis.asyncio import Redis

from app.config import settings
from tests.simulation.conftest import SAMPLE_TARGET_ENRICHED
from tests.simulation.metrics import aggregate_results
from tests.simulation.personas import PRESETS, generate_random_personas
from tests.simulation.sim_queue import (
    create_job,
    create_run,
    get_job_results,
    get_run_progress,
    set_run_job_ids,
)

REPORT_DIR = str(Path(__file__).parent / "reports")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Dispatch simulation jobs to Redis")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--presets", action="store_true", help="Run 5 preset personas")
    group.add_argument("--random", type=int, metavar="N", help="Run N random personas")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--timeout", type=int, default=600, help="Max wait in seconds (default: 600)")
    parser.add_argument("--redis-url", default=settings.redis_url)
    args = parser.parse_args()

    # Generate personas
    if args.presets:
        personas = list(PRESETS.values())
    else:
        personas = generate_random_personas(n=args.random, seed=args.seed)

    redis = Redis.from_url(args.redis_url, decode_responses=True)
    target = SAMPLE_TARGET_ENRICHED
    run_id = uuid.uuid4().hex[:8]

    # --- Enqueue phase ---
    await create_run(redis, run_id, total=len(personas))

    job_ids: list[str] = []
    for persona in personas:
        job_id = await create_job(redis, run_id, persona, target)
        job_ids.append(job_id)

    await set_run_job_ids(redis, run_id, job_ids)

    print(f"Enqueued {len(personas)} simulation jobs (run {run_id})")
    print(f"Waiting for workers... (timeout {args.timeout}s)")

    # --- Wait phase ---
    start = time.monotonic()
    last_done = 0
    try:
        while True:
            progress = await get_run_progress(redis, run_id)
            done = progress["completed"] + progress["failed"]
            total = progress["total"]
            elapsed = time.monotonic() - start

            if done != last_done:
                rate = done / elapsed if elapsed > 0 else 0
                eta = (total - done) / rate if rate > 0 else 0
                print(
                    f"\rProgress: {done}/{total} "
                    f"({progress['completed']} ok, {progress['failed']} fail) "
                    f"[{elapsed:.0f}s elapsed, ~{eta:.0f}s remaining]",
                    end="",
                    flush=True,
                )
                last_done = done

            if done >= total:
                print()
                break
            if elapsed > args.timeout:
                print(f"\nTimeout after {args.timeout}s ({done}/{total} completed)")
                break

            await asyncio.sleep(2)
    except KeyboardInterrupt:
        progress = await get_run_progress(redis, run_id)
        done = progress["completed"] + progress["failed"]
        print(f"\nInterrupted ({done}/{progress['total']} completed)")

    # --- Collect phase ---
    results = await get_job_results(redis, job_ids)
    pairs = [r for r in results if r is not None]

    if not pairs:
        print("No completed results to report.")
        await redis.aclose()
        sys.exit(1)

    report = aggregate_results(pairs)
    print(f"\n{report.console_summary()}")
    path = report.save(REPORT_DIR)
    print(f"\nReport saved to: {path}")

    await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: Verify it imports correctly**

Run: `cd backend && python -c "from tests.simulation.dispatch import main; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add tests/simulation/dispatch.py
git commit -m "feat(sim): CLI dispatcher with progress polling and report aggregation"
```

---

### Task 4: Lint

**Step 1: Run ruff on all new files**

Run: `cd backend && ruff check tests/simulation/sim_queue.py tests/simulation/worker.py tests/simulation/dispatch.py`
Expected: No errors (or fix any that appear)

Run: `cd backend && ruff format tests/simulation/sim_queue.py tests/simulation/worker.py tests/simulation/dispatch.py`

**Step 2: Commit any formatting fixes**

```bash
git add tests/simulation/sim_queue.py tests/simulation/worker.py tests/simulation/dispatch.py
git commit -m "style: lint distributed simulation files"
```

---

### Task 5: End-to-End Validation

**Prerequisites:** Redis must be running locally (`redis-server` or `docker run -p 6379:6379 redis:7-alpine`).

**Step 1: Start worker in background**

Run in one terminal:
```bash
cd backend
python -m tests.simulation.worker --concurrency 3
```

Expected output:
```
2026-03-03 ... INFO [sim_worker] worker-abc123 started (concurrency=3)
```

**Step 2: Run dispatcher with 2 presets (quick validation)**

Run in another terminal:
```bash
cd backend
python -m tests.simulation.dispatch --presets --timeout 300
```

Expected output:
```
Enqueued 5 simulation jobs (run abc12345)
Waiting for workers... (timeout 300s)
Progress: 5/5 (5 ok, 0 fail) [XXs elapsed, ~0s remaining]

=== Simulation Report ===
Total calls: 5
Sale rate: X.X%
Avg turns: X.X
...
Report saved to: tests/simulation/reports/sim_report_XXXXXXXX_XXXXXX.json
```

**Step 3: Verify worker logs show jobs being processed**

Worker terminal should show:
```
... INFO [sim_worker] Job abc123: starting (Alex Chen, goal=buy)
... INFO [sim_worker] Job abc123: done (Alex Chen → sold in X turns, X.Xs)
... INFO [sim_worker] Job def456: starting (Marcus Johnson, goal=refuse)
...
```

**Step 4: Test graceful shutdown**

Press Ctrl+C in the worker terminal while jobs are running. Expected:
```
... INFO [sim_worker] Shutdown requested
... INFO [sim_worker] Draining 2 in-flight jobs...
... INFO [sim_worker] worker-abc123 stopped (completed=3, failed=0)
```

**Step 5: Test with 2 workers (throughput scaling)**

Run two workers in separate terminals:
```bash
# Terminal A
cd backend && python -m tests.simulation.worker --concurrency 5

# Terminal B
cd backend && python -m tests.simulation.worker --concurrency 5
```

Then dispatch 10 random personas:
```bash
cd backend
python -m tests.simulation.dispatch --random 10 --seed 99
```

Verify both workers pick up jobs (check their logs). Jobs should be split across workers.

---

## Run Commands Cheat Sheet

```bash
# Start a worker (from backend/)
python -m tests.simulation.worker --concurrency 10

# Dispatch presets (5 personas, ~$2.30)
python -m tests.simulation.dispatch --presets

# Dispatch random (N personas, ~$0.46 each)
python -m tests.simulation.dispatch --random 20 --seed 42

# Dispatch with custom timeout
python -m tests.simulation.dispatch --random 50 --timeout 900

# Multiple workers for higher throughput
python -m tests.simulation.worker --concurrency 5 &
python -m tests.simulation.worker --concurrency 5 &
python -m tests.simulation.dispatch --random 50
```
