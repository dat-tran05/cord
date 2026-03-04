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
from tests.simulation.sim_queue import mark_failed, pull_job, recover_stale_jobs, store_result

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

    async def recover(self) -> None:
        """Recover stale jobs from processing queue (crash recovery)."""
        recovered = await recover_stale_jobs(self.redis)
        if recovered:
            logger.info("Recovered %d stale jobs from processing queue", recovered)
        else:
            logger.info("No stale jobs to recover")

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
    parser.add_argument(
        "--recover",
        action="store_true",
        help="Recover stale jobs from processing queue before starting. "
        "Only use when no other workers are running.",
    )
    args = parser.parse_args()

    worker = SimWorker(redis_url=args.redis_url, concurrency=args.concurrency)

    if args.recover:
        await worker.recover()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, worker.request_shutdown)

    await worker.run()
    await worker.drain()


if __name__ == "__main__":
    asyncio.run(main())
