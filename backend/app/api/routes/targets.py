import uuid

from fastapi import APIRouter, HTTPException

from app.api.models import TargetCreate, TargetResponse
from app import db

router = APIRouter(prefix="/api/targets", tags=["targets"])


@router.post("", status_code=201, response_model=TargetResponse)
async def create_target(body: TargetCreate):
    target_id = str(uuid.uuid4())[:8]
    target = await db.create_target(target_id, body.model_dump())
    return target


@router.get("", response_model=list[TargetResponse])
async def list_targets():
    return await db.list_targets()


@router.get("/{target_id}", response_model=TargetResponse)
async def get_target(target_id: str):
    target = await db.get_target(target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    return target


async def get_target_data(target_id: str) -> dict | None:
    return await db.get_target(target_id)
