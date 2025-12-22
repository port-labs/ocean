"""Unit tests for Harbor webhook processors."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from harbor.overrides import ArtifactSelector
from webhook_processors.artifact_webhook_processor import ArtifactWebhookProcessor


@pytest.fixture
def event() -> WebhookEvent:
    """Create a basic webhook event."""
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def artifact_webhook_processor(event: WebhookEvent) -> ArtifactWebhookProcessor:
    """Create an ArtifactWebhookProcessor instance."""
    return ArtifactWebhookProcessor(event)


@pytest.fixture
def resource_config() -> ResourceConfig:
    """Create a basic resource config."""
    return ResourceConfig(
        kind="artifacts",
        selector=ArtifactSelector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".digest",
                    title=".tags[0].name",
                    blueprint='"harborArtifact"',
                    properties={
                        "digest": ".digest",
                        "size": ".size",
                        "push_time": ".push_time",
                    },
                    relations={},
                )
            )
        ),
    )


@pytest.mark.asyncio
async def test_should_process_event_push_artifact(
    artifact_webhook_processor: ArtifactWebhookProcessor,
) -> None:
    """Test should_process_event returns True for PUSH_ARTIFACT."""
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={"type": "PUSH_ARTIFACT"},
        headers={},
    )
    assert await artifact_webhook_processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_should_process_event_delete_artifact(
    artifact_webhook_processor: ArtifactWebhookProcessor,
) -> None:
    """Test should_process_event returns True for DELETE_ARTIFACT."""
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={"type": "DELETE_ARTIFACT"},
        headers={},
    )
    assert await artifact_webhook_processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_should_process_event_pull_artifact(
    artifact_webhook_processor: ArtifactWebhookProcessor,
) -> None:
    """Test should_process_event returns False for PULL_ARTIFACT."""
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={"type": "PULL_ARTIFACT"},
        headers={},
    )
    assert await artifact_webhook_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_should_process_event_unknown_type(
    artifact_webhook_processor: ArtifactWebhookProcessor,
) -> None:
    """Test should_process_event returns False for unknown event types."""
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={"type": "UNKNOWN_EVENT"},
        headers={},
    )
    assert await artifact_webhook_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_get_matching_kinds(
    artifact_webhook_processor: ArtifactWebhookProcessor,
) -> None:
    """Test get_matching_kinds returns correct kind."""
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    kinds = await artifact_webhook_processor.get_matching_kinds(event)
    assert kinds == ["artifacts"]


@pytest.mark.asyncio
async def test_authenticate_with_valid_secret(
    artifact_webhook_processor: ArtifactWebhookProcessor,
) -> None:
    """Test authentication succeeds with valid secret."""
    payload = {}
    headers = {"Authorization": "secret123"}

    with patch("webhook_processors.artifact_webhook_processor.ocean") as mock_ocean:
        # Use MagicMock for sync method
        mock_config = MagicMock()
        mock_config.get = MagicMock(return_value="secret123")
        mock_ocean.integration_config = mock_config
        
        result = await artifact_webhook_processor.authenticate(payload, headers)
        assert result is True


@pytest.mark.asyncio
async def test_authenticate_with_invalid_secret(
    artifact_webhook_processor: ArtifactWebhookProcessor,
) -> None:
    """Test authentication fails with invalid secret."""
    payload = {}
    headers = {"Authorization": "wrong_secret"}

    with patch("webhook_processors.artifact_webhook_processor.ocean") as mock_ocean:
        mock_config = MagicMock()
        mock_config.get = MagicMock(return_value="secret123")
        mock_ocean.integration_config = mock_config
        
        result = await artifact_webhook_processor.authenticate(payload, headers)
        assert result is False


@pytest.mark.asyncio
async def test_authenticate_without_header(
    artifact_webhook_processor: ArtifactWebhookProcessor,
) -> None:
    """Test authentication fails without authorization header."""
    payload = {}
    headers = {}

    with patch("webhook_processors.artifact_webhook_processor.ocean") as mock_ocean:
        mock_config = MagicMock()
        mock_config.get = MagicMock(return_value="secret123")
        mock_ocean.integration_config = mock_config
        
        result = await artifact_webhook_processor.authenticate(payload, headers)
        assert result is False


@pytest.mark.asyncio
async def test_authenticate_no_secret_configured(
    artifact_webhook_processor: ArtifactWebhookProcessor,
) -> None:
    """Test authentication succeeds when no secret is configured."""
    payload = {}
    headers = {}

    with patch("webhook_processors.artifact_webhook_processor.ocean") as mock_ocean:
        mock_config = MagicMock()
        mock_config.get = MagicMock(return_value=None)
        mock_ocean.integration_config = mock_config
        
        result = await artifact_webhook_processor.authenticate(payload, headers)
        assert result is True


@pytest.mark.asyncio
async def test_validate_payload_valid(
    artifact_webhook_processor: ArtifactWebhookProcessor,
) -> None:
    """Test validate_payload returns True for valid payload."""
    payload = {
        "type": "PUSH_ARTIFACT",
        "event_data": {
            "resources": [
                {
                    "digest": "sha256:abc123",
                    "resource_url": "harbor.example.com/library/nginx:latest",
                }
            ],
            "repository": {"name": "library/nginx"},
        },
    }
    result = await artifact_webhook_processor.validate_payload(payload)
    assert result is True


@pytest.mark.asyncio
async def test_validate_payload_missing_type(
    artifact_webhook_processor: ArtifactWebhookProcessor,
) -> None:
    """Test validate_payload returns False when type is missing."""
    payload = {
        "event_data": {
            "resources": [{"digest": "sha256:abc123"}],
            "repository": {"name": "library/nginx"},
        }
    }
    result = await artifact_webhook_processor.validate_payload(payload)
    assert result is False


@pytest.mark.asyncio
async def test_validate_payload_missing_event_data(
    artifact_webhook_processor: ArtifactWebhookProcessor,
) -> None:
    """Test validate_payload returns False when event_data is missing."""
    payload = {"type": "PUSH_ARTIFACT"}
    result = await artifact_webhook_processor.validate_payload(payload)
    assert result is False


@pytest.mark.asyncio
async def test_validate_payload_missing_resources(
    artifact_webhook_processor: ArtifactWebhookProcessor,
) -> None:
    """Test validate_payload returns False when resources is missing."""
    payload = {
        "type": "PUSH_ARTIFACT",
        "event_data": {"repository": {"name": "library/nginx"}},
    }
    result = await artifact_webhook_processor.validate_payload(payload)
    assert result is False


@pytest.mark.asyncio
async def test_validate_payload_empty_resources(
    artifact_webhook_processor: ArtifactWebhookProcessor,
) -> None:
    """Test validate_payload returns False when resources is empty."""
    payload = {
        "type": "PUSH_ARTIFACT",
        "event_data": {"resources": [], "repository": {"name": "library/nginx"}},
    }
    result = await artifact_webhook_processor.validate_payload(payload)
    assert result is False


@pytest.mark.asyncio
async def test_validate_payload_missing_digest(
    artifact_webhook_processor: ArtifactWebhookProcessor,
) -> None:
    """Test validate_payload returns False when digest is missing."""
    payload = {
        "type": "PUSH_ARTIFACT",
        "event_data": {
            "resources": [{"resource_url": "harbor.example.com/library/nginx:latest"}],
            "repository": {"name": "library/nginx"},
        },
    }
    result = await artifact_webhook_processor.validate_payload(payload)
    assert result is False


@pytest.mark.asyncio
async def test_handle_event_delete_artifact(
    artifact_webhook_processor: ArtifactWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    """Test handle_event for DELETE_ARTIFACT returns deleted results."""
    payload = {
        "type": "DELETE_ARTIFACT",
        "event_data": {
            "resources": [
                {
                    "digest": "sha256:abc123",
                    "resource_url": "harbor.example.com/library/nginx:latest",
                }
            ],
            "repository": {"name": "library/nginx"},
        },
    }

    result = await artifact_webhook_processor.handle_event(payload, resource_config)

    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 1
    assert result.deleted_raw_results[0]["digest"] == "sha256:abc123"


@pytest.mark.asyncio
async def test_handle_event_push_artifact_success(
    artifact_webhook_processor: ArtifactWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    """Test handle_event for PUSH_ARTIFACT fetches and returns artifact."""
    payload = {
        "type": "PUSH_ARTIFACT",
        "event_data": {
            "resources": [
                {
                    "digest": "sha256:abc123",
                    "resource_url": "harbor.example.com/library/nginx:latest",
                }
            ],
            "repository": {"name": "library/nginx"},
        },
    }

    mock_artifact: dict[str, Any] = {
        "digest": "sha256:abc123",
        "tags": [{"name": "latest"}],
        "size": 12345,
    }

    with patch(
        "webhook_processors.artifact_webhook_processor.get_harbor_client"
    ) as mock_get_client:
        mock_client = AsyncMock()
        mock_client.get_single_artifact = AsyncMock(return_value=mock_artifact)
        mock_get_client.return_value = mock_client

        result = await artifact_webhook_processor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == mock_artifact

        # Verify client was called with correct parameters
        mock_client.get_single_artifact.assert_called_once_with(
            project_name="library",
            repository_name="nginx",
            reference="sha256:abc123",
        )


@pytest.mark.asyncio
async def test_handle_event_push_artifact_not_found(
    artifact_webhook_processor: ArtifactWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    """Test handle_event for PUSH_ARTIFACT when artifact is not found."""
    payload = {
        "type": "PUSH_ARTIFACT",
        "event_data": {
            "resources": [
                {
                    "digest": "sha256:abc123",
                    "resource_url": "harbor.example.com/library/nginx:latest",
                }
            ],
            "repository": {"name": "library/nginx"},
        },
    }

    with patch(
        "webhook_processors.artifact_webhook_processor.get_harbor_client"
    ) as mock_get_client:
        mock_client = AsyncMock()
        mock_client.get_single_artifact = AsyncMock(return_value=None)
        mock_get_client.return_value = mock_client

        result = await artifact_webhook_processor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_handle_event_push_artifact_api_error(
    artifact_webhook_processor: ArtifactWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    """Test handle_event for PUSH_ARTIFACT when API call fails."""
    payload = {
        "type": "PUSH_ARTIFACT",
        "event_data": {
            "resources": [
                {
                    "digest": "sha256:abc123",
                    "resource_url": "harbor.example.com/library/nginx:latest",
                }
            ],
            "repository": {"name": "library/nginx"},
        },
    }

    with patch(
        "webhook_processors.artifact_webhook_processor.get_harbor_client"
    ) as mock_get_client:
        mock_client = AsyncMock()
        mock_client.get_single_artifact = AsyncMock(
            side_effect=Exception("API Error")
        )
        mock_get_client.return_value = mock_client

        result = await artifact_webhook_processor.handle_event(payload, resource_config)

        # Should return empty results on error, not raise exception
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_handle_event_invalid_resource_url(
    artifact_webhook_processor: ArtifactWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    """Test handle_event with invalid resource URL format."""
    payload = {
        "type": "PUSH_ARTIFACT",
        "event_data": {
            "resources": [
                {
                    "digest": "sha256:abc123",
                    "resource_url": "invalid_url",  # Invalid format
                }
            ],
            "repository": {"name": "library/nginx"},
        },
    }

    result = await artifact_webhook_processor.handle_event(payload, resource_config)

    # Should handle parsing error gracefully
    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_handle_event_with_digest_reference(
    artifact_webhook_processor: ArtifactWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    """Test handle_event with digest reference in resource URL."""
    payload = {
        "type": "PUSH_ARTIFACT",
        "event_data": {
            "resources": [
                {
                    "digest": "sha256:abc123",
                    "resource_url": "harbor.example.com/library/nginx@sha256:abc123",
                }
            ],
            "repository": {"name": "library/nginx"},
        },
    }

    mock_artifact: dict[str, Any] = {
        "digest": "sha256:abc123",
        "size": 12345,
    }

    with patch(
        "webhook_processors.artifact_webhook_processor.get_harbor_client"
    ) as mock_get_client:
        mock_client = AsyncMock()
        mock_client.get_single_artifact = AsyncMock(return_value=mock_artifact)
        mock_get_client.return_value = mock_client

        result = await artifact_webhook_processor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 1
        mock_client.get_single_artifact.assert_called_once_with(
            project_name="library",
            repository_name="nginx",
            reference="sha256:abc123",
        )

