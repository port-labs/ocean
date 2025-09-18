from typing import Dict
import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from checkmarx_one.webhook.webhook_processors.project_webhook_processor import (
    ProjectWebhookProcessor,
)
from checkmarx_one.utils import ObjectKind
from checkmarx_one.webhook.events import CheckmarxEventType

from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)


@pytest.fixture
def project_resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind="project",
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".name",
                    blueprint='"checkmarxProject"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def project_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> ProjectWebhookProcessor:
    return ProjectWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestProjectWebhookProcessor:

    @pytest.mark.parametrize(
        "checkmarx_event,result",
        [
            (CheckmarxEventType.PROJECT_CREATED, True),
            ("invalid_event", False),
            (CheckmarxEventType.SCAN_COMPLETED, False),
            (CheckmarxEventType.SCAN_FAILED, False),
            (CheckmarxEventType.SCAN_PARTIAL, False),
        ],
    )
    async def test_should_process_event(
        self,
        project_webhook_processor: ProjectWebhookProcessor,
        checkmarx_event: str,
        result: bool,
    ) -> None:
        mock_request = AsyncMock()
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={},
            headers={"x-cx-webhook-event": checkmarx_event},
        )
        event._original_request = mock_request

        assert await project_webhook_processor._should_process_event(event) is result

    async def test_get_matching_kinds(
        self, project_webhook_processor: ProjectWebhookProcessor
    ) -> None:
        kinds = await project_webhook_processor.get_matching_kinds(
            project_webhook_processor.event
        )
        assert ObjectKind.PROJECT in kinds

    @pytest.mark.parametrize(
        "payload,expected",
        [
            (
                {
                    "ID": "project-123",
                },
                True,
            ),
            (
                {
                    "ID": "project-789",
                    "additionalField": "value",
                },
                True,
            ),
            (
                {
                    "projectId": "project-456",
                },  # wrong field name
                False,
            ),
            (
                {},  # empty payload
                False,
            ),
        ],
    )
    async def test_validate_payload(
        self,
        project_webhook_processor: ProjectWebhookProcessor,
        payload: Dict[str, str],
        expected: bool,
    ) -> None:
        result = await project_webhook_processor.validate_payload(payload)
        assert result is expected

    async def test_handle_event_success(
        self,
        project_webhook_processor: ProjectWebhookProcessor,
        project_resource_config: ResourceConfig,
    ) -> None:
        """Test handling a project event successfully."""
        project_data = {
            "id": "project-123",
            "name": "Test Project",
            "description": "A test project",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T01:00:00Z",
            "status": "active",
            "type": "application",
        }

        payload = {
            "ID": "project-123",
        }

        # Mock the project exporter
        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = project_data

        with (
            patch(
                "checkmarx_one.webhook.webhook_processors.project_webhook_processor.create_project_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            result = await project_webhook_processor.handle_event(
                payload, project_resource_config
            )

            # Verify exporter was called with correct parameters
            mock_exporter.get_resource.assert_called_once()
            call_args = mock_exporter.get_resource.call_args[0][0]
            assert call_args["project_id"] == "project-123"

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == project_data

    async def test_handle_event_exporter_error(
        self,
        project_webhook_processor: ProjectWebhookProcessor,
        project_resource_config: ResourceConfig,
    ) -> None:
        """Test handling when the exporter raises an error."""
        payload = {
            "ID": "project-123",
        }

        # Mock the project exporter to raise an exception
        mock_exporter = AsyncMock()
        mock_exporter.get_resource.side_effect = Exception("API Error")

        with (
            patch(
                "checkmarx_one.webhook.webhook_processors.project_webhook_processor.create_project_exporter"
            ) as mock_create_exporter,
        ):
            mock_create_exporter.return_value = mock_exporter

            with pytest.raises(Exception, match="API Error"):
                await project_webhook_processor.handle_event(
                    payload, project_resource_config
                )

    async def test_authenticate_returns_true(
        self, project_webhook_processor: ProjectWebhookProcessor
    ) -> None:
        """Test that authenticate method returns True."""
        payload: EventPayload = {"ID": "project-123"}
        headers: EventHeaders = {
            "x-cx-webhook-event": CheckmarxEventType.PROJECT_CREATED
        }

        result = await project_webhook_processor.authenticate(payload, headers)
        assert result is True

    async def test_should_process_event_with_valid_request(
        self, project_webhook_processor: ProjectWebhookProcessor
    ) -> None:
        """Test should_process_event with valid request and signature."""
        mock_request = AsyncMock()
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"ID": "project-123"},
            headers={"x-cx-webhook-event": CheckmarxEventType.PROJECT_CREATED},
        )
        event._original_request = mock_request

        # Mock _verify_webhook_signature to return True
        with patch.object(
            project_webhook_processor, "_verify_webhook_signature", return_value=True
        ):
            result = await project_webhook_processor.should_process_event(event)
            assert result is True

    async def test_should_process_event_without_request(
        self, project_webhook_processor: ProjectWebhookProcessor
    ) -> None:
        """Test should_process_event without original request."""
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"ID": "project-123"},
            headers={"x-cx-webhook-event": CheckmarxEventType.PROJECT_CREATED},
        )
        event._original_request = None

        result = await project_webhook_processor.should_process_event(event)
        assert result is False
