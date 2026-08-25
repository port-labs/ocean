from typing import Any, Dict, Generator
import pytest
from unittest.mock import AsyncMock, patch

from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from webhook_processors.document_webhook_processor import DocumentWebhookProcessor
from linear.utils import ObjectKind


@pytest.fixture
def document_processor(mock_webhook_event: WebhookEvent) -> DocumentWebhookProcessor:
    return DocumentWebhookProcessor(event=mock_webhook_event)


@pytest.fixture
def valid_document_payload() -> Dict[str, Any]:
    return {
        "action": "create",
        "type": "Document",
        "data": {
            "id": "50e3e770-03ef-4c12-9f5a-e3122a768bc4",
            "title": "payment-service-prd",
            "slugId": "66165efe01cd",
        },
    }


@pytest.fixture
def invalid_document_payload() -> Dict[str, Any]:
    return {
        "type": "Document",
        "data": {"title": "payment-service-prd"},  # Missing id
    }


@pytest.fixture
def non_document_payload() -> Dict[str, Any]:
    return {
        "action": "create",
        "type": "Issue",
        "data": {"identifier": "ABC-123", "title": "Test Issue"},
    }


@pytest.fixture
def mock_resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.DOCUMENT,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".title",
                    blueprint='"linearDocument"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def mock_client() -> Generator[AsyncMock, None, None]:
    with patch("webhook_processors.document_webhook_processor.LinearClient") as mock:
        client = AsyncMock()
        mock.create_from_ocean_configuration.return_value = client
        yield client


@pytest.mark.asyncio
class TestDocumentWebhookProcessor:
    async def test_should_process_event_valid_event(
        self,
        document_processor: DocumentWebhookProcessor,
        valid_document_payload: dict[str, Any],
    ) -> None:
        event = WebhookEvent(
            trace_id="test",
            payload=valid_document_payload,
            headers={"linear-event": "Document"},
        )
        should_process = await document_processor.should_process_event(event)
        assert should_process is True

    async def test_should_process_event_invalid_event(
        self,
        document_processor: DocumentWebhookProcessor,
        valid_document_payload: dict[str, Any],
    ) -> None:
        event = WebhookEvent(
            trace_id="test", payload=valid_document_payload, headers={}
        )
        should_process = await document_processor.should_process_event(event)
        assert should_process is False

    async def test_should_process_event_non_document_payload(
        self,
        document_processor: DocumentWebhookProcessor,
        non_document_payload: dict[str, Any],
    ) -> None:
        should_process = await document_processor.validate_payload(non_document_payload)
        assert should_process is False

    async def test_validate_payload_missing_id(
        self,
        document_processor: DocumentWebhookProcessor,
        invalid_document_payload: dict[str, Any],
    ) -> None:
        should_process = await document_processor.validate_payload(
            invalid_document_payload
        )
        assert should_process is False

    async def test_get_matching_kinds(
        self,
        document_processor: DocumentWebhookProcessor,
        valid_document_payload: dict[str, Any],
    ) -> None:
        event = WebhookEvent(
            trace_id="test", payload=valid_document_payload, headers={}
        )
        kinds = await document_processor.get_matching_kinds(event)
        assert kinds == [ObjectKind.DOCUMENT]

    @pytest.mark.parametrize(
        "action, expected_results",
        [
            ("create", {"updated_count": 1, "deleted_count": 0, "client_called": True}),
            (
                "remove",
                {"updated_count": 0, "deleted_count": 1, "client_called": False},
            ),
        ],
        ids=["add_action", "remove_action"],
    )
    async def test_handle_event_success(
        self,
        mock_client: AsyncMock,
        document_processor: DocumentWebhookProcessor,
        valid_document_payload: Dict[str, Any],
        mock_resource_config: ResourceConfig,
        action: str,
        expected_results: Dict[str, Any],
    ) -> None:
        mock_document_data = {
            "id": "50e3e770-03ef-4c12-9f5a-e3122a768bc4",
            "title": "payment-service-prd",
            "content": "Here goes the actual content",
        }
        mock_client.get_single_document.return_value = mock_document_data

        valid_document_payload["action"] = action

        result = await document_processor.handle_event(
            valid_document_payload, mock_resource_config
        )

        assert len(result.updated_raw_results) == expected_results["updated_count"]
        assert len(result.deleted_raw_results) == expected_results["deleted_count"]

        if expected_results["client_called"]:
            mock_client.get_single_document.assert_called_once_with(
                "50e3e770-03ef-4c12-9f5a-e3122a768bc4"
            )
            assert result.updated_raw_results[0] == mock_document_data
        else:
            mock_client.get_single_document.assert_not_called()
