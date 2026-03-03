import uuid

from fastapi import APIRouter, HTTPException

from app.api.models import CallCreate, CallResponse
from app.api.routes.targets import get_target_data
from app.analytics.analyzer import CallAnalyzer
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



@router.post("/{call_id}/end")
async def end_call(call_id: str):
    pipeline = _pipelines.get(call_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Call not found")
    await pipeline.stop()
    await db.end_call(call_id, pipeline.transcript)
    return {"status": "ended", "transcript": pipeline.transcript}


@router.get("/{call_id}/analysis")
async def get_analysis(call_id: str):
    pipeline = _pipelines.get(call_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Call not found")
    if pipeline.is_active:
        raise HTTPException(status_code=400, detail="Call is still active. End it first.")
    if not pipeline.transcript:
        raise HTTPException(status_code=400, detail="No transcript available")

    analyzer = CallAnalyzer()
    analysis = await analyzer.analyze(pipeline.transcript)
    await db.save_analysis(call_id, analysis)
    return analysis


@router.get("/{call_id}")
async def get_call(call_id: str):
    pipeline = _pipelines.get(call_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Call not found")
    return {
        "call_id": call_id,
        "is_active": pipeline.is_active,
        "transcript": pipeline.transcript,
    }
