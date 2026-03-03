from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import calls, targets, ws, ws_voice
from app.config import settings
from app.db import init_db, close_db
from app.services.handlers import register_all_handlers
from app.services.task_queue import TaskQueue, TaskWorker


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    register_all_handlers()
    worker = TaskWorker(TaskQueue())
    await worker.start()
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
