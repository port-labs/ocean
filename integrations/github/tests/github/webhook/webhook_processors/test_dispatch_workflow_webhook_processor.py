from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)

from github.webhook.events import WORKFLOW_UPSERT_EVENTS
from github.webhook.webhook_processors.workflow_run.dispatch_workflow_webhook_processor import (
    DispatchWorkflowWebhookProcessor,
)

WORKFLOW_RUN = {
    "id": 12345,
    "status": "completed",
    "conclusion": "success",
    "actor": {"login": "alice"},
    "repository": {
        "id": 99,
        "owner": {"id": 1},
    },
}


def make_event(actor_login: str, status: str = "completed") -> WebhookEvent:
    workflow_run = {
        **WORKFLOW_RUN,
        "status": status,
        "actor": {"login": actor_login},
    }
    return WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "action": WORKFLOW_UPSERT_EVENTS[0],
            "workflow_run": workflow_run,
        },
        headers={"x-github-event": "workflow_run"},
    )


def make_identity_port_run() -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="wf-node-run-1",
        node_uid="node-1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationProvider="github",
            integrationInvocationType="dispatch_workflow",
            integrationActionExecutionProperties={},
        ),
        identity_token="identity.jwt",
    )


@pytest.fixture
def processor() -> DispatchWorkflowWebhookProcessor:
    return DispatchWorkflowWebhookProcessor(event=MagicMock())


@pytest.mark.asyncio
class TestDispatchWorkflowWebhookProcessor:
    async def test_accepts_integration_actor(
        self, processor: DispatchWorkflowWebhookProcessor
    ) -> None:
        with patch(
            "github.webhook.webhook_processors.workflow_run.dispatch_workflow_webhook_processor.get_auth_provider",
            return_value=MagicMock(
                get_integration_actor=AsyncMock(return_value="port-bot[bot]")
            ),
        ):
            assert await processor._should_process_event(make_event("port-bot[bot]"))

    async def test_rejects_unrelated_human_actor(
        self, processor: DispatchWorkflowWebhookProcessor
    ) -> None:
        with (
            patch(
                "github.webhook.webhook_processors.workflow_run.dispatch_workflow_webhook_processor.get_auth_provider",
                return_value=MagicMock(
                    get_integration_actor=AsyncMock(return_value="port-bot[bot]")
                ),
            ),
            patch(
                "github.webhook.webhook_processors.workflow_run.dispatch_workflow_webhook_processor.ocean"
            ) as mock_ocean,
        ):
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(
                return_value=None
            )
            assert not await processor._should_process_event(make_event("stranger"))

    async def test_accepts_identity_run_human_actor(
        self, processor: DispatchWorkflowWebhookProcessor
    ) -> None:
        port_run = make_identity_port_run()
        with (
            patch(
                "github.webhook.webhook_processors.workflow_run.dispatch_workflow_webhook_processor.get_auth_provider",
                return_value=MagicMock(
                    get_integration_actor=AsyncMock(return_value="port-bot[bot]")
                ),
            ),
            patch(
                "github.webhook.webhook_processors.workflow_run.dispatch_workflow_webhook_processor.ocean"
            ) as mock_ocean,
            patch(
                "github.webhook.webhook_processors.workflow_run.dispatch_workflow_webhook_processor.resolve_user_token",
                new=AsyncMock(return_value="gho_alice"),
            ),
            patch(
                "github.webhook.webhook_processors.workflow_run.dispatch_workflow_webhook_processor.PersonalTokenAuthenticator"
            ) as mock_authenticator_cls,
        ):
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(
                return_value=port_run
            )
            mock_authenticator_cls.return_value.get_authenticated_actor = AsyncMock(
                return_value="alice"
            )

            assert await processor._should_process_event(make_event("alice"))

    async def test_rejects_identity_run_with_wrong_human_actor(
        self, processor: DispatchWorkflowWebhookProcessor
    ) -> None:
        port_run = make_identity_port_run()
        with (
            patch(
                "github.webhook.webhook_processors.workflow_run.dispatch_workflow_webhook_processor.get_auth_provider",
                return_value=MagicMock(
                    get_integration_actor=AsyncMock(return_value="port-bot[bot]")
                ),
            ),
            patch(
                "github.webhook.webhook_processors.workflow_run.dispatch_workflow_webhook_processor.ocean"
            ) as mock_ocean,
            patch(
                "github.webhook.webhook_processors.workflow_run.dispatch_workflow_webhook_processor.resolve_user_token",
                new=AsyncMock(return_value="gho_alice"),
            ),
            patch(
                "github.webhook.webhook_processors.workflow_run.dispatch_workflow_webhook_processor.PersonalTokenAuthenticator"
            ) as mock_authenticator_cls,
        ):
            mock_ocean.port_client.find_run_by_external_id = AsyncMock(
                return_value=port_run
            )
            mock_authenticator_cls.return_value.get_authenticated_actor = AsyncMock(
                return_value="alice"
            )

            assert not await processor._should_process_event(make_event("bob"))
