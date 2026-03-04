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
    get_job_statuses,
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
    parser.add_argument(
        "--timeout", type=int, default=600, help="Max wait in seconds (default: 600)"
    )
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

    # --- Diagnostics phase ---
    statuses = await get_job_statuses(redis, job_ids)
    print("\n=== Job Status Breakdown ===")
    for status in ("completed", "failed", "processing", "pending"):
        count = len(statuses.get(status, []))
        extra = ""
        if status == "processing" and count > 0:
            extra = "  (stale — worker likely crashed)"
        if status == "pending" and count > 0:
            extra = "  (never picked up)"
        print(f"  {status:>12}: {count}{extra}")
    print(f"  {'total':>12}: {len(job_ids)}")

    stale = len(statuses.get("processing", []))
    if stale:
        print(
            f"\nWARNING: {stale} jobs stuck in processing. "
            "Run a worker with --recover to re-enqueue them."
        )

    # --- Collect phase ---
    results = await get_job_results(redis, job_ids)
    pairs = [r for r in results if r is not None]

    if not pairs:
        print("\nNo completed results to report.")
        await redis.aclose()
        sys.exit(1)

    report = aggregate_results(pairs)
    print(f"\n{report.console_summary()}")
    path = report.save(REPORT_DIR)
    print(f"\nReport saved to: {path}")

    await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
