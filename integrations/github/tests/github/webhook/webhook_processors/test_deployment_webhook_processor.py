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
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from github.helpers.utils import ObjectKind

from integration import GithubDeploymentConfig, GithubDeploymentSelector


@pytest.fixture
def resource_config() -> GithubDeploymentConfig:
    return GithubDeploymentConfig(
        kind="deployment",
        selector=GithubDeploymentSelector(query="true"),
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
            "organization": {"login": "test-org"},
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
            SingleDeploymentOptions(
                organization="test-org", repo_name="test-repo", id="123"
            )
        )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == expected_data


class TestDeploymentFiltering:
    """Tests for deployment filtering functionality."""

    def test_task_filter_matches(
        self, deployment_webhook_processor: DeploymentWebhookProcessor
    ) -> None:
        """Test task filter accepts deployments with matching task."""
        selector = GithubDeploymentSelector(query="true", task="deploy")

        # Deployment has task "deploy" which matches the filter
        deployment = {"task": "deploy", "environment": "production"}

        assert (
            deployment_webhook_processor._check_deployment_filters(selector, deployment)
            is True
        )

    def test_task_filter_no_match(
        self, deployment_webhook_processor: DeploymentWebhookProcessor
    ) -> None:
        """Test task filter rejects deployments without matching task."""
        selector = GithubDeploymentSelector(query="true", task="deploy:migrations")

        # Deployment has task "deploy" which doesn't match "deploy:migrations"
        deployment = {"task": "deploy", "environment": "production"}

        assert (
            deployment_webhook_processor._check_deployment_filters(selector, deployment)
            is False
        )

    def test_environment_filter_matches(
        self, deployment_webhook_processor: DeploymentWebhookProcessor
    ) -> None:
        """Test environment filter accepts deployments with matching environment."""
        selector = GithubDeploymentSelector(query="true", environment="production")

        deployment = {"task": "deploy", "environment": "production"}

        assert (
            deployment_webhook_processor._check_deployment_filters(selector, deployment)
            is True
        )

    def test_environment_filter_no_match(
        self, deployment_webhook_processor: DeploymentWebhookProcessor
    ) -> None:
        """Test environment filter rejects deployments without matching environment."""
        selector = GithubDeploymentSelector(query="true", environment="staging")

        # Deployment has environment "production" which doesn't match "staging"
        deployment = {"task": "deploy", "environment": "production"}

        assert (
            deployment_webhook_processor._check_deployment_filters(selector, deployment)
            is False
        )

    def test_multiple_filters_all_match(
        self, deployment_webhook_processor: DeploymentWebhookProcessor
    ) -> None:
        """Test that deployment must match ALL filters (task AND environment)."""
        selector = GithubDeploymentSelector(
            query="true", task="deploy", environment="production"
        )

        # Deployment matches both task and environment
        deployment = {"task": "deploy", "environment": "production"}

        assert (
            deployment_webhook_processor._check_deployment_filters(selector, deployment)
            is True
        )

    def test_multiple_filters_partial_match(
        self, deployment_webhook_processor: DeploymentWebhookProcessor
    ) -> None:
        """Test that deployment is rejected if it doesn't match ALL filters."""
        selector = GithubDeploymentSelector(
            query="true", task="deploy", environment="staging"
        )

        # Deployment matches task but not environment
        deployment = {"task": "deploy", "environment": "production"}

        assert (
            deployment_webhook_processor._check_deployment_filters(selector, deployment)
            is False
        )

    def test_filters_no_filters_specified(
        self, deployment_webhook_processor: DeploymentWebhookProcessor
    ) -> None:
        """Test filters accept deployments when no task/environment filters are specified."""
        selector = GithubDeploymentSelector(query="true")  # No filters

        deployment = {"task": "deploy:migrations", "environment": "staging"}

        assert (
            deployment_webhook_processor._check_deployment_filters(selector, deployment)
            is True
        )
