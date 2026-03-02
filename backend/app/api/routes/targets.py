import uuid

from fastapi import APIRouter, HTTPException

from app.api.models import TargetCreate, TargetResponse

router = APIRouter(prefix="/api/targets", tags=["targets"])

# In-memory store (swap to Redis/DB later)
_targets: dict[str, dict] = {}


@router.post("", status_code=201, response_model=TargetResponse)
async def create_target(body: TargetCreate):
    target_id = str(uuid.uuid4())[:8]
    target = {"id": target_id, **body.model_dump()}
    _targets[target_id] = target
    return target


@router.get("", response_model=list[TargetResponse])
async def list_targets():
    return list(_targets.values())


@router.get("/{target_id}", response_model=TargetResponse)
async def get_target(target_id: str):
    if target_id not in _targets:
        raise HTTPException(status_code=404, detail="Target not found")
    return _targets[target_id]


def get_target_data(target_id: str) -> dict | None:
    return _targets.get(target_id)
