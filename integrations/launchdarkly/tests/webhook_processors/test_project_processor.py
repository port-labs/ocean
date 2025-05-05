from typing import Any, Dict
import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from client import ObjectKind
from webhook_processors.project_webhook_processor import (
    ProjectWebhookProcessor,
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
def project_processor(
    mock_webhook_event: WebhookEvent,
) -> ProjectWebhookProcessor:
    return ProjectWebhookProcessor(mock_webhook_event)


@pytest.fixture
def valid_project_payload() -> Dict[str, Any]:
    return {
        "kind": ObjectKind.PROJECT,
        "_links": {"canonical": {"href": "/api/v2/projects/project-1"}},
        "titleVerb": "created",
        "name": "Test Project",
        "key": "project-1",
        "includeInSnippetByDefault": True,
        "defaultClientSideAvailability": {
            "usingEnvironmentId": True,
            "usingMobileKey": True,
        },
        "tags": ["test", "project"],
    }


@pytest.fixture
def invalid_project_payload() -> Dict[str, Any]:
    return {
        "kind": ObjectKind.FEATURE_FLAG,
        "_links": {"canonical": {"href": "/api/v2/projects/project-1"}},
        "titleVerb": "created",
        "name": "Test Project",
    }


@pytest.fixture
def mock_project_resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.PROJECT,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".key",
                    title=".name",
                    blueprint='"launchDarklyProject"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def mock_client() -> Generator[AsyncMock, None, None]:
    with patch(
        "webhook_processors.project_webhook_processor.LaunchDarklyClient"
    ) as mock:
        client = AsyncMock()
        mock.create_from_ocean_configuration.return_value = client
        yield client


@pytest.mark.asyncio
class TestProjectWebhookProcessor:

    async def test_should_process_event(
        self,
        valid_project_payload: Dict[str, Any],
        project_processor: ProjectWebhookProcessor,
        mock_client: AsyncMock,
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id", headers={}, payload=valid_project_payload
        )
        assert await project_processor._should_process_event(event)

    async def test_get_matching_kinds(
        self, project_processor: ProjectWebhookProcessor
    ) -> None:
        kinds = await project_processor.get_matching_kinds(project_processor.event)
        assert ObjectKind.PROJECT in kinds

    @pytest.mark.parametrize(
        "is_deletion,expected_updated_count,expected_deleted_count",
        [
            # Project Deletion
            (True, 0, 1),
            # Project Update
            (False, 1, 0),
        ],
    )
    async def test_handle_event(
        self,
        project_processor: ProjectWebhookProcessor,
        mock_client: AsyncMock,
        valid_project_payload: Dict[str, Any],
        is_deletion: bool,
        expected_updated_count: int,
        expected_deleted_count: int,
        mock_project_resource_config: ResourceConfig,
    ) -> None:
        # Setup
        if is_deletion:
            valid_project_payload["titleVerb"] = "deleted"
            valid_project_payload["_links"]["self"] = {
                "href": "/api/v2/projects/project-1"
            }

        if not is_deletion:
            mock_client.send_api_request.return_value = {
                "key": "project-1",
                "name": "Test Project",
                "includeInSnippetByDefault": True,
                "defaultClientSideAvailability": {
                    "usingEnvironmentId": True,
                    "usingMobileKey": True,
                },
                "tags": ["test", "project"],
            }

        # Execute
        result = await project_processor.handle_event(
            valid_project_payload, mock_project_resource_config
        )

        # Assert
        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == expected_updated_count
        assert len(result.deleted_raw_results) == expected_deleted_count

        if expected_updated_count > 0:
            assert result.updated_raw_results[0]["key"] == "project-1"
            assert result.updated_raw_results[0]["name"] == "Test Project"

        if expected_deleted_count > 0:
            assert result.deleted_raw_results[0]["key"] == "project-1"
