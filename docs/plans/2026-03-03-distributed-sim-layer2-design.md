# Layer 2: Distributed Simulation — Worker Extraction Design

**Goal:** Extract simulation execution into standalone worker processes that pull jobs from Redis, enabling concurrent distributed simulation runs.

**Scope:** Worker extraction pattern only. No Docker, no production code changes. Separate Python processes communicating via Redis.

---

## Architecture

Three independent processes communicate through Redis:

```
┌─────────────────────┐
│   CLI Dispatcher     │  python -m tests.simulation.dispatch
│                      │
│   Enqueues jobs ─────┼──→ Redis List: cord:sim:pending
│   Polls results  ←───┼──  Redis Hash: cord:sim:job:{id}
│   Aggregates report  │
└─────────────────────┘

┌─────────────────────┐
│   Sim Worker (×M)    │  python -m app.sim_worker --concurrency 10
│                      │
│   Pulls jobs    ←────┼──  Redis List: cord:sim:pending
│   Runs CallRunner    │
│   Runs Judge         │
│   Stores results ────┼──→ Redis Hash: cord:sim:job:{id}
└─────────────────────┘

┌─────────────────────┐
│       Redis          │  Shared state
│                      │
│   cord:sim:pending   │  LIST  — job IDs waiting
│   cord:sim:processing│  LIST  — job IDs in-flight
│   cord:sim:job:{id}  │  HASH  — job metadata + result
│   cord:sim:run:{id}  │  HASH  — run-level metadata
└─────────────────────┘
```

The worker is a **new, standalone process** — not the existing `TaskWorker`. Purpose-built for simulation with async concurrency. The existing `TaskQueue`/`TaskWorker` continues handling enrichment and analysis jobs in the main app unchanged.

**Why separate from existing TaskQueue?** Different concerns. The production queue is tightly coupled to the FastAPI app lifecycle. The simulation worker needs concurrent execution, has no FastAPI dependency, and runs independently. Keeping them separate means you can't accidentally break production jobs.

---

## Sim Worker

### Async Concurrency Model

The worker uses `asyncio.Semaphore` to limit concurrent simulations within a single process. Since each simulation is I/O-bound (waiting on OpenAI API), one worker process can efficiently handle 10+ concurrent simulations.

```
Main Loop:
    acquire semaphore → pull job from Redis → spawn asyncio.Task
    (loop immediately, don't wait for task to finish)

Each Task:
    CallRunner.run(target, persona) → ConversationJudge.evaluate() → store result in Redis
    release semaphore on completion (success or failure)
```

### Job Pull: RPOPLPUSH

Same reliable queue pattern as existing TaskQueue. Atomically moves job ID from `cord:sim:pending` to `cord:sim:processing`. If the worker crashes, jobs in `processing` can be identified and recovered.

### No Retry Logic

Intentionally omitted. If a job fails (OpenAI error, timeout, etc.), it's marked `failed` in Redis. The dispatcher reports failures in the summary. Retries can be added later — keeping it simple makes the distributed pattern clearer.

### Graceful Shutdown (Ctrl+C)

1. Stop pulling new jobs
2. Wait for in-flight tasks to complete (60s timeout)
3. Any still-running jobs remain in `cord:sim:processing` — dispatcher reports them as "lost"

### Entrypoint

```bash
python -m app.sim_worker --concurrency 10 --redis-url redis://localhost:6379/0
```

---

## CLI Dispatcher

### Usage

```bash
# Run 5 preset personas
python -m tests.simulation.dispatch --presets --timeout 600

# Run 50 random personas
python -m tests.simulation.dispatch --random 50 --seed 42 --timeout 600
```

### Lifecycle

**1. Enqueue phase:**
- Generate personas (presets or random via existing `personas.py`)
- Create a run record in Redis: `cord:sim:run:{run_id} = {total, completed, failed, job_ids}`
- Create a job hash for each persona + push ID to `cord:sim:pending`
- Print: `"Enqueued 50 simulation jobs (run abc123)"`

**2. Wait phase:**
- Poll `cord:sim:run:{run_id}` every 2 seconds
- Print progress: `"Progress: 23/50 complete, 0 failed"`
- Exit on: all done, timeout, or Ctrl+C

**3. Collect phase:**
- Fetch all job results from Redis
- Deserialize `SimulationResult` + `JudgeVerdict` from each completed job
- Run `aggregate_results()` from existing `metrics.py` — no new aggregation code
- Print `console_summary()` + save JSON report

---

## Redis Key Structure

### Job Hash: `cord:sim:job:{id}`

```
status:       pending | processing | completed | failed
run_id:       parent run ID
persona:      JSON-serialized StudentPersona
target:       JSON-serialized target profile
result:       JSON-serialized SimulationResult (set on completion)
verdict:      JSON-serialized JudgeVerdict (set on completion)
error:        error message (set on failure)
worker_id:    which worker processed this job
created_at:   ISO8601
started_at:   ISO8601 (set when processing starts)
completed_at: ISO8601 (set on completion/failure)
```

### Run Hash: `cord:sim:run:{id}`

```
total:     total job count
completed: atomically incremented via HINCRBY
failed:    atomically incremented via HINCRBY
job_ids:   JSON array of job IDs
created_at: ISO8601
```

Workers use `HINCRBY` to atomically increment `completed` or `failed` counters. The dispatcher polls this hash for progress.

---

## Shared Queue Protocol: `sim_queue.py`

Both dispatcher and worker import shared Redis helpers:

| Function | Used by | Purpose |
|---|---|---|
| `create_run(redis, total, job_ids)` | Dispatcher | Create run tracking hash |
| `create_job(redis, run_id, persona, target)` | Dispatcher | Create job hash + push to pending |
| `pull_job(redis)` | Worker | RPOPLPUSH pending → processing |
| `store_result(redis, job_id, result, verdict)` | Worker | Save result + HINCRBY completed |
| `mark_failed(redis, job_id, error)` | Worker | Save error + HINCRBY failed |
| `get_run_progress(redis, run_id)` | Dispatcher | Read total/completed/failed |
| `get_job_results(redis, job_ids)` | Dispatcher | Batch-fetch all completed results |

---

## File Layout

```
backend/
├── app/
│   └── sim_worker.py              # Standalone worker process
└── tests/
    └── simulation/
        ├── dispatch.py            # CLI dispatcher
        ├── sim_queue.py           # Shared Redis queue protocol
        ├── call_runner.py         # (existing, unchanged)
        ├── simulator.py           # (existing, unchanged)
        ├── judge.py               # (existing, unchanged)
        ├── personas.py            # (existing, unchanged)
        ├── metrics.py             # (existing, unchanged)
        └── conftest.py            # (existing, unchanged)
```

---

## Error Handling

| Failure mode | Behavior |
|---|---|
| Worker crashes mid-job | Jobs in `cord:sim:processing` are "lost." Dispatcher detects them after timeout. |
| OpenAI API error (single call) | Job marked `failed`. Other jobs continue. Reported in summary. |
| OpenAI rate limit | Concurrent calls fail fast, semaphore slots free up, worker naturally backs off. |
| Redis connection lost | Worker/dispatcher crash. Restart — `pending` jobs are still queued, `processing` jobs recoverable. |
| Ctrl+C on worker | Graceful shutdown: finish in-flight, then exit. |

---

## What We Skip (YAGNI)

- No retry logic in worker (dispatcher can re-enqueue manually)
- No health check endpoints (just check if process is running)
- No Prometheus/Grafana metrics (console output for learning)
- No dead letter queue (failed jobs in hash, dispatcher reports them)
- No Docker (separate Python processes for development)
- No modifications to production code (app/services/task_queue.py, handlers.py untouched)

---

## Reuse from Layer 1

All Layer 1 modules used unchanged:
- `personas.py` — persona generation
- `simulator.py` — StudentSimulator
- `call_runner.py` — CallRunner
- `judge.py` — ConversationJudge
- `metrics.py` — aggregate_results + console_summary
- `conftest.py` — SAMPLE_TARGET_ENRICHED

---

## How to Run

```bash
# Terminal 1: Redis
redis-server

# Terminal 2: Worker (10 concurrent simulations)
cd backend
python -m app.sim_worker --concurrency 10

# Terminal 3: Dispatcher (50 random personas)
cd backend
python -m tests.simulation.dispatch --random 50 --seed 42

# Optional: second worker for more throughput
# Terminal 4:
cd backend
python -m app.sim_worker --concurrency 10
```

## Success Criteria

1. Worker starts, connects to Redis, pulls and executes simulation jobs
2. Dispatcher enqueues jobs, shows live progress, prints aggregated report
3. Running 2 workers doubles throughput compared to 1 worker
4. Worker handles Ctrl+C gracefully (finishes in-flight, doesn't lose results)
5. Failed jobs are reported without crashing the run
