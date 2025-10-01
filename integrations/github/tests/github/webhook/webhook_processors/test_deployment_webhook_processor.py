import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from github.webhook.webhook_processors.deployment_webhook_processor import (
    DeploymentWebhookProcessor,
)
from github.core.options import SingleDeploymentOptions
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from github.helpers.utils import ObjectKind


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.DEPLOYMENT,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".description",
                    blueprint='"deployment"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def deployment_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> DeploymentWebhookProcessor:
    return DeploymentWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestDeploymentWebhookProcessor:

    async def test_get_matching_kinds(
        self, deployment_webhook_processor: DeploymentWebhookProcessor
    ) -> None:
        kinds = await deployment_webhook_processor.get_matching_kinds(
            deployment_webhook_processor.event
        )
        assert kinds == [ObjectKind.DEPLOYMENT]

    async def test_handle_event(
        self,
        deployment_webhook_processor: DeploymentWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:

        payload = {
            "action": "created",
            "deployment": {
                "id": 123,
                "environment": "production",
                "ref": "main",
                "sha": "abc123",
                "description": "Deploy to production",
                "url": "https://github.com/org/repo/deployments/123",
                "created_at": "2024-03-20T10:00:00Z",
                "transient_environment": False,
                "production_environment": True,
            },
            "repository": {"name": "test-repo"},
        }

        expected_data = {
            "id": 123,
            "environment": "production",
            "ref": "main",
            "sha": "abc123",
            "description": "Deploy to production",
            "url": "https://github.com/org/repo/deployments/123",
            "created_at": "2024-03-20T10:00:00Z",
            "transient_environment": False,
            "production_environment": True,
            "__repository": "test-repo",
        }

        # Mock the appropriate exporter based on resource config
        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = expected_data

        with patch(
            "github.webhook.webhook_processors.deployment_webhook_processor.RestDeploymentExporter",
            return_value=mock_exporter,
        ):
            result = await deployment_webhook_processor.handle_event(
                payload, resource_config
            )

        # Verify exporter was called with correct options
        mock_exporter.get_resource.assert_called_once_with(
            SingleDeploymentOptions(repo_name="test-repo", id="123")
        )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == expected_data
