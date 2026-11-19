from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger
from port_ocean.context.event import EventType, event_context
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
from azure_integration.foundry.helpers.responses_catalog import (
    catalog_agent_id,
    conversation_row_from_response,
    normalize_foundry_response,
)
from azure_integration.foundry.helpers.responses_stream import (
    TERMINAL_SSE_TYPES,
    ResponsesSseEvent,
)
from azure_integration.foundry.helpers.utils import (
    agent_openai_protocol_path,
    enrich_with_project,
)
from azure_integration.foundry.helpers.webhook_scope import FoundryResponseBody
from azure_integration.foundry.kinds import ObjectKind

COMPLETED_STATUS_LABEL = "Response completed"
FAILED_STATUS_LABEL = "Response failed"
INVOCATION_SUBMITTED_STATUS_LABEL = "Invoke submitted"

_completion_lock = asyncio.Lock()
_MAX_COMPLETED = 1024
_completed_invoke_run_ids: dict[str, None] = {}
_completed_response_ids: dict[str, None] = {}


def _trim(cache: dict[str, None]) -> None:
    while len(cache) > _MAX_COMPLETED:
        cache.pop(next(iter(cache)))


def _remember(run_id: str, response_id: str = "") -> None:
    _completed_invoke_run_ids[run_id] = None
    _trim(_completed_invoke_run_ids)
    if response_id:
        _completed_response_ids[response_id] = None
        _trim(_completed_response_ids)


def _forget(run_id: str, response_id: str = "") -> None:
    _completed_invoke_run_ids.pop(run_id, None)
    if response_id:
        _completed_response_ids.pop(response_id, None)


def is_response_completion_claimed(response_id: str) -> bool:
    return bool(response_id) and response_id in _completed_response_ids


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


async def fetch_foundry_response(
    response_id: str,
    *,
    project_endpoint: str,
    agent_id: str | None = None,
) -> dict[str, Any] | None:
    """GET stored Responses body. Agent invokes try agent protocol path first."""
    client = create_foundry_client()
    paths: list[str] = []
    if agent_id and agent_id.strip():
        paths.append(
            f"{agent_openai_protocol_path(agent_id.strip(), 'responses')}/{response_id}"
        )
    paths.append(f"openai/v1/responses/{response_id}")
    last_error: Exception | None = None
    for path in paths:
        try:
            payload = await client.send_api_request(
                client.build_url(project_endpoint, path), method="GET"
            )
        except Exception as error:
            last_error = error
            continue
        if isinstance(payload, dict) and payload:
            return payload
    if last_error is not None:
        logger.warning(f"Failed to GET Foundry response {response_id}: {last_error}")
    return None


async def register_catalog_rows(
    kind: str,
    raws: list[dict[str, Any]],
    run: IntegrationRun | None = None,
    *,
    project_endpoint: str | None = None,
) -> bool:
    if not raws:
        return False
    endpoint = project_endpoint or (
        _project_endpoint_from_run(run) if run is not None else None
    )
    try:
        batch = [
            (
                enrich_with_project(raw, project_endpoint=endpoint)
                if endpoint
                else dict(raw)
            )
            for raw in raws
        ]
        await ocean.integration.port_app_config_handler.get_port_app_config(
            use_cache=False
        )
        async with event_context(EventType.HTTP_REQUEST, trigger_type="machine"):
            await ocean.register_raw(kind, batch)
        return True
    except Exception as error:
        message = (
            f"Failed to upsert {len(raws)} {kind} entit(y/ies) into the catalog "
            f"(continuing): {error}"
        )
        logger.warning(message)
        if run is not None:
            await ocean.port_client.post_run_log(
                run, message, level="WARNING", should_raise=False
            )
        return False


async def response_body_for_catalog(
    response_id: str,
    response_body: dict[str, Any] | None,
    *,
    project_endpoint: str,
    agent_id: str | None = None,
) -> dict[str, Any] | None:
    """Prefer GET so usage/model/conversation exist for mapping."""
    if (
        response_body is not None
        and response_body.get("usage")
        and (
            response_body.get("model")
            or response_body.get("conversation")
            or response_body.get("conversation_id")
        )
    ):
        return response_body
    fetched = await fetch_foundry_response(
        response_id, project_endpoint=project_endpoint, agent_id=agent_id
    )
    return fetched or response_body


async def register_catalog_response_from_body(
    response_body: dict[str, Any],
    run: IntegrationRun,
    *,
    fallback_agent_id: str | None = None,
    fallback_model_deployment_id: str | None = None,
) -> bool:
    row = normalize_foundry_response(response_body)
    if row is None:
        return False
    if not row.get("agent_id") and fallback_agent_id:
        row["agent_id"] = catalog_agent_id(fallback_agent_id)
    if not row.get("model_deployment_id") and fallback_model_deployment_id:
        row["model_deployment_id"] = fallback_model_deployment_id.strip()
    return await register_catalog_rows(ObjectKind.FOUNDRY_RESPONSE, [row], run)


async def complete_invoke_run_for_response(
    run: IntegrationRun,
    *,
    response_id: str,
    response_body: dict[str, Any] | None,
    success: bool,
    source: str,
    status_label: str | None = None,
    keep_stream: bool = False,
    register_catalog: bool = False,
    post_answer_log: bool = False,
) -> bool:
    """Attach usage/output and close the wf run. Returns False if already terminal."""
    async with _completion_lock:
        if (
            run.id in _completed_invoke_run_ids
            or response_id in _completed_response_ids
        ):
            return False
        if not ocean.port_client.is_run_in_progress(run):
            _remember(run.id, response_id)
            return False

    prior = run.output if isinstance(run, WorkflowNodeRun) else {}
    agent_id = str(
        run.execution_properties.get("agentId") or prior.get("agentId") or ""
    )
    deployment_name = str(
        run.execution_properties.get("deploymentName")
        or prior.get("deploymentName")
        or ""
    ).strip()
    project_endpoint = _project_endpoint_from_run(run)

    if response_body is None and not project_endpoint:
        logger.error(
            f"Cannot complete invoke run {run.id}: projectEndpoint unresolved "
            f"(response {response_id})"
        )
        async with _completion_lock:
            if (
                run.id in _completed_invoke_run_ids
                or response_id in _completed_response_ids
            ):
                return False
            _remember(run.id, response_id)
        try:
            await ocean.port_client.report_run_completed(
                run, False, status_label=FAILED_STATUS_LABEL, should_raise=True
            )
            if isinstance(run, WorkflowNodeRun):
                run.status = WorkflowNodeRunStatus.COMPLETED
        except Exception:
            async with _completion_lock:
                _forget(run.id, response_id)
            raise
        return True

    display_body = (
        await response_body_for_catalog(
            response_id,
            response_body,
            project_endpoint=project_endpoint,
            agent_id=agent_id or None,
        )
        if project_endpoint
        else response_body
    )
    if response_body is None and not isinstance(display_body, dict):
        logger.warning(
            f"Foundry GET returned no body for response {response_id} "
            f"(run {run.id}); completing without answer/usage"
        )

    slim, success_override = FoundryResponseBody.invoke_run_output(
        response_id=response_id,
        display_body=display_body if isinstance(display_body, dict) else None,
        prior_conversation_id=(
            str(prior["conversationId"]) if prior.get("conversationId") else None
        ),
    )
    if success_override is not None:
        success = success_override
    if isinstance(run, WorkflowNodeRun):
        run.output = {**(prior if isinstance(prior, dict) else {}), **slim}

    async with _completion_lock:
        if (
            run.id in _completed_invoke_run_ids
            or response_id in _completed_response_ids
        ):
            return False
        _remember(run.id, response_id)

    try:
        if register_catalog and success and isinstance(display_body, dict):
            await register_catalog_response_from_body(
                display_body,
                run,
                fallback_agent_id=agent_id or None,
                fallback_model_deployment_id=deployment_name or None,
            )
            conv = conversation_row_from_response(
                display_body, agent_id=agent_id or None
            )
            if conv:
                await register_catalog_rows(
                    ObjectKind.FOUNDRY_CONVERSATION, [conv], run
                )

        if post_answer_log:
            answer = slim.get("answer")
            if isinstance(answer, str) and answer.strip():
                await ocean.port_client.post_run_log(run, answer, should_raise=False)

        if not keep_stream:
            from azure_integration.foundry.stream_manager import get_stream_manager

            await get_stream_manager().untrack_for_run(run.id)

        label = status_label or (
            COMPLETED_STATUS_LABEL if success else FAILED_STATUS_LABEL
        )
        logger.info(
            f"Completing run {run.id} from {source} "
            f"(response {response_id}, success={success})"
        )
        await ocean.port_client.report_run_completed(
            run, success, status_label=label, should_raise=True
        )
        if isinstance(run, WorkflowNodeRun):
            run.status = WorkflowNodeRunStatus.COMPLETED
    except Exception:
        async with _completion_lock:
            _forget(run.id, response_id)
        raise
    return True


async def complete_invoke_run_from_webhook(
    run: IntegrationRun, *, event_type: str, response_id: str
) -> bool:
    if is_response_completion_claimed(response_id):
        return False
    success = event_type == "response.completed"
    return await complete_invoke_run_for_response(
        run,
        response_id=response_id,
        response_body=None,
        success=success,
        source=f"Foundry webhook {event_type}",
        register_catalog=success,
        post_answer_log=True,
    )


async def complete_invoke_run_from_sse(
    run: IntegrationRun, parsed: ResponsesSseEvent
) -> bool:
    success = TERMINAL_SSE_TYPES.get(parsed.type)
    if success is None:
        return False
    response_body = parsed.response
    bound = run.output.get("responseId") if isinstance(run, WorkflowNodeRun) else None
    response_id = str((response_body or {}).get("id") or bound or "")
    if not response_id or is_response_completion_claimed(response_id):
        return False
    return await complete_invoke_run_for_response(
        run,
        response_id=response_id,
        response_body=response_body,
        success=success,
        source=f"Responses SSE {parsed.type}",
        register_catalog=success,
    )


async def find_in_progress_run_for_response(response_id: str) -> IntegrationRun | None:
    if is_response_completion_claimed(response_id):
        return None
    run = await ocean.port_client.find_run_by_external_id(response_id)
    if run is None or not ocean.port_client.is_run_in_progress(run):
        return None
    return run
