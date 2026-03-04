import uuid

from fastapi import APIRouter, HTTPException, Request

from app.api.models import CallCreate, CallResponse
from app.api.routes.targets import get_target_data
from app.voice.pipeline import VoicePipeline, CallConfig
from app import db

router = APIRouter(prefix="/api/calls", tags=["calls"])

# Active pipelines (in-memory — these hold live WebSocket objects)
_pipelines: dict[str, VoicePipeline] = {}


@router.post("", status_code=201, response_model=CallResponse)
async def initiate_call(body: CallCreate):
    target = await get_target_data(body.target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    call_id = f"call-{uuid.uuid4().hex[:8]}"
    config = CallConfig(
        call_id=call_id,
        target_name=target["name"],
        target_profile=target,
        mode=body.mode,
    )
    pipeline = VoicePipeline(config)
    _pipelines[call_id] = pipeline

    await pipeline.start()
    await db.create_call(call_id, body.target_id, target["name"], body.mode)

    return CallResponse(
        call_id=call_id,
        target_id=body.target_id,
        target_name=target["name"],
        status="active",
        mode=body.mode,
    )



@router.get("")
async def list_calls():
    calls = await db.list_calls()
    return calls


@router.post("/{call_id}/end")
async def end_call(call_id: str, request: Request):
    pipeline = _pipelines.pop(call_id, None)
    if pipeline:
        await pipeline.stop()
        await db.end_call(call_id, pipeline.transcript)
        transcript = pipeline.transcript
    else:
        # Browser-mode calls aren't in _pipelines (managed by ws_voice.py).
        # The transcript may already be saved by the WS finally block.
        row = await db.get_call(call_id)
        if not row:
            raise HTTPException(status_code=404, detail="Call not found")
        if row["status"] == "active":
            await db.end_call(call_id, row.get("transcript", []))
        transcript = row.get("transcript", [])

    # Enqueue async analysis job (idempotent — skip if already running)
    row = await db.get_call(call_id)
    if row and row.get("analysis_status") not in ("analyzing", "analyzed"):
        await db.update_analysis_status(call_id, "analyzing")
        queue = request.app.state.task_queue
        await queue.enqueue("analysis", {"call_id": call_id})

    return {"status": "ended", "transcript": transcript}


@router.get("/{call_id}/analysis")
async def get_analysis(call_id: str):
    # Check if call is still active in memory
    pipeline = _pipelines.get(call_id)
    if pipeline and pipeline.is_active:
        raise HTTPException(status_code=400, detail="Call is still active")

    # Look up call in DB
    row = await db.get_call(call_id)
    if not row:
        raise HTTPException(status_code=404, detail="Call not found")

    if row["analysis"]:
        return row["analysis"]
    if row.get("analysis_status") == "analyzing":
        return {"status": "analyzing"}
    if row.get("analysis_status") == "failed":
        return {"status": "failed"}
    return {"status": "pending"}


@router.get("/{call_id}")
async def get_call(call_id: str):
    # Check in-memory pipelines first (active calls)
    pipeline = _pipelines.get(call_id)
    if pipeline:
        return {
            "call_id": call_id,
            "is_active": pipeline.is_active,
            "transcript": pipeline.transcript,
            "mode": pipeline.config.mode if hasattr(pipeline, "config") else None,
            "target_name": pipeline.config.target_name if hasattr(pipeline, "config") else None,
            "target_id": "",
            "status": "active" if pipeline.is_active else "ended",
            "analysis": None,
            "analysis_status": None,
            "created_at": None,
            "ended_at": None,
        }

    # Fall back to DB
    row = await db.get_call(call_id)
    if not row:
        raise HTTPException(status_code=404, detail="Call not found")
    return {
        **row,
        "is_active": row["status"] == "active",
    }
