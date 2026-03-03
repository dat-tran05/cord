import logging

from app import db
from app.research.enricher import ProfileEnricher
from app.services.task_queue import TaskQueue

logger = logging.getLogger(__name__)


async def handle_enrichment(payload: dict) -> dict | None:
    """Enrich a target profile via web research + tactical analysis.

    Called by the TaskWorker. Does NOT catch exceptions — the worker handles retries.
    """
    target_id = payload["target_id"]
    target_data = payload["target_data"]

    await db.update_enrichment(target_id, "enriching")
    enricher = ProfileEnricher()
    enriched = await enricher.enrich(target_data)
    await db.update_enrichment(target_id, "enriched", enriched)
    logger.info(f"Enrichment completed for target {target_id}")
    return {"target_id": target_id, "status": "enriched"}


async def handle_enrichment_failure(payload: dict, error: str) -> None:
    """Called when enrichment fails after all retries are exhausted."""
    target_id = payload["target_id"]
    await db.update_enrichment(target_id, "failed")
    logger.error(f"Enrichment permanently failed for target {target_id}: {error}")


def register_all_handlers():
    """Register all job handlers. Called once at app startup."""
    TaskQueue.register_handler(
        "enrichment", handle_enrichment, on_failure=handle_enrichment_failure
    )
