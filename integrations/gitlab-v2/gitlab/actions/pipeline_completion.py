import asyncio

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import ActionRun, WorkflowNodeRun

TERMINAL_PIPELINE_STATUSES = frozenset({"success", "failed", "canceled", "skipped"})


async def find_run_with_retry(
    external_id: str,
    *,
    retries: int = 5,
    initial_delay: float = 0.5,
) -> ActionRun | WorkflowNodeRun | None:
    """Look up a Port run by external ID, retrying with exponential backoff
    to handle the race where the webhook arrives before update_run_started()
    finishes writing. Default: 0.5s, 1s, 2s, 4s → ~7.5s total."""
    delay = initial_delay
    for attempt in range(retries):
        run = await ocean.port_client.find_run_by_external_id(external_id)
        if run is not None:
            return run
        if attempt < retries - 1:
            await asyncio.sleep(delay)
            delay *= 2
    return None


async def complete_run_from_pipeline_status(
    external_id: str,
    status: str,
    *,
    completion_source: str,
) -> bool:
    """Report pipeline completion to Port. Returns True if this call completed the run."""
    run = await ocean.port_client.find_run_by_external_id(external_id)
    if run is None:
        logger.debug(
            f"No Port run for {external_id}, skipping {completion_source} update"
        )
        return False

    if not run.execution_properties.get("reportPipelineStatus", True):
        logger.info(f"reportPipelineStatus disabled for run {run.id}, skipping")
        return False

    if not ocean.port_client.is_run_in_progress(run):
        logger.debug(
            f"Run {run.id} already completed, skipping {completion_source} update"
        )
        return False

    is_success = status == "success"
    logger.info(
        f"Pipeline {completion_source} → run {run.id}: status={status} is_success={is_success}"
    )
    try:
        await ocean.port_client.report_run_completed(
            run, is_success, f"Pipeline completed: {status}"
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 409:
            logger.debug(
                f"Run {run.id} already completed, skipping {completion_source} update"
            )
            return False
        raise
    return True
