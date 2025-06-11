import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from github.core.options import SingleEnvironmentOptions
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from github.helpers.utils import ObjectKind
from github.webhook.webhook_processors.environment_webhook_processor import (
    EnvironmentWebhookProcessor,
)


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.ENVIRONMENT,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".name",
                    title=".name",
                    blueprint='"githubRepoEnvironment"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def environment_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> EnvironmentWebhookProcessor:
    return EnvironmentWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestEnvironmentWebhookProcessor:

    async def test_get_matching_kinds(
        self, environment_webhook_processor: EnvironmentWebhookProcessor
    ) -> None:
        kinds = await environment_webhook_processor.get_matching_kinds(
            environment_webhook_processor.event
        )
        assert kinds == [ObjectKind.ENVIRONMENT]

    async def test_handle_event(
        self,
        environment_webhook_processor: EnvironmentWebhookProcessor,
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
            "name": "production",
            "url": "https://github.com/org/repo/environments/production",
            "created_at": "2024-03-20T10:00:00Z",
            "updated_at": "2024-03-20T10:00:00Z",
            "protected_branches": True,
            "custom_branch_policies": True,
            "__repository": "test-repo",
        }

        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = expected_data

        with patch(
            "github.webhook.webhook_processors.environment_webhook_processor.RestEnvironmentExporter",
            return_value=mock_exporter,
        ):
            result = await environment_webhook_processor.handle_event(
                payload, resource_config
            )

        # Verify exporter was called with correct options
        mock_exporter.get_resource.assert_called_once_with(
            SingleEnvironmentOptions(repo_name="test-repo", name="production")
        )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == expected_data
