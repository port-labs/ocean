from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)

from azure_integration.foundry.webhook_processors.conversation_webhook_processor import (
    ConversationWebhookProcessor,
)


def _run(*, report: bool | None) -> WorkflowNodeRun:
    props: dict = {}
    if report is not None:
        props["reportInvocationStatus"] = report
    return WorkflowNodeRun(
        id="wfnr_1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="azure",
            integrationProvider="azure",
            integrationInvocationType="invoke_agent",
            integrationActionExecutionProperties=props,
        ),
    )


@pytest.mark.asyncio
async def test_authenticate_always_allows() -> None:
    processor = ConversationWebhookProcessor(event=MagicMock())
    assert await processor.authenticate({}, {"webhook-id": "1"}) is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("report", "should_complete"),
    [(None, False), (False, False), (True, True)],
)
async def test_handle_event_respects_report_invocation_status_default(
    report: bool | None, should_complete: bool
) -> None:
    processor = ConversationWebhookProcessor(event=MagicMock())
    payload = {
        "type": "response.completed",
        "id": "evt_1",
        "data": {"id": "resp_1"},
    }
    run = _run(report=report)
    with (
        patch(
            "azure_integration.foundry.webhook_processors.conversation_webhook_processor."
            "is_response_completion_claimed",
            return_value=False,
        ),
        patch(
            "azure_integration.foundry.webhook_processors.conversation_webhook_processor."
            "find_in_progress_run_for_response",
            new_callable=AsyncMock,
            return_value=run,
        ),
        patch(
            "azure_integration.foundry.webhook_processors.conversation_webhook_processor."
            "complete_invoke_run_from_webhook",
            new_callable=AsyncMock,
        ) as complete,
    ):
        await processor.handle_event(payload, None)

    if should_complete:
        complete.assert_awaited_once()
    else:
        complete.assert_not_awaited()
