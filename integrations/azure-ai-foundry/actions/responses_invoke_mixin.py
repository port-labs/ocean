from __future__ import annotations

from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun, WorkflowNodeRunStatus

from helpers.invoke_completion import (
    INVOCATION_SUBMITTED_STATUS_LABEL,
    complete_invoke_run_for_response,
    complete_invoke_run_from_sse,
)
from helpers.invoke_mode import invoke_agent_completion_mode
from helpers.webhook_scope import build_response_external_id
from stream_manager import get_stream_manager

INVOKE_RUNNING_STATUS_LABEL = "Awaiting response"
INVOKE_STARTING_STATUS_LABEL = "Invoking"


class ResponsesInvokeMixin:
    """Shared Responses API invoke + SSE streaming for agent and model actions."""

    client: Any
    project_endpoint: str

    async def execute_responses_invoke(
        self,
        run: IntegrationRun,
        *,
        invoke_label: str,
        stream_key: str,
        invoke_url: str,
        params: dict[str, Any],
        body: dict[str, Any],
        agent_id: str | None,
        bind_output: dict[str, Any],
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
        use_background, _ = invoke_agent_completion_mode(
            report_invocation_status=report_invocation_status
        )
        await_webhook_completion = use_background
        if complete_on_sse_terminal is None:
            complete_on_sse_terminal = (
                not early_complete_on_bind and not await_webhook_completion
            )

        invoke_body = dict(body)
        if use_background:
            invoke_body["background"] = True

        await self._execute_with_sse_completion(
            run,
            invoke_url=invoke_url,
            params=params,
            body=invoke_body,
            stream_key=stream_key,
            agent_id=agent_id,
            bind_output=bind_output,
            early_complete_on_bind=early_complete_on_bind,
            complete_on_sse_terminal=complete_on_sse_terminal,
            await_webhook_completion=await_webhook_completion,
        )

    async def _execute_with_sse_completion(
        self,
        run: IntegrationRun,
        *,
        invoke_url: str,
        params: dict[str, Any],
        body: dict[str, Any],
        stream_key: str,
        agent_id: str | None,
        bind_output: dict[str, Any],
        early_complete_on_bind: bool = False,
        complete_on_sse_terminal: bool = True,
        await_webhook_completion: bool = False,
    ) -> None:
        submitted_after_bind = False

        async def on_response_id(response_id: str) -> None:
            nonlocal submitted_after_bind
            await self._bind_run_to_response(
                run, response_id=response_id, bind_output=bind_output
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

        async def on_terminal_sse(parsed: dict[str, Any]) -> None:
            if complete_on_sse_terminal:
                await complete_invoke_run_from_sse(run, parsed)

        manager = get_stream_manager()
        started = await manager.track(
            stream_key=stream_key,
            invoke_url=invoke_url,
            params=params,
            response_body=body,
            run=run,
            on_response_id=on_response_id,
            stop_on_terminal_sse=complete_on_sse_terminal,
            on_terminal_sse=on_terminal_sse if complete_on_sse_terminal else None,
        )
        if started:
            return

        logger.warning(
            f"Responses stream already active for {stream_key}; not starting a second invoke"
        )

    async def _bind_run_to_response(
        self,
        run: IntegrationRun,
        *,
        response_id: str,
        bind_output: dict[str, Any],
    ) -> None:
        if not ocean.port_client.is_run_in_progress(run):
            logger.debug(
                f"Skipping bind for run {run.id}; already terminal "
                f"(response {response_id})"
            )
            return
        external_id = build_response_external_id(response_id)
        extra_output = {**bind_output, "responseId": response_id}
        if isinstance(run, WorkflowNodeRun):
            output = {**run.output, **extra_output}
            await ocean.port_client.patch_wf_node_run(
                run.id,
                {
                    "status": WorkflowNodeRunStatus.IN_PROGRESS,
                    "externalRunId": external_id,
                    "output": output,
                    "statusLabel": {"text": INVOKE_RUNNING_STATUS_LABEL},
                },
                should_raise=False,
            )
            run.output = output
        else:
            await ocean.port_client.patch_action_run(
                run.id,
                {
                    "externalRunId": external_id,
                    "statusLabel": INVOKE_RUNNING_STATUS_LABEL,
                },
            )
            run.output.update(extra_output)
        logger.info(
            f"Bound run {run.id} to Foundry response {response_id} (external {external_id})"
        )
