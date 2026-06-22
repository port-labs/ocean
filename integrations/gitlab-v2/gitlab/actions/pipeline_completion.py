import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

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


async def complete_run_if_in_progress(
    run: ActionRun | WorkflowNodeRun,
    status: str,
    *,
    completion_source: str,
) -> bool:
    """Report pipeline completion to Port. Returns True if the run was completed."""
    if not run.execution_properties.get("reportPipelineStatus", True):
        logger.info(f"reportPipelineStatus disabled for run {run.id}, skipping")
        return False

    if not ocean.port_client.is_run_in_progress(run):
        logger.debug(
            f"Run {run.id} already completed, skipping {completion_source} update"
        )
        return False

    success = status == "success"
    logger.info(
        f"Pipeline {completion_source} → run {run.id}: status={status} success={success}"
    )
    await ocean.port_client.report_run_completed(
        run, success, f"Pipeline completed: {status}"
    )
    return True


async def poll_pipeline_to_completion(
    external_id: str,
    project_id: int,
    pipeline_id: int,
    get_pipeline: Callable[[int, int], Awaitable[dict[str, Any]]],
    *,
    interval: int = 5,
    timeout: int = 60 * 60,
) -> None:
    """Poll GitLab for pipeline status until terminal, then complete the Port run.
    Exits early if the run is already completed (e.g. by a webhook)."""
    max_attempts = timeout // interval

    for _attempt in range(max_attempts):
        pipeline = await get_pipeline(project_id, pipeline_id)
        status = pipeline.get("status", "")

        run = await ocean.port_client.find_run_by_external_id(external_id)
        if run is None or not ocean.port_client.is_run_in_progress(run):
            return

        if status in TERMINAL_PIPELINE_STATUSES:
            await complete_run_if_in_progress(run, status, completion_source="poll")
            return

        await asyncio.sleep(interval)

    run = await ocean.port_client.find_run_by_external_id(external_id)
    if run is not None and ocean.port_client.is_run_in_progress(run):
        logger.warning(f"Pipeline {pipeline_id} poll timed out for run {run.id}")
        await ocean.port_client.report_run_failure(
            run,
            "Timed out waiting for GitLab pipeline completion",
            should_raise=False,
        )
