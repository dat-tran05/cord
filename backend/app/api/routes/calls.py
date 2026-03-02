import uuid

from fastapi import APIRouter, HTTPException

from app.api.models import CallCreate, CallResponse, TextInput
from app.api.routes.targets import get_target_data
from app.voice.pipeline import VoicePipeline, CallConfig

router = APIRouter(prefix="/api/calls", tags=["calls"])

# Active pipelines
_pipelines: dict[str, VoicePipeline] = {}


@router.post("", status_code=201, response_model=CallResponse)
async def initiate_call(body: CallCreate):
    target = get_target_data(body.target_id)
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

    return CallResponse(
        call_id=call_id,
        target_id=body.target_id,
        target_name=target["name"],
        status="active",
        mode=body.mode,
    )


@router.post("/{call_id}/text", response_model=dict)
async def send_text_message(call_id: str, body: TextInput):
    pipeline = _pipelines.get(call_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Call not found")
    if not pipeline.is_active:
        raise HTTPException(status_code=400, detail="Call is not active")

    response = await pipeline.process_text_input(body.message)
    return {
        "response": response,
        "stage": pipeline.state_machine.current_stage.value,
    }


@router.post("/{call_id}/end")
async def end_call(call_id: str):
    pipeline = _pipelines.get(call_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Call not found")
    await pipeline.stop()
    return {"status": "ended", "transcript": pipeline.transcript}


@router.get("/{call_id}")
async def get_call(call_id: str):
    pipeline = _pipelines.get(call_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Call not found")
    return {
        "call_id": call_id,
        "is_active": pipeline.is_active,
        "stage": pipeline.state_machine.current_stage.value,
        "transcript": pipeline.transcript,
    }
