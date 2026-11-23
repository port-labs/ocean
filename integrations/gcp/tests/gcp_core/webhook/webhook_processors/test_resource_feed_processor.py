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

MODULE = "gcp_core.webhook.webhook_processors.resource_feed_processor"


def _pubsub_payload(asset_data: dict[str, Any]) -> EventPayload:
    encoded = base64.b64encode(json.dumps(asset_data).encode()).decode()
    return {"message": {"data": encoded}}


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
def asset_payload() -> dict[str, Any]:
    return {
        "asset": {
            "assetType": ASSET_TYPE,
            "name": ASSET_NAME,
            "ancestors": [ASSET_PROJECT, "organizations/123"],
            # A content-type=resource feed always carries this; feed_event_to_resource reads it.
            "resource": {"data": ASSET_RESOURCE_DATA},
        },
        "deleted": False,
    }


@pytest.fixture
def pubsub_payload(asset_payload: dict[str, Any]) -> EventPayload:
    return _pubsub_payload(asset_payload)


@pytest.fixture
def mock_webhook_event(pubsub_payload: EventPayload) -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", headers={}, payload=pubsub_payload)


@pytest.fixture
def processor(mock_ocean_context: None, mock_webhook_event: WebhookEvent) -> Any:
    from gcp_core.webhook.webhook_processors.resource_feed_processor import (
        ResourceFeedProcessor,
    )

    return ResourceFeedProcessor(event=mock_webhook_event)


@pytest.fixture
def resource_config() -> MagicMock:
    config = MagicMock()
    config.kind = ASSET_TYPE
    config.selector = MagicMock(preserve_api_response_case_style=False)
    return config


class TestGetMatchingKinds:
    async def test_returns_the_assets_own_type(
        self, processor: Any, mock_webhook_event: WebhookEvent
    ) -> None:
        # The manager intersects this with the mapping and pairs each kind with every resource
        # of that kind, so filtering here would repeat the event once per matching resource.
        assert await processor.get_matching_kinds(mock_webhook_event) == [ASSET_TYPE]

    async def test_returns_the_assets_own_type_even_when_unmapped(
        self, processor: Any, asset_payload: dict[str, Any]
    ) -> None:
        payload = json.loads(json.dumps(asset_payload))
        payload["asset"]["assetType"] = "storage.googleapis.com/Bucket"
        event = WebhookEvent(trace_id="t", headers={}, payload=_pubsub_payload(payload))

        assert await processor.get_matching_kinds(event) == [
            "storage.googleapis.com/Bucket"
        ]

    async def test_returns_nothing_for_an_unusable_payload(
        self, processor: Any
    ) -> None:
        event = WebhookEvent(trace_id="t", headers={}, payload={"not": "a message"})
        assert await processor.get_matching_kinds(event) == []


class TestHandleEvent:
    async def test_returns_updated_results_for_created_resource(
        self,
        processor: Any,
        pubsub_payload: EventPayload,
        resource_config: MagicMock,
    ) -> None:
        with (
            patch(
                f"{MODULE}.resolve_request_controllers",
                new=AsyncMock(return_value=(MagicMock(), MagicMock())),
            ),
            patch(
                f"{MODULE}.feed_event_to_resource",
                new=AsyncMock(return_value=ASSET_RESOURCE_DATA),
            ),
        ):
            result = await processor.handle_event(pubsub_payload, resource_config)

        assert result.updated_raw_results == [ASSET_RESOURCE_DATA]
        assert result.deleted_raw_results == []

    async def test_returns_deleted_results_for_deleted_resource(
        self,
        processor: Any,
        asset_payload: dict[str, Any],
        resource_config: MagicMock,
    ) -> None:
        payload = _pubsub_payload({**asset_payload, "deleted": True})

        with (
            patch(
                f"{MODULE}.resolve_request_controllers",
                new=AsyncMock(return_value=(MagicMock(), MagicMock())),
            ),
            patch(
                f"{MODULE}.feed_event_to_resource",
                new=AsyncMock(return_value=ASSET_RESOURCE_DATA),
            ),
        ):
            result = await processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == [ASSET_RESOURCE_DATA]

    @pytest.mark.parametrize(
        "ancestors",
        [
            pytest.param(["organizations/123"], id="no_project_ancestor"),
            pytest.param([], id="empty_ancestors"),
            pytest.param(None, id="ancestors_absent"),
        ],
    )
    async def test_returns_empty_results_without_a_project_ancestor(
        self,
        processor: Any,
        asset_payload: dict[str, Any],
        resource_config: MagicMock,
        ancestors: list[str] | None,
    ) -> None:
        payload = json.loads(json.dumps(asset_payload))
        if ancestors is None:
            del payload["asset"]["ancestors"]
        else:
            payload["asset"]["ancestors"] = ancestors

        result = await processor.handle_event(_pubsub_payload(payload), resource_config)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
