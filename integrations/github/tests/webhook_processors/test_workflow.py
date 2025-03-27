import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)
from webhook_processors.workflow import WorkflowWebhookProcessor
from client import GitHubClient

from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from helpers.utils import ObjectKind


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.WORKFLOW,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".repository.full_name",
                    title=".name",
                    blueprint='"githubWorkflow"',
                    properties={},
                )
            )
        ),
    )


@pytest.mark.asyncio
class TestWorkflowWebhookProcessor:
    @pytest.fixture
    def workflow_webhook_processor(
        self, mock_webhook_event: WebhookEvent
    ) -> WorkflowWebhookProcessor:
        return WorkflowWebhookProcessor(event=mock_webhook_event)

    @pytest.mark.parametrize("action", ["requested", "completed", "in_progress"])
    async def test_should_process_valid_events(
        self, workflow_webhook_processor: WorkflowWebhookProcessor, action: str
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"action": action, "workflow_run": {}, "workflow": {}},
            headers={"X-GitHub-Event": "workflow_run"},
        )
        result = await workflow_webhook_processor.should_process_event(event)
        assert result is True

    async def test_should_not_process_invalid_event_type(
        self, workflow_webhook_processor: WorkflowWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"action": "completed", "workflow_run": {}},
            headers={"X-GitHub-Event": "push"},
        )
        result = await workflow_webhook_processor.should_process_event(event)
        assert result is False

    async def test_handle_workflow_event_success(
        self,
        workflow_webhook_processor: WorkflowWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        # Arrange
        workflow_data = {
            "id": 1,
            "name": "CI",
            "path": ".github/workflows/ci.yml",
            "state": "active",
        }
        run_data = {
            "id": 123,
            "status": "completed",
            "conclusion": "success",
            "created_at": "2024-03-19T10:00:00Z",
        }

        mock_client = AsyncMock(spec=GitHubClient)
        mock_client.get_single_resource.return_value = workflow_data

        # Act
        with patch(
            "webhook_processors.workflow.GitHubClient.from_ocean_config",
            return_value=mock_client,
        ):
            result = await workflow_webhook_processor.handle_event(
                {
                    "action": "completed",
                    "workflow": {"id": 1},
                    "workflow_run": run_data,
                    "repository": {"name": "test-repo"},
                },
                resource_config,
            )

        # Assert
        expected_data = {**workflow_data, "latest_run": run_data}
        assert result.updated_raw_results == [expected_data]
        assert result.deleted_raw_results == []
        mock_client.get_single_resource.assert_called_once_with(
            "workflow", "test-repo/1"
        )

    async def test_handle_workflow_event_api_error(
        self,
        workflow_webhook_processor: WorkflowWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        # Arrange
        mock_client = AsyncMock(spec=GitHubClient)
        mock_client.get_single_resource.side_effect = Exception("API Error")

        # Act & Assert
        with patch(
            "webhook_processors.workflow.GitHubClient.from_ocean_config",
            return_value=mock_client,
        ):
            with pytest.raises(Exception, match="API Error"):
                await workflow_webhook_processor.handle_event(
                    {
                        "action": "completed",
                        "workflow": {"id": 1},
                        "workflow_run": {},
                        "repository": {"name": "test-repo"},
                    },
                    resource_config,
                )

    async def test_handle_workflow_event_missing_data(
        self,
        workflow_webhook_processor: WorkflowWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:

        with pytest.raises(KeyError):
            await workflow_webhook_processor.handle_event(
                {"action": "completed"}, resource_config
            )

    async def test_handle_workflow_event_data_enrichment(
        self,
        workflow_webhook_processor: WorkflowWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        # Arrange
        workflow_data = {"id": 1, "name": "CI", "path": ".github/workflows/ci.yml"}
        run_data = {
            "id": 123,
            "status": "completed",
            "conclusion": "success",
            "head_sha": "abc123",
        }

        mock_client = AsyncMock(spec=GitHubClient)
        mock_client.get_single_resource.return_value = workflow_data

        # Act
        with patch(
            "webhook_processors.workflow.GitHubClient.from_ocean_config",
            return_value=mock_client,
        ):
            result = await workflow_webhook_processor.handle_event(
                {
                    "action": "completed",
                    "workflow": {"id": 1},
                    "workflow_run": run_data,
                    "repository": {"name": "test-repo"},
                },
                resource_config,
            )

        # Assert
        assert "latest_run" in result.updated_raw_results[0]
        assert result.updated_raw_results[0]["latest_run"]["head_sha"] == "abc123"
