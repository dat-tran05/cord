from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import calls, targets, ws, ws_voice
from app.config import settings
from app.db import init_db, close_db, get_stuck_enriching, update_enrichment, get_stuck_analyzing, update_analysis_status
from app.services.handlers import register_all_handlers
from app.services.task_queue import TaskQueue, TaskWorker

logger = __import__("logging").getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    register_all_handlers()
    queue = TaskQueue()
    worker = TaskWorker(queue)
    await worker.start()

    # Store queue in app.state so routes can access it
    app.state.task_queue = queue

    # Re-enqueue targets stuck at "enriching" from a previous crash (target enrichment)
    stuck = await get_stuck_enriching()
    for t in stuck:
        await update_enrichment(t["id"], "pending")
        await queue.enqueue("enrichment", {"target_id": t["id"], "target_data": t})
        logger.info("Re-enqueued stuck enrichment for target %s (%s)", t["id"], t["name"])

    # Re-enqueue calls stuck at "analyzing" from a previous crash (post-convo analysis)
    stuck_calls = await get_stuck_analyzing()
    for c in stuck_calls:
        await update_analysis_status(c["call_id"], "analyzing")
        await queue.enqueue("analysis", {"call_id": c["call_id"]})
        logger.info("Re-enqueued stuck analysis for call %s", c["call_id"])

    yield
    await worker.stop()
    await close_db()


app = FastAPI(title="CORD Voice Agent", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(targets.router)
app.include_router(calls.router)
app.include_router(ws.router)
app.include_router(ws_voice.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
