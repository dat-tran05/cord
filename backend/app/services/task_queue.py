from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable

from redis.asyncio import Redis

from app.config import settings

logger = logging.getLogger(__name__)

JOB_PREFIX = "cord:queue:job:"
PENDING_QUEUE = "cord:queue:pending"
PROCESSING_QUEUE = "cord:queue:processing"
JOB_TTL = 86400

JobHandler = Callable[[dict], Awaitable[dict | None]]
FailureHandler = Callable[[dict, str], Awaitable[None]]


class TaskQueue:
    _handlers: dict[str, tuple[JobHandler, FailureHandler | None]] = {}

    def __init__(self, client: Redis | None = None):
        self._client = client

    @property
    def client(self) -> Redis:
        if self._client is None:
            self._client = Redis.from_url(settings.redis_url, decode_responses=True)
        return self._client

    @classmethod
    def register_handler(
        cls,
        job_type: str,
        handler: JobHandler,
        on_failure: FailureHandler | None = None,
    ) -> None:
        cls._handlers[job_type] = (handler, on_failure)

    async def enqueue(self, job_type: str, payload: dict, max_retries: int = 3) -> str:
        if job_type not in self._handlers:
            raise ValueError(f"No handler registered for job type: {job_type}")

        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        job_data = {
            "id": job_id,
            "job_type": job_type,
            "payload": json.dumps(payload),
            "status": "pending",
            "retries": "0",
            "max_retries": str(max_retries),
            "result": "",
            "created_at": now,
            "updated_at": now,
        }

        key = f"{JOB_PREFIX}{job_id}"
        async with self.client.pipeline(transaction=True) as pipe:
            pipe.hset(key, mapping=job_data)
            pipe.lpush(PENDING_QUEUE, job_id)
            await pipe.execute()

        logger.info("Enqueued job %s (type=%s)", job_id, job_type)
        return job_id

    async def get_job(self, job_id: str) -> dict | None:
        key = f"{JOB_PREFIX}{job_id}"
        data = await self.client.hgetall(key)
        if not data:
            return None

        data["retries"] = int(data["retries"])
        data["max_retries"] = int(data["max_retries"])

        try:
            data["payload"] = json.loads(data["payload"])
        except (json.JSONDecodeError, TypeError):
            pass

        if data.get("result"):
            try:
                data["result"] = json.loads(data["result"])
            except (json.JSONDecodeError, TypeError):
                pass

        return data

    async def _process_one(self) -> bool:
        job_id = await self.client.rpoplpush(PENDING_QUEUE, PROCESSING_QUEUE)
        if job_id is None:
            return False

        key = f"{JOB_PREFIX}{job_id}"
        now = datetime.now(timezone.utc).isoformat()
        await self.client.hset(key, mapping={"status": "processing", "updated_at": now})

        data = await self.client.hgetall(key)
        job_type = data["job_type"]
        payload = json.loads(data["payload"])
        retries = int(data["retries"])
        max_retries = int(data["max_retries"])

        handler, on_failure = self._handlers[job_type]

        try:
            result = await handler(payload)
            now = datetime.now(timezone.utc).isoformat()
            async with self.client.pipeline(transaction=True) as pipe:
                pipe.hset(
                    key,
                    mapping={
                        "status": "completed",
                        "result": json.dumps(result) if result else "",
                        "updated_at": now,
                    },
                )
                pipe.expire(key, JOB_TTL)
                pipe.lrem(PROCESSING_QUEUE, 1, job_id)
                await pipe.execute()
            logger.info("Job %s completed", job_id)
        except Exception as exc:
            retries += 1
            now = datetime.now(timezone.utc).isoformat()
            error_msg = str(exc)

            if retries < max_retries:
                async with self.client.pipeline(transaction=True) as pipe:
                    pipe.hset(
                        key,
                        mapping={
                            "status": "pending",
                            "retries": str(retries),
                            "updated_at": now,
                        },
                    )
                    pipe.lrem(PROCESSING_QUEUE, 1, job_id)
                    pipe.lpush(PENDING_QUEUE, job_id)
                    await pipe.execute()
                logger.warning(
                    "Job %s failed (retry %d/%d): %s", job_id, retries, max_retries, error_msg
                )
            else:
                async with self.client.pipeline(transaction=True) as pipe:
                    pipe.hset(
                        key,
                        mapping={
                            "status": "failed",
                            "retries": str(retries),
                            "result": json.dumps(error_msg),
                            "updated_at": now,
                        },
                    )
                    pipe.expire(key, JOB_TTL)
                    pipe.lrem(PROCESSING_QUEUE, 1, job_id)
                    await pipe.execute()
                logger.error("Job %s permanently failed: %s", job_id, error_msg)

                if on_failure:
                    try:
                        await on_failure(payload, error_msg)
                    except Exception:
                        logger.exception("Failure handler error for job %s", job_id)

        return True

    async def _recover_processing(self) -> int:
        count = 0
        while True:
            job_id = await self.client.rpoplpush(PROCESSING_QUEUE, PENDING_QUEUE)
            if job_id is None:
                break
            now = datetime.now(timezone.utc).isoformat()
            key = f"{JOB_PREFIX}{job_id}"
            await self.client.hset(key, mapping={"status": "pending", "updated_at": now})
            count += 1
        return count


class TaskWorker:
    def __init__(self, queue: TaskQueue):
        self.queue = queue
        self._task: asyncio.Task | None = None
        self._shutdown = asyncio.Event()

    async def start(self) -> None:
        recovered = await self.queue._recover_processing()
        if recovered:
            logger.info("Recovered %d stale jobs from processing queue", recovered)
        self._task = asyncio.create_task(self._run())
        logger.info("Task worker started")

    async def stop(self) -> None:
        self._shutdown.set()
        if self._task:
            await self._task
        logger.info("Task worker stopped")

    async def _run(self) -> None:
        while not self._shutdown.is_set():
            try:
                processed = await self.queue._process_one()
                if not processed:
                    try:
                        await asyncio.wait_for(self._shutdown.wait(), timeout=1.0)
                    except asyncio.TimeoutError:
                        pass
            except Exception:
                logger.exception("Worker loop error")
                await asyncio.sleep(1)
