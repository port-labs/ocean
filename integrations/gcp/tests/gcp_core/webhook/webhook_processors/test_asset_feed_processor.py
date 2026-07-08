import base64
import json
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import port_ocean.context.ocean as ocean_context_module
import pytest
from port_ocean.context.ocean import (
    PortOceanContext,
    initialize_port_ocean_context,
)
from port_ocean.core.handlers.webhook.webhook_event import EventPayload, WebhookEvent


ASSET_TYPE = "compute.googleapis.com/Instance"
ASSET_NAME = "//compute.googleapis.com/projects/test-project/zones/us-central1-a/instances/test-instance"
ASSET_PROJECT = "projects/test-project"
ASSET_RESOURCE_DATA = {"name": ASSET_NAME, "assetType": ASSET_TYPE}


def _encode_asset_data(asset_data: dict[str, Any]) -> str:
    return base64.b64encode(json.dumps(asset_data).encode()).decode()


@pytest.fixture(autouse=True)
def mock_ocean_context() -> Generator[None, None, None]:
    mock_app: MagicMock = MagicMock()
    mock_app.config.integration.config = {
        "search_all_resources_per_minute_quota": 100,
        "encoded_adc_configuration": None,
    }
    mock_app.integration_router = MagicMock()
    mock_app.port_client = MagicMock()
    mock_app.cache_provider = AsyncMock()
    mock_app.cache_provider.get.return_value = None
    initialize_port_ocean_context(mock_app)
    yield
    ocean_context_module._port_ocean = PortOceanContext(None)


@pytest.fixture
def processor(mock_ocean_context: None, mock_webhook_event: WebhookEvent) -> Any:
    from gcp_core.webhook.webhook_processors.asset_feed_processor import (
        AssetFeedProcessor,
    )

    return AssetFeedProcessor(event=mock_webhook_event)


@pytest.fixture
def asset_payload() -> dict[str, Any]:
    return {
        "asset": {
            "assetType": ASSET_TYPE,
            "name": ASSET_NAME,
            "ancestors": [ASSET_PROJECT, "organizations/123"],
        },
        "deleted": False,
    }


@pytest.fixture
def pubsub_payload(asset_payload: dict[str, Any]) -> EventPayload:
    return {
        "message": {
            "data": _encode_asset_data(asset_payload),
        }
    }


@pytest.fixture
def mock_webhook_event(pubsub_payload: EventPayload) -> WebhookEvent:
    return WebhookEvent(
        trace_id="test-trace-id",
        headers={},
        payload=pubsub_payload,
    )


@pytest.fixture
def resource_config() -> MagicMock:
    config = MagicMock()
    config.selector = MagicMock()
    config.selector.preserve_api_response_case_style = False
    return config


class TestShouldProcessEvent:
    async def test_returns_true_for_valid_asset_event(
        self,
        mock_ocean_context: None,
        processor: MagicMock,
        mock_webhook_event: WebhookEvent,
        asset_payload: dict[str, Any],
    ) -> None:
        with patch(
            "gcp_core.webhook.webhook_processors.asset_feed_processor.parse_asset_data",
            new=AsyncMock(return_value=asset_payload),
        ):
            assert await processor.should_process_event(mock_webhook_event) is True

    async def test_returns_false_for_feed_created_confirmation(
        self,
        mock_ocean_context: None,
        processor: MagicMock,
        mock_webhook_event: WebhookEvent,
    ) -> None:
        from gcp_core.errors import GotFeedCreatedSuccessfullyMessageError

        with patch(
            "gcp_core.webhook.webhook_processors.asset_feed_processor.parse_asset_data",
            new=AsyncMock(side_effect=GotFeedCreatedSuccessfullyMessageError),
        ):
            assert await processor.should_process_event(mock_webhook_event) is False

    async def test_returns_false_for_unparseable_payload(
        self,
        mock_ocean_context: None,
        processor: MagicMock,
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            headers={},
            payload={"not": "a pubsub message"},
        )
        assert await processor.should_process_event(event) is False


class TestGetMatchingKinds:
    async def test_returns_asset_type_as_kind(
        self,
        mock_ocean_context: None,
        processor: MagicMock,
        mock_webhook_event: WebhookEvent,
        asset_payload: dict[str, Any],
    ) -> None:
        mock_resource_config = MagicMock()
        mock_resource_config.kind = ASSET_TYPE

        mock_event = MagicMock()
        mock_event.port_app_config.resources = [mock_resource_config]
        with (
            patch(
                "gcp_core.webhook.webhook_processors.asset_feed_processor.parse_asset_data",
                new=AsyncMock(return_value=asset_payload),
            ),
            patch(
                "gcp_core.webhook.webhook_processors.asset_feed_processor.port_event",
                new=mock_event,
            ),
        ):
            kinds = await processor.get_matching_kinds(mock_webhook_event)

        assert kinds == [ASSET_TYPE]


class TestValidatePayload:
    @pytest.mark.parametrize(
        ("payload", "expected"),
        [
            pytest.param(
                {"message": {"data": "encoded"}},
                True,
                id="valid",
            ),
            pytest.param(
                {"message": {}},
                False,
                id="missing_data_key",
            ),
            pytest.param(
                {"not": "a pubsub message"},
                False,
                id="missing_message_key",
            ),
        ],
    )
    async def test_validate_payload(
        self,
        mock_ocean_context: None,
        processor: MagicMock,
        payload: EventPayload,
        expected: bool,
    ) -> None:
        with patch(
            "gcp_core.webhook.webhook_processors.asset_feed_processor.parse_asset_data",
            new=AsyncMock(return_value={"some": "data"}),
        ):
            assert await processor.validate_payload(payload) is expected


class TestAuthenticate:
    async def test_always_returns_true(
        self,
        mock_ocean_context: None,
        processor: MagicMock,
        pubsub_payload: EventPayload,
    ) -> None:
        assert await processor.authenticate(pubsub_payload, {}) is True


class TestHandleEvent:
    async def test_returns_updated_results_for_created_resource(
        self,
        mock_ocean_context: None,
        processor: MagicMock,
        pubsub_payload: EventPayload,
        asset_payload: dict[str, Any],
        resource_config: MagicMock,
    ) -> None:
        with (
            # NEW: Mock resolve_request_controllers instead of global variables
            patch(
                "gcp_core.webhook.webhook_processors.asset_feed_processor.resolve_request_controllers",
                new=AsyncMock(return_value=(MagicMock(), MagicMock())),
            ),
            patch(
                "gcp_core.webhook.webhook_processors.asset_feed_processor.parse_asset_data",
                new=AsyncMock(return_value=asset_payload),
            ),
            patch(
                "gcp_core.webhook.webhook_processors.asset_feed_processor.get_project_name_from_ancestors",
                return_value=ASSET_PROJECT,
            ),
            patch(
                "gcp_core.webhook.webhook_processors.asset_feed_processor.feed_event_to_resource",
                new=AsyncMock(return_value=ASSET_RESOURCE_DATA),
            ),
        ):
            result = await processor.handle_event(pubsub_payload, resource_config)

        assert result.updated_raw_results == [ASSET_RESOURCE_DATA]
        assert result.deleted_raw_results == []

    async def test_returns_deleted_results_for_deleted_resource(
        self,
        mock_ocean_context: None,
        processor: MagicMock,
        asset_payload: dict[str, Any],
        resource_config: MagicMock,
    ) -> None:
        deleted_payload = {**asset_payload, "deleted": True}
        pubsub_payload: EventPayload = {
            "message": {"data": _encode_asset_data(deleted_payload)}
        }

        with (
            patch(
                "gcp_core.webhook.webhook_processors.asset_feed_processor.resolve_request_controllers",
                new=AsyncMock(return_value=(MagicMock(), MagicMock())),
            ),
            patch(
                "gcp_core.webhook.webhook_processors.asset_feed_processor.parse_asset_data",
                new=AsyncMock(return_value=deleted_payload),
            ),
            patch(
                "gcp_core.webhook.webhook_processors.asset_feed_processor.get_project_name_from_ancestors",
                return_value=ASSET_PROJECT,
            ),
            patch(
                "gcp_core.webhook.webhook_processors.asset_feed_processor.feed_event_to_resource",
                new=AsyncMock(return_value=ASSET_RESOURCE_DATA),
            ),
        ):
            result = await processor.handle_event(pubsub_payload, resource_config)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == [ASSET_RESOURCE_DATA]

    async def test_returns_empty_results_when_no_project_ancestor(
        self,
        mock_ocean_context: None,
        processor: MagicMock,
        pubsub_payload: EventPayload,
        asset_payload: dict[str, Any],
        resource_config: MagicMock,
    ) -> None:
        from gcp_core.errors import AssetHasNoProjectAncestorError

        with (
            patch(
                "gcp_core.webhook.webhook_processors.asset_feed_processor.parse_asset_data",
                new=AsyncMock(return_value=asset_payload),
            ),
            patch(
                "gcp_core.webhook.webhook_processors.asset_feed_processor.get_project_name_from_ancestors",
                side_effect=AssetHasNoProjectAncestorError,
            ),
        ):
            result = await processor.handle_event(pubsub_payload, resource_config)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
