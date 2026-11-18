from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger
from port_ocean.context.event import EventType, event_context
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun

from azure_integration.foundry.core.exporters.project_exporter import (
    foundry_project_from_arm_id,
)
from azure_integration.foundry.helpers.model_responses_api import fetch_foundry_response
from azure_integration.foundry.helpers.responses_catalog import (
    catalog_agent_id,
    conversation_row_from_response,
    normalize_foundry_response,
)
from azure_integration.foundry.helpers.responses_stream import (
    ResponsesSseEvent,
    success_for_terminal_sse_event,
)
from azure_integration.foundry.helpers.utils import enrich_with_project
from azure_integration.foundry.helpers.webhook_scope import (
    extract_assistant_text_from_response,
    usage_from_response,
)
from azure_integration.foundry.kinds import ObjectKind

COMPLETED_STATUS_LABEL = "Response completed"
FAILED_STATUS_LABEL = "Response failed"
INVOCATION_SUBMITTED_STATUS_LABEL = "Invoke submitted"

_completion_lock = asyncio.Lock()
_MAX_COMPLETED = 1024
# Claimed completions: webhook/SSE race — skip second path (incl. Foundry GET).
_completed_invoke_run_ids: dict[str, None] = {}
_completed_response_ids: dict[str, None] = {}


def _trim(cache: dict[str, None]) -> None:
    while len(cache) > _MAX_COMPLETED:
        cache.pop(next(iter(cache)))


def _remember_completed(run_id: str, response_id: str = "") -> None:
    _completed_invoke_run_ids[run_id] = None
    _trim(_completed_invoke_run_ids)
    if response_id:
        _completed_response_ids[response_id] = None
        _trim(_completed_response_ids)


def is_response_completion_claimed(response_id: str) -> bool:
    return bool(response_id) and response_id in _completed_response_ids


def response_body_from_sse_event(
    parsed: ResponsesSseEvent,
) -> dict[str, Any] | None:
    return parsed.response


def _is_unresolved_template(value: str) -> bool:
    return "{{" in value


def _looks_like_resolved_project_endpoint(value: str) -> bool:
    endpoint = value.strip()
    if not endpoint or _is_unresolved_template(endpoint):
        return False
    lower = endpoint.casefold()
    return lower.startswith("http://") or lower.startswith("https://")


def _endpoint_from_arm_id(arm_id: str | None) -> str | None:
    if (
        not isinstance(arm_id, str)
        or not arm_id.strip()
        or _is_unresolved_template(arm_id)
    ):
        return None
    project = foundry_project_from_arm_id(arm_id.strip())
    if project is None:
        return None
    return project.endpoint.rstrip("/")


def _project_endpoint_from_run(run: IntegrationRun) -> str | None:
    # Prefer bound run.output (resolved ids) over execution_properties (may still
    # hold unresolved JQ like "{{ .outputs... }}").
    sources: list[Any] = []
    prior = run.output if isinstance(run, WorkflowNodeRun) else None
    if isinstance(prior, dict):
        sources.append(prior)
    sources.append(run.execution_properties or {})
    for src in sources:
        endpoint = src.get("projectEndpoint")
        if isinstance(endpoint, str) and _looks_like_resolved_project_endpoint(endpoint):
            return endpoint.rstrip("/")
        resolved = _endpoint_from_arm_id(src.get("projectArmId"))
        if resolved:
            return resolved
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
) -> dict[str, Any] | None:
    """Prefer a GET response payload so usage/model/conversation fields exist for mapping."""
    if response_body is None:
        return await fetch_foundry_response(
            response_id, project_endpoint=project_endpoint
        )
    needs_fetch = not response_body.get("usage") or not (
        response_body.get("model")
        or response_body.get("conversation")
        or response_body.get("conversation_id")
    )
    if not needs_fetch:
        return response_body
    fetched = await fetch_foundry_response(
        response_id, project_endpoint=project_endpoint
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
) -> bool:
    """Attach usage/output and close the wf run. Returns False if already terminal."""
    async with _completion_lock:
        if run.id in _completed_invoke_run_ids or response_id in _completed_response_ids:
            return False
        if not ocean.port_client.is_run_in_progress(run):
            _remember_completed(run.id, response_id)
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
            if run.id in _completed_invoke_run_ids or response_id in _completed_response_ids:
                return False
            _remember_completed(run.id, response_id)
        await ocean.port_client.report_run_completed(
            run,
            False,
            status_label=FAILED_STATUS_LABEL,
            should_raise=False,
        )
        return True

    # Always prefer a GET so usage/model/conversation exist (webhook payload is id-only).
    display_body = (
        await response_body_for_catalog(
            response_id, response_body, project_endpoint=project_endpoint
        )
        if project_endpoint
        else response_body
    )
    # Slim run output: ids + answer text + token usage only.
    slim: dict[str, Any] = {"responseId": response_id}
    if prior.get("conversationId"):
        slim["conversationId"] = prior["conversationId"]
    if isinstance(display_body, dict):
        slim.update(usage_from_response(display_body))
        text = extract_assistant_text_from_response(display_body)
        if text:
            slim["answer"] = text
        conversation = display_body.get("conversation")
        if isinstance(conversation, dict) and conversation.get("id"):
            slim["conversationId"] = conversation["id"]
        elif display_body.get("conversation_id"):
            slim["conversationId"] = display_body["conversation_id"]

    if isinstance(run, WorkflowNodeRun):
        run.output = slim

    async with _completion_lock:
        if run.id in _completed_invoke_run_ids or response_id in _completed_response_ids:
            return False
        _remember_completed(run.id, response_id)

    if register_catalog and isinstance(display_body, dict):
        await register_catalog_response_from_body(
            display_body,
            run,
            fallback_agent_id=agent_id or None,
            fallback_model_deployment_id=deployment_name or None,
        )
        if success:
            row = conversation_row_from_response(
                display_body, agent_id=agent_id or None
            )
            if row:
                await register_catalog_rows(ObjectKind.FOUNDRY_CONVERSATION, [row], run)

    if not keep_stream:
        from azure_integration.foundry.stream_manager import get_stream_manager

        await get_stream_manager().untrack_for_run(run.id)

    resolved_label = status_label
    if resolved_label is None:
        resolved_label = COMPLETED_STATUS_LABEL if success else FAILED_STATUS_LABEL

    logger.info(
        f"Completing run {run.id} from {source} "
        f"(response {response_id}, success={success})"
    )
    await ocean.port_client.report_run_completed(
        run,
        success,
        status_label=resolved_label,
        should_raise=False,
    )
    return True


async def complete_invoke_run_from_webhook(
    run: IntegrationRun,
    *,
    event_type: str,
    response_id: str,
) -> bool:
    if is_response_completion_claimed(response_id):
        logger.debug(
            f"Skipping Foundry webhook {event_type} for {response_id}; "
            "already completed (SSE or prior webhook)"
        )
        return False
    success = event_type == "response.completed"
    # Option C: untrack (cancel → flush buffer) before report_run_completed.
    return await complete_invoke_run_for_response(
        run,
        response_id=response_id,
        response_body=None,  # force GET via response_body_for_catalog
        success=success,
        source=f"Foundry webhook {event_type}",
        register_catalog=success,
    )


async def complete_invoke_run_from_sse(
    run: IntegrationRun, parsed: ResponsesSseEvent
) -> bool:
    success = success_for_terminal_sse_event(parsed.type)
    if success is None:
        return False
    response_body = response_body_from_sse_event(parsed)
    bound_response_id = (
        run.output.get("responseId") if isinstance(run, WorkflowNodeRun) else None
    )
    response_id = str((response_body or {}).get("id") or bound_response_id or "")
    if not response_id:
        return False
    if is_response_completion_claimed(response_id):
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
