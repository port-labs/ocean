import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from github.webhook.webhook_processors.deployment_status_webhook_processor import (
    DeploymentStatusWebhookProcessor,
)
from github.core.options import SingleDeploymentStatusOptions
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from github.helpers.utils import ObjectKind

from integration import GithubDeploymentStatusConfig, GithubDeploymentStatusSelector


@pytest.fixture
def resource_config() -> GithubDeploymentStatusConfig:
    return GithubDeploymentStatusConfig(
        kind=ObjectKind.DEPLOYMENT_STATUS,
        selector=GithubDeploymentStatusSelector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".state",
                    blueprint='"deploymentStatus"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def deployment_status_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> DeploymentStatusWebhookProcessor:
    return DeploymentStatusWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestDeploymentStatusWebhookProcessor:
    async def test_get_matching_kinds(
        self, deployment_status_webhook_processor: DeploymentStatusWebhookProcessor
    ) -> None:
        kinds = await deployment_status_webhook_processor.get_matching_kinds(
            deployment_status_webhook_processor.event
        )
        assert kinds == [ObjectKind.DEPLOYMENT_STATUS]

    async def test_should_process_event_correct_header(
        self, deployment_status_webhook_processor: DeploymentStatusWebhookProcessor
    ) -> None:
        """Test that processor accepts deployment_status events."""
        event = WebhookEvent(
            trace_id="test",
            payload={},
            headers={"x-github-event": "deployment_status"},
        )
        result = await deployment_status_webhook_processor._should_process_event(event)
        assert result is True

    async def test_should_process_event_wrong_header(
        self, deployment_status_webhook_processor: DeploymentStatusWebhookProcessor
    ) -> None:
        """Test that processor rejects non-deployment_status events."""
        event = WebhookEvent(
            trace_id="test",
            payload={},
            headers={"x-github-event": "deployment"},
        )
        result = await deployment_status_webhook_processor._should_process_event(event)
        assert result is False

    async def test_validate_payload_valid(
        self, deployment_status_webhook_processor: DeploymentStatusWebhookProcessor
    ) -> None:
        """Test payload validation with valid payload."""
        payload = {
            "deployment_status": {"id": 456},
            "deployment": {"id": 123},
        }
        result = await deployment_status_webhook_processor._validate_payload(payload)
        assert result is True

    async def test_validate_payload_missing_deployment_status(
        self, deployment_status_webhook_processor: DeploymentStatusWebhookProcessor
    ) -> None:
        """Test payload validation with missing deployment_status."""
        payload = {
            "deployment": {"id": 123},
        }
        result = await deployment_status_webhook_processor._validate_payload(payload)
        assert result is False

    async def test_validate_payload_missing_deployment(
        self, deployment_status_webhook_processor: DeploymentStatusWebhookProcessor
    ) -> None:
        """Test payload validation with missing deployment."""
        payload = {
            "deployment_status": {"id": 456},
        }
        result = await deployment_status_webhook_processor._validate_payload(payload)
        assert result is False

    async def test_validate_payload_missing_ids(
        self, deployment_status_webhook_processor: DeploymentStatusWebhookProcessor
    ) -> None:
        """Test payload validation with missing ids."""
        payload: EventPayload = {
            "deployment_status": {},
            "deployment": {},
        }
        result = await deployment_status_webhook_processor._validate_payload(payload)
        assert result is False

    async def test_handle_event(
        self,
        deployment_status_webhook_processor: DeploymentStatusWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        payload = {
            "action": "created",
            "deployment": {
                "id": 123,
                "environment": "production",
                "task": "deploy",
                "ref": "main",
                "sha": "abc123",
            },
            "deployment_status": {
                "id": 456,
                "state": "success",
                "description": "Deployment finished",
            },
            "repository": {"name": "test-repo"},
            "organization": {"login": "test-org"},
        }

        expected_data = {
            "id": 456,
            "state": "success",
            "description": "Deployment finished",
            "__repository": "test-repo",
            "__organization": "test-org",
            "__deployment_id": "123",
        }

        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = expected_data

        with patch(
            "github.webhook.webhook_processors.deployment_status_webhook_processor.RestDeploymentStatusExporter",
            return_value=mock_exporter,
        ):
            result = await deployment_status_webhook_processor.handle_event(
                payload, resource_config
            )

        mock_exporter.get_resource.assert_called_once_with(
            SingleDeploymentStatusOptions(
                organization="test-org",
                repo_name="test-repo",
                deployment_id="123",
                status_id="456",
            )
        )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == expected_data

    async def test_handle_event_filtered_by_task(
        self,
        deployment_status_webhook_processor: DeploymentStatusWebhookProcessor,
    ) -> None:
        """Test that events are filtered when task doesn't match."""
        resource_config = GithubDeploymentStatusConfig(
            kind=ObjectKind.DEPLOYMENT_STATUS,
            selector=GithubDeploymentStatusSelector(
                query="true", task="deploy:migrations"
            ),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".state",
                        blueprint='"deploymentStatus"',
                        properties={},
                    )
                )
            ),
        )

        payload = {
            "action": "created",
            "deployment": {
                "id": 123,
                "environment": "production",
                "task": "deploy",  # Doesn't match "deploy:migrations"
            },
            "deployment_status": {"id": 456, "state": "success"},
            "repository": {"name": "test-repo"},
            "organization": {"login": "test-org"},
        }

        result = await deployment_status_webhook_processor.handle_event(
            payload, resource_config
        )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0

    async def test_handle_event_filtered_by_environment(
        self,
        deployment_status_webhook_processor: DeploymentStatusWebhookProcessor,
    ) -> None:
        """Test that events are filtered when environment doesn't match."""
        resource_config = GithubDeploymentStatusConfig(
            kind=ObjectKind.DEPLOYMENT_STATUS,
            selector=GithubDeploymentStatusSelector(
                query="true", environment="staging"
            ),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".state",
                        blueprint='"deploymentStatus"',
                        properties={},
                    )
                )
            ),
        )

        payload = {
            "action": "created",
            "deployment": {
                "id": 123,
                "environment": "production",  # Doesn't match "staging"
                "task": "deploy",
            },
            "deployment_status": {"id": 456, "state": "success"},
            "repository": {"name": "test-repo"},
            "organization": {"login": "test-org"},
        }

        result = await deployment_status_webhook_processor.handle_event(
            payload, resource_config
        )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0


class TestDeploymentStatusFiltering:
    """Tests for deployment status filtering functionality."""

    def test_task_filter_matches(
        self, deployment_status_webhook_processor: DeploymentStatusWebhookProcessor
    ) -> None:
        """Test task filter accepts deployments with matching task."""
        selector = GithubDeploymentStatusSelector(query="true", task="deploy")
        deployment = {"task": "deploy", "environment": "production"}

        assert (
            deployment_status_webhook_processor._check_deployment_filters(
                selector, deployment
            )
            is True
        )

    def test_task_filter_no_match(
        self, deployment_status_webhook_processor: DeploymentStatusWebhookProcessor
    ) -> None:
        """Test task filter rejects deployments without matching task."""
        selector = GithubDeploymentStatusSelector(
            query="true", task="deploy:migrations"
        )
        deployment = {"task": "deploy", "environment": "production"}

        assert (
            deployment_status_webhook_processor._check_deployment_filters(
                selector, deployment
            )
            is False
        )

    def test_environment_filter_matches(
        self, deployment_status_webhook_processor: DeploymentStatusWebhookProcessor
    ) -> None:
        """Test environment filter accepts deployments with matching environment."""
        selector = GithubDeploymentStatusSelector(
            query="true", environment="production"
        )
        deployment = {"task": "deploy", "environment": "production"}

        assert (
            deployment_status_webhook_processor._check_deployment_filters(
                selector, deployment
            )
            is True
        )

    def test_environment_filter_no_match(
        self, deployment_status_webhook_processor: DeploymentStatusWebhookProcessor
    ) -> None:
        """Test environment filter rejects deployments without matching environment."""
        selector = GithubDeploymentStatusSelector(query="true", environment="staging")
        deployment = {"task": "deploy", "environment": "production"}

        assert (
            deployment_status_webhook_processor._check_deployment_filters(
                selector, deployment
            )
            is False
        )

    def test_multiple_filters_all_match(
        self, deployment_status_webhook_processor: DeploymentStatusWebhookProcessor
    ) -> None:
        """Test that deployment must match ALL filters (task AND environment)."""
        selector = GithubDeploymentStatusSelector(
            query="true", task="deploy", environment="production"
        )
        deployment = {"task": "deploy", "environment": "production"}

        assert (
            deployment_status_webhook_processor._check_deployment_filters(
                selector, deployment
            )
            is True
        )

    def test_multiple_filters_partial_match(
        self, deployment_status_webhook_processor: DeploymentStatusWebhookProcessor
    ) -> None:
        """Test that deployment is rejected if it doesn't match ALL filters."""
        selector = GithubDeploymentStatusSelector(
            query="true", task="deploy", environment="staging"
        )
        deployment = {"task": "deploy", "environment": "production"}

        assert (
            deployment_status_webhook_processor._check_deployment_filters(
                selector, deployment
            )
            is False
        )

    def test_no_filters_specified(
        self, deployment_status_webhook_processor: DeploymentStatusWebhookProcessor
    ) -> None:
        """Test filters accept deployments when no task/environment filters are specified."""
        selector = GithubDeploymentStatusSelector(query="true")
        deployment = {"task": "deploy:migrations", "environment": "staging"}

        assert (
            deployment_status_webhook_processor._check_deployment_filters(
                selector, deployment
            )
            is True
        )
