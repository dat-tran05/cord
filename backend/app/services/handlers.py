import logging

from app import db
from app.analytics.analyzer import CallAnalyzer
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


async def handle_analysis(payload: dict) -> dict | None:
    """Analyze a completed call transcript.

    Called by the TaskWorker. Does NOT catch exceptions — the worker handles retries.
    """
    call_id = payload["call_id"]
    call = await db.get_call(call_id)
    if not call:
        logger.error(f"Analysis job: call {call_id} not found in DB")
        return None

    analyzer = CallAnalyzer()
    analysis = await analyzer.analyze(call["transcript"])
    await db.save_analysis(call_id, analysis)
    logger.info(f"Analysis completed for call {call_id}")
    return {"call_id": call_id, "status": "analyzed"}


async def handle_analysis_failure(payload: dict, error: str) -> None:
    """Called when analysis fails after all retries are exhausted."""
    call_id = payload["call_id"]
    await db.update_analysis_status(call_id, "failed")
    logger.error(f"Analysis permanently failed for call {call_id}: {error}")


def register_all_handlers():
    """Register all job handlers. Called once at app startup."""
    TaskQueue.register_handler(
        "enrichment", handle_enrichment, on_failure=handle_enrichment_failure
    )
    TaskQueue.register_handler(
        "analysis", handle_analysis, on_failure=handle_analysis_failure
    )
