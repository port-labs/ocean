from typing import Any, Dict
import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from client import ObjectKind
from webhook_processors.environment_webhook_processor import (
    EnvironmentWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from typing import Generator


@pytest.fixture
def environment_processor(
    mock_webhook_event: WebhookEvent,
) -> EnvironmentWebhookProcessor:
    return EnvironmentWebhookProcessor(mock_webhook_event)


@pytest.fixture
def valid_environment_payload() -> Dict[str, Any]:
    return {
        "kind": ObjectKind.ENVIRONMENT,
        "_links": {
            "canonical": {"href": "/api/v2/projects/project-1/environments/env-1"}
        },
        "titleVerb": "created",
        "name": "Test Environment",
        "key": "env-1",
        "color": "#000000",
        "defaultTtl": 30,
        "secureMode": False,
        "defaultTrackEvents": True,
        "requireComments": False,
        "confirmChanges": False,
        "tags": ["test", "environment"],
    }


@pytest.fixture
def mock_environment_resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.ENVIRONMENT,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier='.key + "-" + .__projectKey',
                    title=".name",
                    blueprint='"launchDarklyEnvironment"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def mock_client() -> Generator[AsyncMock, None, None]:
    with patch(
        "webhook_processors.environment_webhook_processor.LaunchDarklyClient"
    ) as mock:
        client = AsyncMock()
        mock.create_from_ocean_configuration.return_value = client
        yield client


@pytest.mark.asyncio
class TestEnvironmentWebhookProcessor:

    async def test_should_process_event(
        self,
        valid_environment_payload: Dict[str, Any],
        environment_processor: EnvironmentWebhookProcessor,
        mock_client: AsyncMock,
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id", headers={}, payload=valid_environment_payload
        )
        assert await environment_processor._should_process_event(event)

    async def test_get_matching_kinds(
        self, environment_processor: EnvironmentWebhookProcessor
    ) -> None:
        kinds = await environment_processor.get_matching_kinds(
            environment_processor.event
        )
        assert ObjectKind.ENVIRONMENT in kinds

    @pytest.mark.parametrize(
        "is_deletion,expected_updated_count,expected_deleted_count",
        [
            # Environment Deletion
            (True, 0, 1),
            # Environment Update
            (False, 1, 0),
        ],
    )
    async def test_handle_event(
        self,
        environment_processor: EnvironmentWebhookProcessor,
        mock_client: AsyncMock,
        valid_environment_payload: Dict[str, Any],
        is_deletion: bool,
        expected_updated_count: int,
        expected_deleted_count: int,
        mock_environment_resource_config: ResourceConfig,
    ) -> None:
        # Setup
        if is_deletion:
            valid_environment_payload["titleVerb"] = "deleted"
            valid_environment_payload["_links"]["self"] = {
                "href": "/api/v2/projects/project-1/environments/env-1"
            }

        if not is_deletion:
            mock_client.send_api_request.return_value = {
                "key": "env-1",
                "name": "Test Environment",
                "color": "#000000",
                "defaultTtl": 30,
                "secureMode": False,
                "defaultTrackEvents": True,
                "requireComments": False,
                "confirmChanges": False,
                "tags": ["test", "environment"],
            }

        # Execute
        result = await environment_processor.handle_event(
            valid_environment_payload, mock_environment_resource_config
        )

        # Assert
        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == expected_updated_count
        assert len(result.deleted_raw_results) == expected_deleted_count

        if expected_updated_count > 0:
            assert result.updated_raw_results[0]["key"] == "env-1"
            assert result.updated_raw_results[0]["name"] == "Test Environment"
            assert result.updated_raw_results[0]["__projectKey"] == "project-1"

        if expected_deleted_count > 0:
            assert result.deleted_raw_results[0]["key"] == "env-1"
            assert result.deleted_raw_results[0]["__projectKey"] == "project-1"
