from __future__ import annotations

from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import (
    IntegrationRun,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)
from port_ocean.exceptions.execution_manager import ActionExecutionError

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient
from azure_integration.foundry.helpers.invoke_completion import (
    INVOCATION_SUBMITTED_STATUS_LABEL,
    complete_invoke_run_for_response,
    complete_invoke_run_from_sse,
)
from azure_integration.foundry.models.responses import ResponsesSseEvent
from azure_integration.foundry.stream_manager import get_stream_manager

INVOKE_RUNNING_STATUS_LABEL = "Agent working"
MODEL_RUNNING_STATUS_LABEL = "Model thinking"
INVOKE_STARTING_STATUS_LABEL = "Invoking"


class ResponsesInvokeMixin:
    """Shared Responses API invoke + SSE streaming for agent and model actions."""

    def __init__(self, client: FoundryHttpClient) -> None:
        self.client = client

    async def execute_responses_invoke(
        self,
        run: IntegrationRun,
        *,
        invoke_label: str,
        stream_key: str,
        invoke_url: str,
        body: dict[str, Any],
        bind_output: dict[str, Any],
        running_status_label: str,
        params: dict[str, Any] | None = None,
        report_invocation_status: bool = False,
        early_complete_on_bind: bool = False,
        complete_on_sse_terminal: bool | None = None,
    ) -> None:
        await ocean.port_client.post_run_log(
            run,
            invoke_label,
            status_label=INVOKE_STARTING_STATUS_LABEL,
            should_raise=False,
        )
        if complete_on_sse_terminal is None:
            complete_on_sse_terminal = report_invocation_status

        invoke_body = dict(body)
        invoke_body["background"] = True
        # Background Responses require store=true (Foundry/OpenAI docs).
        invoke_body["store"] = True

        submitted_after_bind = False

        async def on_response_id(response_id: str) -> None:
            nonlocal submitted_after_bind
            await self._bind_run_to_response(
                run,
                response_id=response_id,
                bind_output=bind_output,
                running_status_label=running_status_label,
            )
            if not early_complete_on_bind or submitted_after_bind:
                return
            submitted_after_bind = True
            await complete_invoke_run_for_response(
                run,
                response_id=response_id,
                response_body=None,
                success=True,
                source="invoke submitted",
                status_label=INVOCATION_SUBMITTED_STATUS_LABEL,
                keep_stream=True,
            )

        async def on_terminal_sse(parsed: ResponsesSseEvent) -> None:
            if complete_on_sse_terminal:
                await complete_invoke_run_from_sse(run, parsed)

        manager = get_stream_manager()
        result = await manager.track(
            stream_key=stream_key,
            invoke_url=invoke_url,
            params=params,
            response_body=invoke_body,
            run=run,
            on_response_id=on_response_id,
            stop_on_terminal_sse=complete_on_sse_terminal,
            on_terminal_sse=on_terminal_sse if complete_on_sse_terminal else None,
        )
        if result == "started":
            return
        if result == "duplicate":
            raise ActionExecutionError(
                f"Responses stream already active for {stream_key}; "
                "not starting a second invoke"
            )

        # At stream capacity: non-SSE background POST; webhook/SSE-free completion.
        logger.warning(
            f"Foundry stream capacity reached; submitting {stream_key} without SSE "
            "(webhook completion if reportInvocationStatus)"
        )
        payload = await self.client.send_api_request(
            invoke_url,
            method="POST",
            params=params,
            json_body={**invoke_body, "stream": False},
        )
        response_id = (
            str(payload.get("id"))
            if isinstance(payload, dict) and payload.get("id")
            else ""
        )
        if not response_id:
            raise ActionExecutionError(
                f"Foundry invoke returned no response id for {stream_key}"
            )
        await on_response_id(response_id)
        if complete_on_sse_terminal and isinstance(payload, dict):
            # Best-effort: if body already terminal, complete now; else webhook.
            status = payload.get("status")
            if status in {"completed", "failed", "cancelled", "incomplete"}:
                await complete_invoke_run_for_response(
                    run,
                    response_id=response_id,
                    response_body=payload,
                    success=status == "completed",
                    source="non-SSE invoke (stream capacity)",
                )

    async def _bind_run_to_response(
        self,
        run: IntegrationRun,
        *,
        response_id: str,
        bind_output: dict[str, Any],
        running_status_label: str,
    ) -> None:
        if not ocean.port_client.is_run_in_progress(run):
            logger.debug(
                f"Skipping bind for run {run.id}; already terminal "
                f"(response {response_id})"
            )
            return
        output = {**bind_output, "responseId": response_id}
        if isinstance(run, WorkflowNodeRun):
            run.output = output
            await ocean.port_client.patch_wf_node_run(
                run.id,
                {
                    "status": WorkflowNodeRunStatus.IN_PROGRESS,
                    "externalRunId": response_id,
                    "output": output,
                    "statusLabel": {"text": running_status_label},
                },
            )
        else:
            await ocean.port_client.update_run_started(
                run, "", response_id, status_label=running_status_label
            )
        waiting = (
            "Waiting for model response"
            if running_status_label == MODEL_RUNNING_STATUS_LABEL
            else "Waiting for agent response"
        )
        await ocean.port_client.post_run_log(
            run, waiting, should_raise=False
        )
        logger.info(f"Bound run {run.id} to Foundry response {response_id}")
