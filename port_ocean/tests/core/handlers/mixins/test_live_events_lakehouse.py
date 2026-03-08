from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from port_ocean.clients.port.client import PortClient
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.entities_state_applier.port.applier import (
    HttpEntitiesStateApplier,
)
from port_ocean.core.handlers.entity_processor.jq_entity_processor import (
    JQEntityProcessor,
)
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults
from port_ocean.core.integrations.mixins.live_events import LiveEventsMixin
from port_ocean.core.models import LakehouseOperation
from port_ocean.ocean import Ocean


one_webhook_event_raw_results_for_creation = WebhookEventRawResults(
    updated_raw_results=[
        {
            "name": "repo-one",
            "links": {"html": {"href": "https://example.com/repo-one"}},
            "main_branch": "main",
        }
    ],
    deleted_raw_results=[],
)
one_webhook_event_raw_results_for_creation.resource = ResourceConfig(
    kind="repository",
    selector=Selector(query="true"),
    port=PortResourceConfig(
        entity=MappingsConfig(
            mappings=EntityMapping(
                identifier=".name",
                title=".name",
                blueprint='"service"',
                properties={
                    "url": ".links.html.href",
                    "defaultBranch": ".main_branch",
                },
                relations={},
            )
        )
    ),
)

one_webhook_event_raw_results_for_deletion = WebhookEventRawResults(
    deleted_raw_results=[
        {
            "name": "repo-one",
            "links": {"html": {"href": "https://example.com/repo-one"}},
            "main_branch": "main",
        }
    ],
    updated_raw_results=[],
)
one_webhook_event_raw_results_for_deletion.resource = ResourceConfig(
    kind="repository",
    selector=Selector(query="true"),
    port=PortResourceConfig(
        entity=MappingsConfig(
            mappings=EntityMapping(
                identifier=".name",
                title=".name",
                blueprint='"service"',
                properties={
                    "url": ".links.html.href",
                    "defaultBranch": ".main_branch",
                },
                relations={},
            )
        )
    ),
)


@pytest.fixture
def mock_context(monkeypatch: Any) -> PortOceanContext:
    mock_context = AsyncMock()
    monkeypatch.setattr(PortOceanContext, "app", mock_context)
    return mock_context


@pytest.fixture
def mock_entity_processor(mock_context: PortOceanContext) -> JQEntityProcessor:
    return JQEntityProcessor(mock_context)


@pytest.fixture
def mock_entities_state_applier(
    mock_context: PortOceanContext,
) -> HttpEntitiesStateApplier:
    return HttpEntitiesStateApplier(mock_context)


@pytest.fixture
def mock_port_app_config_handler() -> MagicMock:
    handler = MagicMock()
    handler.get_port_app_config = AsyncMock()
    return handler


@pytest.fixture
def mock_http_client() -> MagicMock:
    mock_http_client = MagicMock()

    async def post(url: str, *args: Any, **kwargs: Any) -> MagicMock:
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"ok": True}
        return response

    mock_http_client.post = AsyncMock(side_effect=post)
    return mock_http_client


@pytest.fixture
def mock_port_client(mock_http_client: MagicMock) -> PortClient:
    mock_port_client = PortClient(
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )
    mock_port_client.auth = AsyncMock()
    mock_port_client.auth.headers = AsyncMock(
        return_value={
            "Authorization": "test",
            "User-Agent": "test",
        }
    )

    mock_port_client.search_entities = AsyncMock(return_value=[])  # type: ignore
    mock_port_client.client = mock_http_client
    return mock_port_client


@pytest.fixture
def mock_ocean(mock_port_client: PortClient) -> Ocean:
    with patch("port_ocean.ocean.Ocean.__init__", return_value=None):
        ocean_mock = Ocean(
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )
        ocean_mock.config = MagicMock()
        ocean_mock.config.port = MagicMock()
        ocean_mock.config.port.port_app_config_cache_ttl = 60
        ocean_mock.port_client = mock_port_client

        return ocean_mock


@pytest.fixture
def mock_live_events_mixin(
    mock_entity_processor: JQEntityProcessor,
    mock_entities_state_applier: HttpEntitiesStateApplier,
    mock_port_app_config_handler: MagicMock,
) -> LiveEventsMixin:
    mixin = LiveEventsMixin()
    mixin._entity_processor = mock_entity_processor
    mixin._entities_state_applier = mock_entities_state_applier
    mixin._port_app_config_handler = mock_port_app_config_handler
    return mixin


@pytest.mark.asyncio
async def test_send_webhook_raw_data_to_lakehouse_enabled_upsert(
    mock_live_events_mixin: LiveEventsMixin,
    mock_ocean: Ocean,
) -> None:
    """Test lakehouse send when enabled - UPSERT operation with raw data"""
    from unittest.mock import MagicMock
    from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

    with patch("port_ocean.core.integrations.mixins.live_events.ocean", mock_ocean):
        mock_ocean.port_client.post_integration_raw_data = AsyncMock()

        # Create webhook event
        webhook_event = MagicMock(spec=WebhookEvent)
        webhook_event.trace_id = "test-event-id"

        raw_data = [{"name": "repo-one", "stars": 100}]
        webhook_results = WebhookEventRawResults(
            updated_raw_results=raw_data,
            deleted_raw_results=[],
        )
        webhook_results.resource = one_webhook_event_raw_results_for_creation.resource
        webhook_results._webhook_trace_id = webhook_event.trace_id

        # Call the method
        await mock_live_events_mixin._send_webhook_raw_data_to_lakehouse(
            [webhook_results]
        )

        # Verify lakehouse API called with UPSERT and raw data
        mock_ocean.port_client.post_integration_raw_data.assert_called_once_with(
            raw_data,
            "test-event-id",
            "repository",
            operation=LakehouseOperation.UPSERT,
        )


@pytest.mark.asyncio
async def test_send_webhook_raw_data_to_lakehouse_enabled_delete(
    mock_live_events_mixin: LiveEventsMixin,
    mock_ocean: Ocean,
) -> None:
    """Test lakehouse send when enabled - DELETE operation with raw data"""
    from unittest.mock import MagicMock
    from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

    with patch("port_ocean.core.integrations.mixins.live_events.ocean", mock_ocean):
        mock_ocean.port_client.post_integration_raw_data = AsyncMock()

        # Create webhook event
        webhook_event = MagicMock(spec=WebhookEvent)
        webhook_event.trace_id = "test-event-id"

        raw_data = [{"id": "123"}]
        webhook_results = WebhookEventRawResults(
            updated_raw_results=[],
            deleted_raw_results=raw_data,
        )
        webhook_results.resource = one_webhook_event_raw_results_for_deletion.resource
        webhook_results._webhook_trace_id = webhook_event.trace_id

        # Call the method
        await mock_live_events_mixin._send_webhook_raw_data_to_lakehouse(
            [webhook_results]
        )

        # Verify lakehouse API called with DELETE and raw data
        mock_ocean.port_client.post_integration_raw_data.assert_called_once_with(
            raw_data,
            "test-event-id",
            "repository",
            operation=LakehouseOperation.DELETE,
        )


@pytest.mark.asyncio
async def test_send_webhook_raw_data_to_lakehouse_api_failure(
    mock_live_events_mixin: LiveEventsMixin,
    mock_ocean: Ocean,
) -> None:
    """Test that lakehouse API failure doesn't break webhook processing"""
    from unittest.mock import MagicMock
    from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

    with patch("port_ocean.core.integrations.mixins.live_events.ocean", mock_ocean):
        # Mock API to raise exception
        mock_ocean.port_client.post_integration_raw_data = AsyncMock(
            side_effect=Exception("Lakehouse API error")
        )

        # Create webhook event
        webhook_event = MagicMock(spec=WebhookEvent)
        webhook_event.trace_id = "test-event-id"

        webhook_results = WebhookEventRawResults(
            updated_raw_results=[{"name": "repo-one"}],
            deleted_raw_results=[],
        )
        webhook_results.resource = one_webhook_event_raw_results_for_creation.resource
        webhook_results._webhook_trace_id = webhook_event.trace_id

        # Call the method - should not raise exception
        await mock_live_events_mixin._send_webhook_raw_data_to_lakehouse(
            [webhook_results]
        )

        # Verify API was called but exception was caught
        mock_ocean.port_client.post_integration_raw_data.assert_called_once()


@pytest.mark.asyncio
async def test_send_webhook_raw_data_to_lakehouse_empty_results(
    mock_live_events_mixin: LiveEventsMixin,
    mock_ocean: Ocean,
) -> None:
    """Test that empty results don't call lakehouse API"""
    with patch("port_ocean.core.integrations.mixins.live_events.ocean", mock_ocean):
        mock_ocean.port_client.post_integration_raw_data = AsyncMock()

        webhook_results = WebhookEventRawResults(
            updated_raw_results=[],
            deleted_raw_results=[],
        )
        webhook_results.resource = one_webhook_event_raw_results_for_creation.resource
        webhook_results._webhook_trace_id = "test-event-id"

        # Call the method
        await mock_live_events_mixin._send_webhook_raw_data_to_lakehouse(
            [webhook_results]
        )

        # Verify lakehouse API not called when there's no data
        mock_ocean.port_client.post_integration_raw_data.assert_not_called()


@pytest.mark.asyncio
async def test_send_webhook_raw_data_to_lakehouse_both_operations(
    mock_live_events_mixin: LiveEventsMixin,
    mock_ocean: Ocean,
) -> None:
    """Test lakehouse send with both UPSERT and DELETE operations"""
    from unittest.mock import MagicMock, call
    from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

    with patch("port_ocean.core.integrations.mixins.live_events.ocean", mock_ocean):
        mock_ocean.port_client.post_integration_raw_data = AsyncMock()

        # Create webhook event
        webhook_event = MagicMock(spec=WebhookEvent)
        webhook_event.trace_id = "test-event-id"

        upsert_data = [{"name": "repo-one"}]
        delete_data = [{"id": "123"}]
        webhook_results = WebhookEventRawResults(
            updated_raw_results=upsert_data,
            deleted_raw_results=delete_data,
        )
        webhook_results.resource = one_webhook_event_raw_results_for_creation.resource
        webhook_results._webhook_trace_id = webhook_event.trace_id

        # Call the method
        await mock_live_events_mixin._send_webhook_raw_data_to_lakehouse(
            [webhook_results]
        )

        # Verify both UPSERT and DELETE calls were made
        assert mock_ocean.port_client.post_integration_raw_data.call_count == 2
        mock_ocean.port_client.post_integration_raw_data.assert_has_calls(
            [
                call(
                    upsert_data,
                    "test-event-id",
                    "repository",
                    operation=LakehouseOperation.UPSERT,
                ),
                call(
                    delete_data,
                    "test-event-id",
                    "repository",
                    operation=LakehouseOperation.DELETE,
                ),
            ]
        )
