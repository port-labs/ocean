from __future__ import annotations

from typing import Any

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import (
    IntegrationRun,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)

from azure_integration.foundry.clients.http.foundry_client import create_foundry_client
from azure_integration.foundry.core.exporters.project_exporter import (
    foundry_project_from_arm_id,
)
from azure_integration.foundry.core.exporters.responses_exporter import (
    ResponsesExporter,
)
from azure_integration.foundry.core.options import EndpointScope, SingleResponseOptions
from azure_integration.foundry.helpers.responses_stream import ResponsesSseEvent
from azure_integration.foundry.helpers.utils import project_name_from_endpoint
from azure_integration.foundry.models.responses import TERMINAL_EVENTS, Response

COMPLETED_STATUS_LABEL = "Response completed"
FAILED_STATUS_LABEL = "Response failed"
INVOCATION_SUBMITTED_STATUS_LABEL = "Invoke submitted"


def _endpoint_from_arm_id(arm_id: Any) -> str | None:
    if not isinstance(arm_id, str) or not arm_id.strip() or "{{" in arm_id:
        return None
    project = foundry_project_from_arm_id(arm_id.strip())
    return project.endpoint.rstrip("/") if project else None


def _project_endpoint_from_run(run: IntegrationRun) -> str | None:
    # Prefer bound run.output (resolved) over execution_properties (may be JQ).
    sources: list[Any] = []
    if isinstance(run, WorkflowNodeRun) and isinstance(run.output, dict):
        sources.append(run.output)
    sources.append(run.execution_properties or {})
    for src in sources:
        endpoint = src.get("projectEndpoint")
        if (
            isinstance(endpoint, str)
            and endpoint.strip()
            and "{{" not in endpoint
            and endpoint.casefold().startswith(("http://", "https://"))
        ):
            return endpoint.rstrip("/")
        resolved = _endpoint_from_arm_id(src.get("projectArmId"))
        if resolved:
            return resolved
    return None


async def complete_invoke_run_for_response(
    run: IntegrationRun,
    *,
    response_id: str,
    response_body: dict[str, Any] | None,
    success: bool,
    source: str,
    status_label: str | None = None,
    keep_stream: bool = False,
) -> bool:
    """Attach usage/output and close the wf run. Returns False if already terminal."""
    if not ocean.port_client.is_run_in_progress(run):
        return False

    if isinstance(run, WorkflowNodeRun):
        run.output = {
            **run.output,
            **Response.model_validate(response_body).run_output(
                response_id=response_id
            ),
        }

    if not keep_stream:
        from azure_integration.foundry.stream_manager import get_stream_manager

        await get_stream_manager().untrack_for_run(run.id)

    logger.info(
        f"Completing run {run.id} from {source} "
        f"(response {response_id}, success={success})"
    )
    await ocean.port_client.report_run_completed(
        run,
        success,
        status_label=status_label
        or (COMPLETED_STATUS_LABEL if success else FAILED_STATUS_LABEL),
        should_log=False,
    )
    return True


async def complete_invoke_run_from_webhook(
    run: IntegrationRun, *, event_type: str, response_id: str
) -> bool:
    project_endpoint = _project_endpoint_from_run(run)
    if not project_endpoint:
        logger.error(
            f"Cannot complete invoke run {run.id}: projectEndpoint unresolved "
            f"(response {response_id})"
        )
        await ocean.port_client.report_run_completed(
            run,
            False,
            status_label=FAILED_STATUS_LABEL,
            should_log=False,
        )
        return False

    prior = run.output if isinstance(run, WorkflowNodeRun) else {}
    agent_id = (
        str(
            run.execution_properties.get("agentId")
            or (prior.get("agentId") if isinstance(prior, dict) else None)
            or ""
        )
        or None
    )
    body = await ResponsesExporter(create_foundry_client()).get_resource(
        SingleResponseOptions(
            project_endpoint=project_endpoint,
            project_id=project_name_from_endpoint(project_endpoint),
            resource_id=response_id,
            endpoint_scope=(EndpointScope.AGENT if agent_id else EndpointScope.PROJECT),
            agent_id=agent_id,
        )
    )
    if body is None:
        logger.warning(
            f"Foundry GET returned no body for response {response_id} "
            f"(run {run.id}); completing without answer/usage"
        )

    return await complete_invoke_run_for_response(
        run,
        response_id=response_id,
        response_body=body,
        success=TERMINAL_EVENTS.get(event_type, False),
        source=f"Foundry webhook {event_type}",
    )


async def complete_invoke_run_from_sse(
    run: IntegrationRun, parsed: ResponsesSseEvent
) -> bool:
    success = TERMINAL_EVENTS.get(parsed.type)
    if success is None:
        return False
    response_body = parsed.response
    bound = run.output.get("responseId") if isinstance(run, WorkflowNodeRun) else None
    response_id = str((response_body or {}).get("id") or bound or "")
    if not response_id:
        return False
    return await complete_invoke_run_for_response(
        run,
        response_id=response_id,
        response_body=response_body,
        success=success,
        source=f"Responses SSE {parsed.type}",
    )
