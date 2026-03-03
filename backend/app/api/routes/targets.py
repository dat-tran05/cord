import asyncio
import logging
import uuid

from fastapi import APIRouter, HTTPException

from app.api.models import TargetCreate, TargetResponse
from app import db
from app.research.enricher import ProfileEnricher

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/targets", tags=["targets"])


async def _run_enrichment(target_id: str, seed_data: dict) -> None:
    """Run enrichment in background — updates DB when done."""
    try:
        await db.update_enrichment(target_id, "enriching")
        enricher = ProfileEnricher()
        enriched = await enricher.enrich(seed_data)
        await db.update_enrichment(target_id, "enriched", enriched)
    except Exception:
        logger.exception(f"Enrichment failed for target {target_id}")
        await db.update_enrichment(target_id, "failed")


@router.post("", status_code=201, response_model=TargetResponse)
async def create_target(body: TargetCreate):
    target_id = str(uuid.uuid4())[:8]
    target = await db.create_target(target_id, body.model_dump())
    asyncio.create_task(_run_enrichment(target_id, body.model_dump()))
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


@router.delete("/{target_id}", status_code=204)
async def delete_target(target_id: str):
    deleted = await db.delete_target(target_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Target not found")


async def get_target_data(target_id: str) -> dict | None:
    return await db.get_target(target_id)
