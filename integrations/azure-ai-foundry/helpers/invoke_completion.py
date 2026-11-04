from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun

from helpers.conversation_catalog import (
    conversation_row_from_response,
    register_catalog_conversation,
)
from helpers.model_responses_api import fetch_foundry_response
from helpers.responses_catalog import catalog_agent_id, normalize_foundry_response
from helpers.webhook_scope import (
    build_response_external_id,
    extract_assistant_text_from_response,
    usage_from_response,
)
from helpers.project_scope import enrich_with_project
from helpers.catalog_sync import normalize_catalog_payload
from integration import ObjectKind
from port_ocean.context.event import EventType, event_context

COMPLETED_STATUS_LABEL = "Response completed"
FAILED_STATUS_LABEL = "Response failed"
INVOCATION_SUBMITTED_STATUS_LABEL = "Invoke submitted"

_completion_lock = asyncio.Lock()
_completed_invoke_run_ids: set[str] = set()

_TERMINAL_SSE_TYPES = {
    "response.completed": True,
    "response.failed": False,
    "response.cancelled": False,
    "response.incomplete": False,
}


def response_body_from_sse_event(parsed: dict[str, Any]) -> dict[str, Any] | None:
    response = parsed.get("response")
    return response if isinstance(response, dict) else None


def success_for_terminal_event(event_type: str) -> bool | None:
    if event_type in _TERMINAL_SSE_TYPES:
        return _TERMINAL_SSE_TYPES[event_type]
    return None


async def register_catalog_response_from_body(
    response_body: dict[str, Any],
    run: IntegrationRun,
    *,
    fallback_agent_id: str | None = None,
) -> None:
    row = normalize_foundry_response(response_body)
    if row is None:
        return
    if not row.get("agent_id") and fallback_agent_id:
        row["agent_id"] = catalog_agent_id(fallback_agent_id)
    try:
        batch = [
            enrich_with_project(
                normalize_catalog_payload(ObjectKind.RESPONSE, row)
            )
        ]
        await ocean.integration.port_app_config_handler.get_port_app_config(
            use_cache=False
        )
        async with event_context(EventType.HTTP_REQUEST, trigger_type="machine"):
            await ocean.register_raw(ObjectKind.RESPONSE, batch)
    except Exception as error:
        logger.warning(
            f"Failed to register response {row.get('id')} in catalog (continuing): {error}"
        )
        await ocean.port_client.post_run_log(
            run,
            f"Catalog response upsert failed: {error}",
            level="WARNING",
            should_raise=False,
        )


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
    async with _completion_lock:
        if run.id in _completed_invoke_run_ids:
            return False
        if not ocean.port_client.is_run_in_progress(run):
            _completed_invoke_run_ids.add(run.id)
            return False
        _completed_invoke_run_ids.add(run.id)

    agent_id = str(
        run.execution_properties.get("agentId") or run.output.get("agentId") or ""
    )
    extra_output: dict[str, Any] = {"responseId": response_id}
    if isinstance(response_body, dict):
        extra_output.update(usage_from_response(response_body))
        text = extract_assistant_text_from_response(response_body)
        if text:
            extra_output["response"] = text
        conversation = response_body.get("conversation")
        if isinstance(conversation, dict) and conversation.get("id"):
            extra_output["conversationId"] = conversation["id"]
        elif response_body.get("conversation_id"):
            extra_output["conversationId"] = response_body["conversation_id"]

    if isinstance(run, WorkflowNodeRun):
        run.output.update(extra_output)

    if isinstance(response_body, dict):
        await register_catalog_response_from_body(
            response_body, run, fallback_agent_id=agent_id or None
        )
        if success:
            row = conversation_row_from_response(
                response_body, agent_id=agent_id or None
            )
            if row:
                await register_catalog_conversation(row, run)

    if not keep_stream:
        from stream_manager import get_stream_manager

        await get_stream_manager().untrack_for_run(run.id)

    resolved_label = status_label
    if resolved_label is None:
        resolved_label = (
            COMPLETED_STATUS_LABEL if success else FAILED_STATUS_LABEL
        )

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
    success = event_type == "response.completed"
    response_body = await fetch_foundry_response(response_id)
    return await complete_invoke_run_for_response(
        run,
        response_id=response_id,
        response_body=response_body,
        success=success,
        source=f"Foundry webhook {event_type}",
        keep_stream=True,
    )


async def complete_invoke_run_from_sse(
    run: IntegrationRun, parsed: dict[str, Any]
) -> bool:
    event_type = parsed.get("type")
    if not isinstance(event_type, str):
        return False
    success = success_for_terminal_event(event_type)
    if success is None:
        return False
    response_body = response_body_from_sse_event(parsed)
    response_id = str(
        (response_body or {}).get("id")
        or run.output.get("responseId")
        or ""
    )
    if not response_id:
        return False
    if response_body is None or not response_body.get("usage"):
        fetched = await fetch_foundry_response(response_id)
        if fetched:
            response_body = fetched
    return await complete_invoke_run_for_response(
        run,
        response_id=response_id,
        response_body=response_body,
        success=success,
        source=f"Responses SSE {event_type}",
    )


async def find_in_progress_run_for_response(response_id: str) -> IntegrationRun | None:
    run = await ocean.port_client.find_run_by_external_id(
        build_response_external_id(response_id)
    )
    if run is None or not ocean.port_client.is_run_in_progress(run):
        return None
    return run
