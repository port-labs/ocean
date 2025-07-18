from fastapi import APIRouter, Request, HTTPException
from resources.deployments import DeploymentsFetcher
from utils.emit_to_port import emit_to_port
from utils.logger import logger


router = APIRouter()





@router.post("/webhook/spacelift")
async def spacelift_webhook(request: Request):
    try:
        payload = await request.json()
        logger.info("Received Spacelift webhook event.")
        logger.debug(f"Payload: {payload}")
    except Exception:
        logger.error("Invalid JSON in webhook", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = payload.get("event")
    run_data = payload.get("run")

    if not run_data or not run_data.get("id"):
        logger.warning("Missing run ID in payload.")
        raise HTTPException(status_code=400, detail="Missing run ID")

    run_id = run_data["id"]
    logger.info(f"Processing event '{event_type}' for run ID: {run_id}")

    fetcher = DeploymentsFetcher()

    try:
        async for entity in fetcher.fetch_by_id(run_id):
            await emit_to_port(kind=DeploymentsFetcher.kind, entity=entity)
    except Exception:
        logger.error("Webhook handling failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Webhook ingestion failed")

    return {"status": "ok"}
