import asyncio
import logging
import uuid

from fastapi import APIRouter, HTTPException

from app.api.models import TargetCreate, TargetResponse
from app import db
from app.research.enricher import ProfileEnricher

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/targets", tags=["targets"])

# Hold references to prevent GC of fire-and-forget tasks
_enrichment_tasks: set[asyncio.Task] = set()


async def _run_enrichment(target_id: str, target_data: dict) -> None:
    """Background task: enrich a target profile and persist results."""
    try:
        await db.update_enrichment(target_id, "enriching")
        enricher = ProfileEnricher()
        enriched = await enricher.enrich(target_data)
        await db.update_enrichment(target_id, "enriched", enriched)
        logger.info(f"Enrichment completed for target {target_id}")
    except Exception:
        logger.exception(f"Enrichment failed for target {target_id}")
        await db.update_enrichment(target_id, "failed")


@router.post("", status_code=201, response_model=TargetResponse)
async def create_target(body: TargetCreate):
    target_id = str(uuid.uuid4())[:8]
    target = await db.create_target(target_id, body.model_dump())

    # Fire-and-forget enrichment
    task = asyncio.create_task(_run_enrichment(target_id, body.model_dump()))
    _enrichment_tasks.add(task)
    task.add_done_callback(_enrichment_tasks.discard)

    return target


@router.post("/{target_id}/enrich", response_model=TargetResponse)
async def re_enrich_target(target_id: str):
    """Retry enrichment for a target (e.g., after a failure)."""
    target = await db.get_target(target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    task = asyncio.create_task(_run_enrichment(target_id, target))
    _enrichment_tasks.add(task)
    task.add_done_callback(_enrichment_tasks.discard)

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
