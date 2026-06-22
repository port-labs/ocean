import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

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


async def fail_run_by_external_id(external_id: str, message: str) -> None:
    """Look up a run and report failure if it is still in progress."""
    run = await ocean.port_client.find_run_by_external_id(external_id)
    if run is not None and ocean.port_client.is_run_in_progress(run):
        await ocean.port_client.report_run_failure(
            run,
            message,
            should_raise=False,
        )


async def _fetch_poll_state(
    external_id: str,
    project_id: int,
    pipeline_id: int,
    get_pipeline: Callable[[int, int], Awaitable[dict[str, Any]]],
    *,
    concurrent: bool,
) -> tuple[dict[str, Any], ActionRun | WorkflowNodeRun] | None:
    """Return pipeline + run to keep polling, or None if the run is done/missing.

    On the first iteration both lookups run concurrently. Later iterations check
    Port first so a webhook completion during sleep avoids an extra GitLab call.
    """
    if concurrent:
        pipeline_result, run_result = await asyncio.gather(
            get_pipeline(project_id, pipeline_id),
            ocean.port_client.find_run_by_external_id(external_id),
            return_exceptions=True,
        )
        if isinstance(run_result, BaseException):
            raise run_result
        if run_result is None or not ocean.port_client.is_run_in_progress(run_result):
            return None
        if isinstance(pipeline_result, BaseException):
            raise pipeline_result
        return pipeline_result, run_result

    run = await ocean.port_client.find_run_by_external_id(external_id)
    if run is None or not ocean.port_client.is_run_in_progress(run):
        return None
    pipeline = await get_pipeline(project_id, pipeline_id)
    return pipeline, run


async def poll_pipeline_to_completion(
    external_id: str,
    project_id: int,
    pipeline_id: int,
    get_pipeline: Callable[[int, int], Awaitable[dict[str, Any]]],
    *,
    interval: int = 5,
    timeout: int = 30 * 60,
) -> None:
    """Poll GitLab for pipeline status until terminal, then complete the Port run."""
    max_attempts = timeout // interval

    try:
        for attempt in range(max_attempts):
            try:
                state = await _fetch_poll_state(
                    external_id,
                    project_id,
                    pipeline_id,
                    get_pipeline,
                    concurrent=attempt == 0,
                )
            except Exception as exc:
                logger.warning(
                    f"Failed to poll pipeline {pipeline_id}, retrying",
                    external_id=external_id,
                    attempt=attempt + 1,
                    error=str(exc),
                )
                await asyncio.sleep(interval)
                continue

            if state is None:
                return

            pipeline, _run = state
            if pipeline.get("status", "") in TERMINAL_PIPELINE_STATUSES:
                await complete_run_from_pipeline_status(
                    external_id,
                    pipeline["status"],
                    completion_source="poll",
                )
                return

            await asyncio.sleep(interval)

        logger.warning(
            f"Pipeline {pipeline_id} poll timed out",
            external_id=external_id,
        )
        await fail_run_by_external_id(
            external_id,
            "Timed out waiting for GitLab pipeline completion",
        )
    except Exception:
        logger.exception(
            f"Unexpected error while polling pipeline {pipeline_id}",
            external_id=external_id,
        )
        await fail_run_by_external_id(
            external_id,
            "Unexpected error while polling GitLab pipeline completion",
        )


def schedule_pipeline_poll(
    external_id: str,
    project_id: int,
    pipeline_id: int,
    get_pipeline: Callable[[int, int], Awaitable[dict[str, Any]]],
) -> None:
    """Start polling in the background; log any exception that escapes the poller."""
    task = asyncio.create_task(
        poll_pipeline_to_completion(
            external_id=external_id,
            project_id=project_id,
            pipeline_id=pipeline_id,
            get_pipeline=get_pipeline,
        )
    )

    def _log_task_failure(done_task: asyncio.Task[None]) -> None:
        if done_task.cancelled():
            return
        if exc := done_task.exception():
            logger.error(
                f"Pipeline poll task failed for pipeline {pipeline_id}",
                external_id=external_id,
                error=str(exc),
            )

    task.add_done_callback(_log_task_failure)
