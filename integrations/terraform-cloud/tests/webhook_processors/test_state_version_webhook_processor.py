from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from webhook_processors.state_version_webhook_processor import (
    StateVersionWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from utils import ObjectKind


@pytest.fixture
def processor() -> Any:
    mock_event = MagicMock(spec=WebhookEvent)
    return StateVersionWebhookProcessor(mock_event)


@pytest.fixture
def mock_terraform_client() -> Any:
    return MagicMock()


class TestGetMatchingKinds:
    @pytest.mark.asyncio
    async def test_get_matching_kinds_returns_state_version(
        self, processor: Any
    ) -> None:
        event = MagicMock()

        result = await processor.get_matching_kinds(event)

        assert result == [ObjectKind.STATE_VERSION]
        assert len(result) == 1


class TestShouldProcessEvent:
    @pytest.mark.asyncio
    async def test_should_process_event_applied_status(self, processor: Any) -> None:
        event = MagicMock()
        event.payload = {"notifications": [{"run_status": "applied"}]}

        result = await processor._should_process_event(event)

        assert result is True

    @pytest.mark.asyncio
    async def test_should_process_event_not_applied_status(
        self, processor: Any
    ) -> None:
        event = MagicMock()
        event.payload = {"notifications": [{"run_status": "planning"}]}

        result = await processor._should_process_event(event)

        assert result is False

    @pytest.mark.asyncio
    async def test_should_process_event_multiple_notifications(
        self, processor: Any
    ) -> None:
        event = MagicMock()
        event.payload = {
            "notifications": [
                {"run_status": "planning"},
                {"run_status": "applied"},
            ]
        }

        result = await processor._should_process_event(event)

        assert result is True

    @pytest.mark.asyncio
    async def test_should_process_event_empty_notifications(
        self, processor: Any
    ) -> None:
        event = MagicMock()
        event.payload = {"notifications": []}

        result = await processor._should_process_event(event)

        assert result is False


class TestEnrichStateVersionWithOutput:
    @pytest.mark.asyncio
    async def test_enrich_state_version_with_output_success(
        self, processor: Any, mock_terraform_client: Any
    ) -> None:
        state_version = {"id": "sv-123", "attributes": {"serial": 1}}
        output_data = [{"name": "output1", "value": "value1"}]

        mock_terraform_client.get_state_version_output = AsyncMock(
            return_value=output_data
        )

        result = await processor._enrich_state_version_with_output(
            state_version, mock_terraform_client
        )

        assert result["id"] == "sv-123"
        assert result["__output"] == output_data
        mock_terraform_client.get_state_version_output.assert_called_once_with("sv-123")

    @pytest.mark.asyncio
    async def test_enrich_state_version_with_output_api_failure(
        self, processor: Any, mock_terraform_client: Any
    ) -> None:
        state_version = {"id": "sv-123", "attributes": {"serial": 1}}

        mock_terraform_client.get_state_version_output = AsyncMock(
            side_effect=Exception("API Error")
        )

        result = await processor._enrich_state_version_with_output(
            state_version, mock_terraform_client
        )

        assert result["id"] == "sv-123"
        assert result["__output"] == {}

    @pytest.mark.asyncio
    async def test_enrich_state_version_preserves_original_data(
        self, processor: Any, mock_terraform_client: Any
    ) -> None:
        state_version = {
            "id": "sv-123",
            "attributes": {"serial": 1, "status": "finalized"},
            "relationships": {"workspace": {"data": {"id": "ws-1"}}},
        }
        output_data = [{"name": "output1"}]

        mock_terraform_client.get_state_version_output = AsyncMock(
            return_value=output_data
        )

        result = await processor._enrich_state_version_with_output(
            state_version, mock_terraform_client
        )

        assert result["attributes"]["serial"] == 1
        assert result["attributes"]["status"] == "finalized"
        assert result["relationships"]["workspace"]["data"]["id"] == "ws-1"


class TestHandleEvent:
    @pytest.mark.asyncio
    async def test_handle_event_success(self, processor: Any) -> None:
        payload: dict[str, Any] = {
            "workspace_name": "test-workspace",
            "organization_name": "test-org",
        }
        resource_config = MagicMock()

        mock_client = MagicMock()
        state_versions = [
            {"id": "sv-1", "attributes": {"serial": 1}},
            {"id": "sv-2", "attributes": {"serial": 2}},
        ]

        async def mock_state_versions_generator(
            workspace_name: str, organization_name: str
        ) -> Any:
            yield state_versions

        mock_client.get_state_versions_for_single_workspace = (
            mock_state_versions_generator
        )
        mock_client.get_state_version_output = AsyncMock(
            side_effect=[
                [{"name": "output1"}],
                [{"name": "output2"}],
            ]
        )

        with patch(
            "webhook_processors.state_version_webhook_processor.init_terraform_client"
        ) as mock_init:
            mock_init.return_value = mock_client

            result = await processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert len(result.updated_raw_results) == 2
            assert result.updated_raw_results[0]["id"] == "sv-1"
            assert result.updated_raw_results[1]["id"] == "sv-2"
            assert "__output" in result.updated_raw_results[0]
            assert "__output" in result.updated_raw_results[1]
            assert result.deleted_raw_results == []

    @pytest.mark.asyncio
    async def test_handle_event_no_state_versions(self, processor: Any) -> None:
        payload: dict[str, Any] = {
            "workspace_name": "test-workspace",
            "organization_name": "test-org",
        }
        resource_config = MagicMock()

        mock_client = MagicMock()

        async def mock_state_versions_generator(
            workspace_name: str, organization_name: str
        ) -> Any:
            yield []

        mock_client.get_state_versions_for_single_workspace = (
            mock_state_versions_generator
        )

        with patch(
            "webhook_processors.state_version_webhook_processor.init_terraform_client"
        ) as mock_init:
            mock_init.return_value = mock_client

            result = await processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert len(result.updated_raw_results) == 0
            assert result.deleted_raw_results == []

    @pytest.mark.asyncio
    async def test_handle_event_multiple_batches(self, processor: Any) -> None:
        payload: dict[str, Any] = {
            "workspace_name": "test-workspace",
            "organization_name": "test-org",
        }
        resource_config = MagicMock()

        mock_client = MagicMock()

        async def mock_state_versions_generator(
            workspace_name: str, organization_name: str
        ) -> Any:
            yield [{"id": "sv-1", "attributes": {"serial": 1}}]
            yield [{"id": "sv-2", "attributes": {"serial": 2}}]

        mock_client.get_state_versions_for_single_workspace = (
            mock_state_versions_generator
        )
        mock_client.get_state_version_output = AsyncMock(
            side_effect=[
                [{"name": "output1"}],
                [{"name": "output2"}],
            ]
        )

        with patch(
            "webhook_processors.state_version_webhook_processor.init_terraform_client"
        ) as mock_init:
            mock_init.return_value = mock_client

            result = await processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert len(result.updated_raw_results) == 2

    @pytest.mark.asyncio
    async def test_handle_event_enrichment_partial_failure(
        self, processor: Any
    ) -> None:
        payload: dict[str, Any] = {
            "workspace_name": "test-workspace",
            "organization_name": "test-org",
        }
        resource_config = MagicMock()

        mock_client = MagicMock()
        state_versions = [
            {"id": "sv-1", "attributes": {"serial": 1}},
            {"id": "sv-2", "attributes": {"serial": 2}},
        ]

        async def mock_state_versions_generator(
            workspace_name: str, organization_name: str
        ) -> Any:
            yield state_versions

        mock_client.get_state_versions_for_single_workspace = (
            mock_state_versions_generator
        )
        mock_client.get_state_version_output = AsyncMock(
            side_effect=[
                [{"name": "output1"}],
                Exception("API Error"),
            ]
        )

        with patch(
            "webhook_processors.state_version_webhook_processor.init_terraform_client"
        ) as mock_init:
            mock_init.return_value = mock_client

            result = await processor.handle_event(payload, resource_config)

            assert len(result.updated_raw_results) == 2
            assert result.updated_raw_results[0]["__output"] == [{"name": "output1"}]
            assert result.updated_raw_results[1]["__output"] == {}

    @pytest.mark.asyncio
    async def test_handle_event_extracts_correct_payload_fields(
        self, processor: Any
    ) -> None:
        payload: dict[str, Any] = {
            "workspace_name": "my-workspace",
            "organization_name": "my-org",
            "run_id": "run-123",
        }
        resource_config = MagicMock()

        mock_client = MagicMock()

        async def mock_state_versions_generator(
            workspace_name: str, organization_name: str
        ) -> Any:
            yield []

        mock_generator_wrapped = MagicMock(side_effect=mock_state_versions_generator)
        mock_client.get_state_versions_for_single_workspace = mock_generator_wrapped

        with patch(
            "webhook_processors.state_version_webhook_processor.init_terraform_client"
        ) as mock_init:
            mock_init.return_value = mock_client

            await processor.handle_event(payload, resource_config)

            mock_generator_wrapped.assert_called_once_with("my-workspace", "my-org")
