"""Tests for DeploymentWebhookProcessor."""

import pytest
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)

from vercel.helpers.utils import ObjectKind
from vercel.webhook.webhook_processors.deployment_webhook_processor import (
    DeploymentWebhookProcessor,
)


@pytest.fixture
def resource_config() -> ResourceConfig:
    """Create a resource config for testing."""
    return ResourceConfig(
        kind=ObjectKind.DEPLOYMENT,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".uid",
                    title=".name",
                    blueprint='"vercelDeployment"',
                    properties={},
                    relations={},
                )
            )
        ),
    )


@pytest.fixture
def deployment_processor(mock_webhook_event: WebhookEvent) -> DeploymentWebhookProcessor:
    """Create a DeploymentWebhookProcessor instance."""
    return DeploymentWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestDeploymentWebhookProcessor:
    """Test cases for DeploymentWebhookProcessor."""

    async def test_validate_payload_with_deployment(
        self, deployment_processor: DeploymentWebhookProcessor
    ) -> None:
        """Test payload validation with deployment data."""
        payload = {"deployment": {"uid": "dep_123"}}
        assert await deployment_processor.validate_payload(payload) is True

    async def test_validate_payload_with_uid(
        self, deployment_processor: DeploymentWebhookProcessor
    ) -> None:
        """Test payload validation with uid field."""
        payload = {"uid": "dep_123"}
        assert await deployment_processor.validate_payload(payload) is True

    async def test_validate_payload_missing_data(
        self, deployment_processor: DeploymentWebhookProcessor
    ) -> None:
        """Test payload validation without deployment data."""
        payload = {"other": "data"}
        assert await deployment_processor.validate_payload(payload) is False

    async def test_should_process_event_deployment_created(
        self, deployment_processor: DeploymentWebhookProcessor
    ) -> None:
        """Test should_process_event with deployment.created event."""
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"type": "deployment.created"},
            headers={},
        )
        assert await deployment_processor._should_process_event(event) is True

    async def test_should_process_event_deployment_deleted(
        self, deployment_processor: DeploymentWebhookProcessor
    ) -> None:
        """Test should_process_event with deployment.deleted event."""
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"type": "deployment.deleted"},
            headers={},
        )
        assert await deployment_processor._should_process_event(event) is True

    async def test_should_process_event_other_type(
        self, deployment_processor: DeploymentWebhookProcessor
    ) -> None:
        """Test should_process_event with non-deployment event."""
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"type": "project.created"},
            headers={},
        )
        assert await deployment_processor._should_process_event(event) is False

    async def test_get_matching_kinds(
        self, deployment_processor: DeploymentWebhookProcessor
    ) -> None:
        """Test get_matching_kinds returns deployment."""
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={},
            headers={},
        )
        kinds = await deployment_processor.get_matching_kinds(event)
        assert kinds == [ObjectKind.DEPLOYMENT]

    async def test_handle_event_upsert(
        self,
        deployment_processor: DeploymentWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        """Test handling deployment creation event."""
        payload = {
            "type": "deployment.created",
            "payload": {
                "deployment": {
                    "uid": "dep_123",
                    "url": "example.vercel.app",
                    "state": "READY",
                },
                "project": {"name": "my-project"},
            },
        }

        result = await deployment_processor.handle_event(payload, resource_config)

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0]["uid"] == "dep_123"
        assert result.updated_raw_results[0]["name"] == "my-project"
        assert len(result.deleted_raw_results) == 0

    async def test_handle_event_deletion(
        self,
        deployment_processor: DeploymentWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        """Test handling deployment deletion event."""
        payload = {
            "type": "deployment.deleted",
            "payload": {
                "deployment": {
                    "uid": "dep_123",
                },
            },
        }

        result = await deployment_processor.handle_event(payload, resource_config)

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0]["uid"] == "dep_123"

    async def test_handle_event_deletion_without_identifier(
        self,
        deployment_processor: DeploymentWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        """Test handling deletion event without identifier."""
        payload = {
            "type": "deployment.deleted",
            "payload": {
                "deployment": {},
            },
        }

        result = await deployment_processor.handle_event(payload, resource_config)

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0
