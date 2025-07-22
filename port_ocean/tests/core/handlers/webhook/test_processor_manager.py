import pytest
from port_ocean.core.handlers.webhook.processor_manager import (
    LiveEventsProcessorManager,
)
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    WebhookEvent,
    WebhookEventRawResults,
    EventPayload,
)
from fastapi import APIRouter
from port_ocean.core.integrations.mixins.handler import HandlerMixin
from port_ocean.utils.signal import SignalHandler
from typing import Dict, Any
import asyncio
from fastapi.testclient import TestClient
from fastapi import FastAPI
from port_ocean.context.ocean import PortOceanContext
from unittest.mock import AsyncMock
from port_ocean.context.event import EventContext, event_context, EventType
from port_ocean.context.ocean import ocean
from unittest.mock import MagicMock, patch
from httpx import Response
from port_ocean.clients.port.client import PortClient
from port_ocean import Ocean
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortAppConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.mixins.live_events import LiveEventsMixin
from port_ocean.core.models import Entity
from port_ocean.exceptions.webhook_processor import (
    RetryableError,
    WebhookEventNotSupportedError,
)
from port_ocean.core.handlers.queue import LocalQueue


class MockProcessor(AbstractWebhookProcessor):
    async def authenticate(
        self, payload: Dict[str, Any], headers: Dict[str, str]
    ) -> bool:
        return True

    async def validate_payload(self, payload: Dict[str, Any]) -> bool:
        return True

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return True

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return ["repository"]


class MockProcessorFalse(AbstractWebhookProcessor):
    async def authenticate(
        self, payload: Dict[str, Any], headers: Dict[str, str]
    ) -> bool:
        return True

    async def validate_payload(self, payload: Dict[str, Any]) -> bool:
        return True

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return False

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return ["repository"]


class MockWebhookProcessor(AbstractWebhookProcessor):
    def __init__(self, event: WebhookEvent) -> None:
        super().__init__(event)
        self.processed = False
        self.cancel_called = False
        self.error_to_raise: Exception | asyncio.CancelledError | None = None
        self.retry_count = 0
        self.max_retries = 3

    async def authenticate(
        self, payload: Dict[str, Any], headers: Dict[str, str]
    ) -> bool:
        return True

    async def validate_payload(self, payload: Dict[str, Any]) -> bool:
        return True

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        if self.error_to_raise:
            raise self.error_to_raise
        self.processed = True
        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

    async def cancel(self) -> None:
        self.cancel_called = True

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return True

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return ["test"]


class MockWebhookHandlerForProcessWebhookRequest(AbstractWebhookProcessor):
    """Concrete implementation for testing."""

    def __init__(
        self,
        event: WebhookEvent,
        should_fail: bool = False,
        fail_count: int = 0,
        max_retries: int = 3,
    ) -> None:
        super().__init__(event)
        self.authenticated = False
        self.validated = False
        self.handled = False
        self.should_fail = should_fail
        self.fail_count = fail_count
        self.current_fails = 0
        self.error_handler_called = False
        self.cancelled = False
        self.max_retries = max_retries

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        self.authenticated = True
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        self.validated = True
        return True

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        if self.should_fail and self.current_fails < self.fail_count:
            self.current_fails += 1
            raise RetryableError("Temporary failure")
        self.handled = True
        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return ["repository"]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Filter the event data before processing."""
        return True

    async def cancel(self) -> None:
        self.cancelled = True

    async def on_error(self, error: Exception) -> None:
        self.error_handler_called = True
        await super().on_error(error)


@pytest.fixture
def processor_manager() -> LiveEventsProcessorManager:
    router = APIRouter()
    signal_handler = SignalHandler()
    return LiveEventsProcessorManager(
        router,
        signal_handler,
        max_event_processing_seconds=3,
        max_wait_seconds_before_shutdown=3,
    )


@pytest.fixture
def webhook_event() -> WebhookEvent:
    return WebhookEvent(payload={}, headers={}, trace_id="test-trace")


@pytest.fixture
def webhook_event_for_process_webhook_request() -> WebhookEvent:
    return WebhookEvent(
        trace_id="test-trace",
        payload={"test": "data"},
        headers={"content-type": "application/json"},
    )


@pytest.fixture
def processor_manager_for_process_webhook_request() -> LiveEventsProcessorManager:
    return LiveEventsProcessorManager(APIRouter(), SignalHandler(), 3, 3)


@pytest.fixture
def processor(
    webhook_event_for_process_webhook_request: WebhookEvent,
) -> MockWebhookHandlerForProcessWebhookRequest:
    return MockWebhookHandlerForProcessWebhookRequest(
        webhook_event_for_process_webhook_request
    )


@pytest.fixture
def mock_port_app_config() -> PortAppConfig:
    return PortAppConfig(
        enable_merge_entity=True,
        delete_dependent_entities=True,
        create_missing_related_entities=False,
        resources=[
            ResourceConfig(
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
        ],
    )


@pytest.fixture
def mock_http_client() -> MagicMock:
    mock_http_client = MagicMock()
    mock_upserted_entities = []

    async def post(url: str, *args: Any, **kwargs: Any) -> Response:
        entity = kwargs.get("json", {})
        if entity.get("properties", {}).get("mock_is_to_fail", {}):
            return Response(
                404, headers=MagicMock(), json={"ok": False, "error": "not_found"}
            )

        mock_upserted_entities.append(
            f"{entity.get('identifier')}-{entity.get('blueprint')}"
        )
        return Response(
            200,
            json={
                "entity": {
                    "identifier": entity.get("identifier"),
                    "blueprint": entity.get("blueprint"),
                }
            },
        )

    mock_http_client.post = AsyncMock(side_effect=post)
    return mock_http_client


@pytest.fixture
def mock_port_client(mock_http_client: MagicMock) -> PortClient:
    mock_port_client = PortClient(
        MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()
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
        ocean_mock.integration_router = APIRouter()
        ocean_mock.fast_api_app = FastAPI()
        return ocean_mock


@pytest.fixture
def mock_context(mock_ocean: Ocean) -> PortOceanContext:
    context = PortOceanContext(mock_ocean)
    ocean._app = context.app
    return context


entity = Entity(
    identifier="repo-one",
    blueprint="service",
    title="repo-one",
    team=[],
    properties={
        "url": "https://example.com/repo-one",
        "defaultBranch": "main",
    },
    relations={},
)


@pytest.mark.asyncio
async def test_extractMatchingProcessors_processorMatch(
    processor_manager: LiveEventsProcessorManager,
    webhook_event: WebhookEvent,
    mock_port_app_config: PortAppConfig,
) -> None:
    test_path = "/test"
    processor_manager.register_processor(test_path, MockProcessor)

    async with event_context(EventType.HTTP_REQUEST, trigger_type="request") as event:
        event.port_app_config = mock_port_app_config
        processors = await processor_manager._extract_matching_processors(
            webhook_event, test_path
        )

        assert len(processors) == 1
        config, processor = processors[0]
        assert isinstance(processor, MockProcessor)
        assert config.kind == "repository"
        assert processor.event != webhook_event
        assert processor.event.payload == webhook_event.payload


@pytest.mark.asyncio
async def test_extractMatchingProcessors_noMatch(
    processor_manager: LiveEventsProcessorManager,
    webhook_event: WebhookEvent,
    mock_port_app_config: PortAppConfig,
) -> None:
    test_path = "/test"
    processor_manager.register_processor(test_path, MockProcessorFalse)

    with pytest.raises(
        WebhookEventNotSupportedError, match="No matching processors found"
    ):
        async with event_context(
            EventType.HTTP_REQUEST, trigger_type="request"
        ) as event:
            event.port_app_config = mock_port_app_config
            await processor_manager._extract_matching_processors(
                webhook_event, test_path
            )


@pytest.mark.asyncio
async def test_extractMatchingProcessors_multipleMatches(
    processor_manager: LiveEventsProcessorManager,
    webhook_event: WebhookEvent,
    mock_port_app_config: PortAppConfig,
) -> None:
    test_path = "/test"
    processor_manager.register_processor(test_path, MockProcessor)
    processor_manager.register_processor(test_path, MockProcessor)

    async with event_context(EventType.HTTP_REQUEST, trigger_type="request") as event:
        event.port_app_config = mock_port_app_config
        processors = await processor_manager._extract_matching_processors(
            webhook_event, test_path
        )

    assert len(processors) == 2
    assert all(isinstance(p, MockProcessor) for _, p in processors)
    assert all(p.event != webhook_event for _, p in processors)


@pytest.mark.asyncio
async def test_extractMatchingProcessors_onlyOneMatches(
    processor_manager: LiveEventsProcessorManager,
    webhook_event: WebhookEvent,
    mock_port_app_config: PortAppConfig,
) -> None:
    test_path = "/test"
    processor_manager.register_processor(test_path, MockProcessor)
    processor_manager.register_processor(test_path, MockProcessorFalse)

    async with event_context(EventType.HTTP_REQUEST, trigger_type="request") as event:
        event.port_app_config = mock_port_app_config
        processors = await processor_manager._extract_matching_processors(
            webhook_event, test_path
        )

    assert len(processors) == 1
    config, processor = processors[0]
    assert isinstance(processor, MockProcessor)
    assert config.kind == "repository"
    assert processor.event != webhook_event
    assert processor.event.payload == webhook_event.payload


@pytest.mark.asyncio
async def test_extractMatchingProcessors_noProcessorsRegistered(
    processor_manager: LiveEventsProcessorManager,
    webhook_event: WebhookEvent,
    mock_port_app_config: PortAppConfig,
) -> None:
    """Test that WebhookEventNotSupportedError is raised for unknown events without any registered processors"""
    test_path = "/unknown_path"
    # No processors registered for this path

    # Manually add the path to _processors_classes to simulate a path with no processors
    processor_manager._processors_classes[test_path] = []

    with pytest.raises(
        WebhookEventNotSupportedError, match="No matching processors found"
    ):
        async with event_context(
            EventType.HTTP_REQUEST, trigger_type="request"
        ) as event:
            event.port_app_config = mock_port_app_config
            await processor_manager._extract_matching_processors(
                webhook_event, test_path
            )


@pytest.mark.asyncio
async def test_extractMatchingProcessors_processorsAvailableButKindsNotConfigured(
    processor_manager: LiveEventsProcessorManager,
    webhook_event: WebhookEvent,
) -> None:
    """Test that processors available but kinds not configured returns empty list"""
    test_path = "/test"

    from port_ocean.core.handlers.port_app_config.models import (
        PortAppConfig,
        ResourceConfig,
    )

    # Create a mock processor that will match the event but return a kind not in the port app config
    class MockProcessorWithUnmappedKind(AbstractWebhookProcessor):
        async def authenticate(
            self, payload: Dict[str, Any], headers: Dict[str, str]
        ) -> bool:
            return True

        async def validate_payload(self, payload: Dict[str, Any]) -> bool:
            return True

        async def handle_event(
            self, payload: EventPayload, resource: ResourceConfig
        ) -> WebhookEventRawResults:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        async def should_process_event(self, event: WebhookEvent) -> bool:
            return True  # This processor will match

        async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
            return ["unmapped_kind"]  # This kind is not in the mock_port_app_config

    processor_manager.register_processor(test_path, MockProcessorWithUnmappedKind)

    empty_port_app_config = PortAppConfig(
        resources=[],
    )

    async with event_context(EventType.HTTP_REQUEST, trigger_type="request") as event:
        event.port_app_config = empty_port_app_config
        processors = await processor_manager._extract_matching_processors(
            webhook_event, test_path
        )

    assert len(processors) == 0


def test_registerProcessor_registrationWorks(
    processor_manager: LiveEventsProcessorManager,
) -> None:
    processor_manager.register_processor("/test", MockWebhookProcessor)
    assert "/test" in processor_manager._processors_classes
    assert len(processor_manager._processors_classes["/test"]) == 1
    assert isinstance(processor_manager._event_queues["/test"], LocalQueue)


def test_registerProcessor_multipleHandlers_allRegistered(
    processor_manager: LiveEventsProcessorManager,
) -> None:
    processor_manager.register_processor("/test", MockWebhookProcessor)
    processor_manager.register_processor("/test", MockWebhookProcessor)

    assert len(processor_manager._processors_classes["/test"]) == 2


def test_registerProcessor_invalidHandlerRegistration_throwsError(
    processor_manager: LiveEventsProcessorManager,
) -> None:
    """Test registration of invalid processor type."""

    with pytest.raises(ValueError):
        processor_manager.register_processor("/test", object)  # type: ignore


@pytest.mark.asyncio
async def test_processWebhookRequest_successfulProcessing(
    processor: MockWebhookHandlerForProcessWebhookRequest,
    processor_manager_for_process_webhook_request: LiveEventsProcessorManager,
    mock_port_app_config: PortAppConfig,
) -> None:
    """Test successful webhook processing flow."""
    await processor_manager_for_process_webhook_request._process_webhook_request(
        processor, mock_port_app_config.resources[0]
    )

    assert processor.authenticated
    assert processor.validated
    assert processor.handled
    assert not processor.error_handler_called


@pytest.mark.asyncio
async def test_processWebhookRequest_retryTwoTimesThenSuccessfulProcessing(
    webhook_event_for_process_webhook_request: WebhookEvent,
    processor_manager_for_process_webhook_request: LiveEventsProcessorManager,
    mock_port_app_config: PortAppConfig,
) -> None:
    """Test retry mechanism with temporary failures."""
    processor = MockWebhookHandlerForProcessWebhookRequest(
        webhook_event_for_process_webhook_request, should_fail=True, fail_count=2
    )

    await processor_manager_for_process_webhook_request._process_webhook_request(
        processor, mock_port_app_config.resources[0]
    )

    assert processor.handled
    assert processor.current_fails == 2
    assert processor.retry_count == 2
    assert processor.error_handler_called


@pytest.mark.asyncio
async def test_processWebhookRequest_maxRetriesExceeded_exceptionRaised(
    webhook_event: WebhookEvent,
    processor_manager_for_process_webhook_request: LiveEventsProcessorManager,
    mock_port_app_config: PortAppConfig,
) -> None:
    """Test behavior when max retries are exceeded."""
    processor = MockWebhookHandlerForProcessWebhookRequest(
        webhook_event, should_fail=True, fail_count=2, max_retries=1
    )

    with pytest.raises(RetryableError):
        await processor_manager_for_process_webhook_request._process_webhook_request(
            processor, mock_port_app_config.resources[0]
        )

    assert processor.retry_count == processor.max_retries
    assert processor.error_handler_called
    assert not processor.handled


@pytest.mark.asyncio
@patch(
    "port_ocean.core.handlers.entities_state_applier.port.applier.HttpEntitiesStateApplier.upsert"
)
@patch(
    "port_ocean.core.handlers.entities_state_applier.port.applier.HttpEntitiesStateApplier.delete"
)
async def test_integrationTest_postRequestSent_webhookEventRawResultProcessed_entityUpserted(
    mock_delete: AsyncMock,
    mock_upsert: AsyncMock,
    mock_context: PortOceanContext,
    mock_port_app_config: PortAppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integration test for the complete webhook processing flow"""

    monkeypatch.setattr(
        "port_ocean.core.integrations.mixins.handler.ocean", mock_context
    )
    monkeypatch.setattr(
        "port_ocean.core.integrations.mixins.live_events.ocean", mock_context
    )
    processed_events: list[WebhookEventRawResults] = []
    mock_upsert.return_value = [entity]

    class TestProcessor(AbstractWebhookProcessor):
        def __init__(self, event: WebhookEvent) -> None:
            super().__init__(event)

        async def authenticate(
            self, payload: Dict[str, Any], headers: Dict[str, str]
        ) -> bool:
            return True

        async def validate_payload(self, payload: Dict[str, Any]) -> bool:
            return True

        async def handle_event(
            self, payload: EventPayload, resource: ResourceConfig
        ) -> WebhookEventRawResults:
            event_data = WebhookEventRawResults(
                updated_raw_results=[
                    {
                        "name": "repo-one",
                        "links": {"html": {"href": "https://example.com/repo-one"}},
                        "main_branch": "main",
                    }
                ],
                deleted_raw_results=[],
            )
            processed_events.append(event_data)
            return event_data

        async def should_process_event(self, event: WebhookEvent) -> bool:
            return True

        async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
            return ["repository"]

    processing_complete = asyncio.Event()
    original_process_data = LiveEventsMixin.sync_raw_results

    async def patched_export_single_resource(
        self: LiveEventsMixin, webhookEventRawResults: list[WebhookEventRawResults]
    ) -> None:
        try:
            await original_process_data(self, webhookEventRawResults)
        except Exception as e:
            raise e
        finally:
            processing_complete.set()

    monkeypatch.setattr(
        LiveEventsMixin,
        "sync_raw_results",
        patched_export_single_resource,
    )
    monkeypatch.setattr(
        HandlerMixin,
        "port_app_config_handler",
        AsyncMock(return_value=mock_port_app_config),
    )
    monkeypatch.setattr(
        EventContext,
        "port_app_config",
        mock_port_app_config,
    )
    test_path = "/webhook-test"
    mock_context.app.integration = BaseIntegration(ocean)
    mock_context.app.webhook_manager = LiveEventsProcessorManager(
        mock_context.app.integration_router,
        SignalHandler(),
        max_event_processing_seconds=3,
        max_wait_seconds_before_shutdown=3,
    )

    mock_context.app.webhook_manager.register_processor(test_path, TestProcessor)
    await mock_context.app.webhook_manager.start_processing_event_messages()
    mock_context.app.fast_api_app.include_router(
        mock_context.app.webhook_manager._router
    )
    client = TestClient(mock_context.app.fast_api_app)

    test_payload = {"test": "data"}

    async with event_context(EventType.HTTP_REQUEST, trigger_type="request"):
        response = client.post(
            test_path, json=test_payload, headers={"Content-Type": "application/json"}
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    try:
        await asyncio.wait_for(processing_complete.wait(), timeout=10.0)
    except asyncio.TimeoutError:
        pytest.fail("Event processing timed out")

    assert len(processed_events) == 1

    mock_upsert.assert_called_once()
    mock_delete.assert_not_called()

    await mock_context.app.webhook_manager.shutdown()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.handlers.entities_state_applier.port.applier.HttpEntitiesStateApplier.upsert"
)
@patch(
    "port_ocean.core.handlers.entities_state_applier.port.applier.HttpEntitiesStateApplier.delete"
)
async def test_integrationTest_postRequestSent_reachedTimeout_entityNotUpserted(
    mock_delete: AsyncMock,
    mock_upsert: AsyncMock,
    mock_context: PortOceanContext,
    mock_port_app_config: PortAppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integration test for the complete webhook processing flow"""

    monkeypatch.setattr(
        "port_ocean.core.integrations.mixins.handler.ocean", mock_context
    )
    monkeypatch.setattr(
        "port_ocean.core.integrations.mixins.live_events.ocean", mock_context
    )
    mock_upsert.return_value = [entity]
    test_state = {"exception_thrown": None}

    class TestProcessor(AbstractWebhookProcessor):
        async def authenticate(
            self, payload: Dict[str, Any], headers: Dict[str, str]
        ) -> bool:
            return True

        async def validate_payload(self, payload: Dict[str, Any]) -> bool:
            return True

        async def handle_event(
            self, payload: EventPayload, resource: ResourceConfig
        ) -> WebhookEventRawResults:
            await asyncio.sleep(3)
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        async def should_process_event(self, event: WebhookEvent) -> bool:
            return True

        async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
            return ["repository"]

    processing_complete = asyncio.Event()
    original_process_data = LiveEventsProcessorManager._process_single_event

    async def patched_process_single_event(
        self: LiveEventsProcessorManager,
        processor: AbstractWebhookProcessor,
        path: str,
        resource: ResourceConfig,
    ) -> WebhookEventRawResults:
        try:
            return await original_process_data(self, processor, path, resource)
        except Exception as e:
            test_state["exception_thrown"] = e  # type: ignore
            raise e
        finally:
            processing_complete.set()

    monkeypatch.setattr(
        LiveEventsProcessorManager,
        "_process_single_event",
        patched_process_single_event,
    )
    monkeypatch.setattr(
        HandlerMixin,
        "port_app_config_handler",
        AsyncMock(return_value=mock_port_app_config),
    )
    monkeypatch.setattr(
        EventContext,
        "port_app_config",
        mock_port_app_config,
    )
    test_path = "/webhook-test"
    mock_context.app.integration = BaseIntegration(ocean)
    mock_context.app.webhook_manager = LiveEventsProcessorManager(
        mock_context.app.integration_router,
        SignalHandler(),
        2,
        2,
    )

    mock_context.app.webhook_manager.register_processor(test_path, TestProcessor)
    await mock_context.app.webhook_manager.start_processing_event_messages()
    mock_context.app.fast_api_app.include_router(
        mock_context.app.webhook_manager._router
    )
    client = TestClient(mock_context.app.fast_api_app)

    test_payload = {"test": "data"}

    async with event_context(EventType.HTTP_REQUEST, trigger_type="request"):
        response = client.post(
            test_path, json=test_payload, headers={"Content-Type": "application/json"}
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    try:
        await asyncio.wait_for(processing_complete.wait(), timeout=100.0)
    except asyncio.TimeoutError:
        pytest.fail("Event processing timed out")

    assert isinstance(test_state["exception_thrown"], asyncio.TimeoutError) is True
    mock_upsert.assert_not_called()
    mock_delete.assert_not_called()

    await mock_context.app.webhook_manager.shutdown()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.handlers.entities_state_applier.port.applier.HttpEntitiesStateApplier.upsert"
)
@patch(
    "port_ocean.core.handlers.entities_state_applier.port.applier.HttpEntitiesStateApplier.delete"
)
async def test_integrationTest_postRequestSent_noMatchingHandlers_entityNotUpserted(
    mock_delete: AsyncMock,
    mock_upsert: AsyncMock,
    mock_context: PortOceanContext,
    mock_port_app_config: PortAppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integration test for the complete webhook processing flow"""

    monkeypatch.setattr(
        "port_ocean.core.integrations.mixins.handler.ocean", mock_context
    )
    monkeypatch.setattr(
        "port_ocean.core.integrations.mixins.live_events.ocean", mock_context
    )
    test_state = {"exception_thrown": None}
    mock_upsert.return_value = [entity]

    class TestProcessor(AbstractWebhookProcessor):
        async def authenticate(
            self, payload: Dict[str, Any], headers: Dict[str, str]
        ) -> bool:
            return True

        async def validate_payload(self, payload: Dict[str, Any]) -> bool:
            return True

        async def handle_event(
            self, payload: EventPayload, resource: ResourceConfig
        ) -> WebhookEventRawResults:
            event_data = WebhookEventRawResults(
                updated_raw_results=[
                    {
                        "name": "repo-one",
                        "links": {"html": {"href": "https://example.com/repo-one"}},
                        "main_branch": "main",
                    }
                ],
                deleted_raw_results=[],
            )
            return event_data

        async def should_process_event(self, event: WebhookEvent) -> bool:
            return False

        async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
            return ["repository"]

    processing_complete = asyncio.Event()
    original_process_data = LiveEventsProcessorManager._extract_matching_processors

    async def patched_extract_matching_processors(
        self: LiveEventsProcessorManager, event: WebhookEvent, path: str
    ) -> list[tuple[ResourceConfig, AbstractWebhookProcessor]]:
        try:
            return await original_process_data(self, event, path)
        except Exception as e:
            test_state["exception_thrown"] = e  # type: ignore
            return []
        finally:
            processing_complete.set()

    monkeypatch.setattr(
        LiveEventsProcessorManager,
        "_extract_matching_processors",
        patched_extract_matching_processors,
    )
    monkeypatch.setattr(
        HandlerMixin,
        "port_app_config_handler",
        AsyncMock(return_value=mock_port_app_config),
    )
    monkeypatch.setattr(
        EventContext,
        "port_app_config",
        mock_port_app_config,
    )
    test_path = "/webhook-test"
    mock_context.app.integration = BaseIntegration(ocean)
    mock_context.app.webhook_manager = LiveEventsProcessorManager(
        mock_context.app.integration_router,
        SignalHandler(),
        3,
        3,
    )

    mock_context.app.webhook_manager.register_processor(test_path, TestProcessor)
    await mock_context.app.webhook_manager.start_processing_event_messages()
    mock_context.app.fast_api_app.include_router(
        mock_context.app.webhook_manager._router
    )
    client = TestClient(mock_context.app.fast_api_app)

    test_payload = {"test": "data"}
    async with event_context(EventType.HTTP_REQUEST, trigger_type="request"):
        response = client.post(
            test_path, json=test_payload, headers={"Content-Type": "application/json"}
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    try:
        await asyncio.wait_for(processing_complete.wait(), timeout=10.0)
    except asyncio.TimeoutError:
        pytest.fail("Event processing timed out")

    assert (
        isinstance(test_state["exception_thrown"], WebhookEventNotSupportedError)
        is True
    )

    mock_upsert.assert_not_called()
    mock_delete.assert_not_called()

    await mock_context.app.webhook_manager.shutdown()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.handlers.entities_state_applier.port.applier.HttpEntitiesStateApplier.upsert"
)
@patch(
    "port_ocean.core.handlers.entities_state_applier.port.applier.HttpEntitiesStateApplier.delete"
)
async def test_integrationTest_postRequestSent_webhookEventRawResultProcessedForMultipleProcessors_entitiesUpserted(
    mock_delete: AsyncMock,
    mock_upsert: AsyncMock,
    mock_context: PortOceanContext,
    mock_port_app_config: PortAppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integration test for the complete webhook processing flow"""

    monkeypatch.setattr(
        "port_ocean.core.integrations.mixins.handler.ocean", mock_context
    )
    monkeypatch.setattr(
        "port_ocean.core.integrations.mixins.live_events.ocean", mock_context
    )
    processed_events: list[WebhookEventRawResults] = []
    mock_upsert.return_value = [entity]

    class TestProcessorA(AbstractWebhookProcessor):
        async def authenticate(
            self, payload: Dict[str, Any], headers: Dict[str, str]
        ) -> bool:
            return True

        async def validate_payload(self, payload: Dict[str, Any]) -> bool:
            return True

        async def handle_event(
            self, payload: EventPayload, resource: ResourceConfig
        ) -> WebhookEventRawResults:
            event_data = WebhookEventRawResults(
                updated_raw_results=[
                    {
                        "name": "repo-one",
                        "links": {"html": {"href": "https://example.com/repo-one"}},
                        "main_branch": "main",
                    }
                ],
                deleted_raw_results=[],
            )
            processed_events.append(event_data)
            return event_data

        async def should_process_event(self, event: WebhookEvent) -> bool:
            return True

        async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
            return ["repository"]

    class TestProcessorB(AbstractWebhookProcessor):
        async def authenticate(
            self, payload: Dict[str, Any], headers: Dict[str, str]
        ) -> bool:
            return True

        async def validate_payload(self, payload: Dict[str, Any]) -> bool:
            return True

        async def handle_event(
            self, payload: EventPayload, resource: ResourceConfig
        ) -> WebhookEventRawResults:
            event_data = WebhookEventRawResults(
                updated_raw_results=[
                    {
                        "name": "repo-two",
                        "links": {"html": {"href": "https://example.com/repo-two"}},
                        "main_branch": "main",
                    }
                ],
                deleted_raw_results=[],
            )
            processed_events.append(event_data)
            return event_data

        async def should_process_event(self, event: WebhookEvent) -> bool:
            return True

        async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
            return ["repository"]

    class TestProcessorFiltersOut(AbstractWebhookProcessor):
        async def authenticate(
            self, payload: Dict[str, Any], headers: Dict[str, str]
        ) -> bool:
            return True

        async def validate_payload(self, payload: Dict[str, Any]) -> bool:
            return True

        async def handle_event(
            self, payload: EventPayload, resource: ResourceConfig
        ) -> WebhookEventRawResults:
            event_data = WebhookEventRawResults(
                updated_raw_results=[
                    {
                        "name": "repo-one",
                        "links": {"html": {"href": "https://example.com/repo-one"}},
                        "main_branch": "main",
                    }
                ],
                deleted_raw_results=[],
            )
            processed_events.append(event_data)
            return event_data

        async def should_process_event(self, event: WebhookEvent) -> bool:
            return False

        async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
            return ["repository"]

    processing_complete = asyncio.Event()
    original_process_data = LiveEventsMixin.sync_raw_results

    async def patched_export_single_resource(
        self: LiveEventsMixin, webhookEventRawResults: list[WebhookEventRawResults]
    ) -> None:
        try:
            await original_process_data(self, webhookEventRawResults)
        except Exception as e:
            raise e
        finally:
            processing_complete.set()

    monkeypatch.setattr(
        LiveEventsMixin,
        "sync_raw_results",
        patched_export_single_resource,
    )
    monkeypatch.setattr(
        HandlerMixin,
        "port_app_config_handler",
        AsyncMock(return_value=mock_port_app_config),
    )
    monkeypatch.setattr(
        EventContext,
        "port_app_config",
        mock_port_app_config,
    )
    test_path = "/webhook-test"
    mock_context.app.integration = BaseIntegration(ocean)
    mock_context.app.webhook_manager = LiveEventsProcessorManager(
        mock_context.app.integration_router,
        SignalHandler(),
        3,
        3,
    )

    mock_context.app.webhook_manager.register_processor(test_path, TestProcessorA)
    mock_context.app.webhook_manager.register_processor(test_path, TestProcessorB)
    mock_context.app.webhook_manager.register_processor(
        test_path, TestProcessorFiltersOut
    )
    await mock_context.app.webhook_manager.start_processing_event_messages()
    mock_context.app.fast_api_app.include_router(
        mock_context.app.webhook_manager._router
    )
    client = TestClient(mock_context.app.fast_api_app)

    test_payload = {"test": "data"}

    async with event_context(EventType.HTTP_REQUEST, trigger_type="request"):
        response = client.post(
            test_path, json=test_payload, headers={"Content-Type": "application/json"}
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    try:
        await asyncio.wait_for(processing_complete.wait(), timeout=10.0)
    except asyncio.TimeoutError:
        pytest.fail("Event processing timed out")

    assert len(processed_events) == 2
    assert mock_upsert.call_count == 1
    mock_delete.assert_not_called()

    await mock_context.app.webhook_manager.shutdown()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.handlers.entities_state_applier.port.applier.HttpEntitiesStateApplier.upsert"
)
@patch(
    "port_ocean.core.handlers.entities_state_applier.port.applier.HttpEntitiesStateApplier.delete"
)
async def test_integrationTest_postRequestSent_webhookEventRawResultProcessedwithRetry_entityUpserted(
    mock_delete: AsyncMock,
    mock_upsert: AsyncMock,
    mock_context: PortOceanContext,
    mock_port_app_config: PortAppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integration test for the complete webhook processing flow"""

    monkeypatch.setattr(
        "port_ocean.core.integrations.mixins.handler.ocean", mock_context
    )
    monkeypatch.setattr(
        "port_ocean.core.integrations.mixins.live_events.ocean", mock_context
    )
    processed_events: list[WebhookEventRawResults] = []
    mock_upsert.return_value = [entity]
    test_state = {"retry": False}

    class TestProcessor(AbstractWebhookProcessor):
        def __init__(self, event: WebhookEvent) -> None:
            super().__init__(event)
            self.tries = 0

        async def authenticate(
            self, payload: Dict[str, Any], headers: Dict[str, str]
        ) -> bool:
            return True

        async def validate_payload(self, payload: Dict[str, Any]) -> bool:
            return True

        async def handle_event(
            self, payload: EventPayload, resource: ResourceConfig
        ) -> WebhookEventRawResults:
            self.tries += 1
            if self.tries < 2:
                test_state["retry"] = True
                raise RetryableError("Test error")
            event_data = WebhookEventRawResults(
                updated_raw_results=[
                    {
                        "name": "repo-one",
                        "links": {"html": {"href": "https://example.com/repo-one"}},
                        "main_branch": "main",
                    }
                ],
                deleted_raw_results=[],
            )
            processed_events.append(event_data)
            return event_data

        async def should_process_event(self, event: WebhookEvent) -> bool:
            return True

        async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
            return ["repository"]

    processing_complete = asyncio.Event()
    original_process_data = LiveEventsMixin.sync_raw_results

    async def patched_export_single_resource(
        self: LiveEventsMixin, webhookEventRawResults: list[WebhookEventRawResults]
    ) -> None:
        try:
            await original_process_data(self, webhookEventRawResults)
        except Exception as e:
            raise e
        finally:
            processing_complete.set()

    monkeypatch.setattr(
        LiveEventsMixin,
        "sync_raw_results",
        patched_export_single_resource,
    )
    monkeypatch.setattr(
        HandlerMixin,
        "port_app_config_handler",
        AsyncMock(return_value=mock_port_app_config),
    )
    monkeypatch.setattr(
        EventContext,
        "port_app_config",
        mock_port_app_config,
    )
    test_path = "/webhook-test"
    mock_context.app.integration = BaseIntegration(ocean)
    mock_context.app.webhook_manager = LiveEventsProcessorManager(
        mock_context.app.integration_router,
        SignalHandler(),
        3,
        3,
    )

    mock_context.app.webhook_manager.register_processor(test_path, TestProcessor)
    await mock_context.app.webhook_manager.start_processing_event_messages()
    mock_context.app.fast_api_app.include_router(
        mock_context.app.webhook_manager._router
    )
    client = TestClient(mock_context.app.fast_api_app)

    test_payload = {"test": "data"}

    async with event_context(EventType.HTTP_REQUEST, trigger_type="request"):
        response = client.post(
            test_path, json=test_payload, headers={"Content-Type": "application/json"}
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    try:
        await asyncio.wait_for(processing_complete.wait(), timeout=10.0)
    except asyncio.TimeoutError:
        pytest.fail("Event processing timed out")

    assert len(processed_events) == 1
    assert test_state["retry"] is True
    mock_upsert.assert_called_once()
    mock_delete.assert_not_called()

    await mock_context.app.webhook_manager.shutdown()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.handlers.entities_state_applier.port.applier.HttpEntitiesStateApplier.upsert"
)
@patch(
    "port_ocean.core.handlers.entities_state_applier.port.applier.HttpEntitiesStateApplier.delete"
)
async def test_integrationTest_postRequestSent_webhookEventRawResultProcessedwithRetry_exceededMaxRetries_entityNotUpserted(
    mock_delete: AsyncMock,
    mock_upsert: AsyncMock,
    mock_context: PortOceanContext,
    mock_port_app_config: PortAppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integration test for the complete webhook processing flow"""

    monkeypatch.setattr(
        "port_ocean.core.integrations.mixins.handler.ocean", mock_context
    )
    monkeypatch.setattr(
        "port_ocean.core.integrations.mixins.live_events.ocean", mock_context
    )
    processed_events: list[WebhookEventRawResults] = []
    mock_upsert.return_value = [entity]
    test_state = {"retry": False, "exception": False}

    class TestProcessor(AbstractWebhookProcessor):
        def __init__(self, event: WebhookEvent) -> None:
            super().__init__(event)
            self.tries = 0

        async def authenticate(
            self, payload: Dict[str, Any], headers: Dict[str, str]
        ) -> bool:
            return True

        async def validate_payload(self, payload: Dict[str, Any]) -> bool:
            return True

        async def handle_event(
            self, payload: EventPayload, resource: ResourceConfig
        ) -> WebhookEventRawResults:
            self.tries += 1
            if self.tries < 5:
                test_state["retry"] = True
                raise RetryableError("Test error")
            event_data = WebhookEventRawResults(
                updated_raw_results=[
                    {
                        "name": "repo-one",
                        "links": {"html": {"href": "https://example.com/repo-one"}},
                        "main_branch": "main",
                    }
                ],
                deleted_raw_results=[],
            )
            processed_events.append(event_data)
            return event_data

        async def should_process_event(self, event: WebhookEvent) -> bool:
            return True

        async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
            return ["repository"]

    processing_complete = asyncio.Event()
    original_process_data = LiveEventsProcessorManager._process_webhook_request

    async def patched_process_webhook_request(
        self: LiveEventsProcessorManager,
        processor: AbstractWebhookProcessor,
        resource: ResourceConfig,
    ) -> WebhookEventRawResults:
        try:
            return await original_process_data(self, processor, resource)
        except Exception as e:
            test_state["exception"] = True
            raise e
        finally:
            processing_complete.set()

    monkeypatch.setattr(
        LiveEventsProcessorManager,
        "_process_webhook_request",
        patched_process_webhook_request,
    )
    monkeypatch.setattr(
        HandlerMixin,
        "port_app_config_handler",
        AsyncMock(return_value=mock_port_app_config),
    )
    monkeypatch.setattr(
        EventContext,
        "port_app_config",
        mock_port_app_config,
    )
    test_path = "/webhook-test"
    mock_context.app.integration = BaseIntegration(ocean)
    mock_context.app.webhook_manager = LiveEventsProcessorManager(
        mock_context.app.integration_router,
        SignalHandler(),
        90.0,
        5.0,
    )

    mock_context.app.webhook_manager.register_processor(test_path, TestProcessor)
    await mock_context.app.webhook_manager.start_processing_event_messages()
    mock_context.app.fast_api_app.include_router(
        mock_context.app.webhook_manager._router
    )
    client = TestClient(mock_context.app.fast_api_app)

    test_payload = {"test": "data"}

    async with event_context(EventType.HTTP_REQUEST, trigger_type="request"):
        response = client.post(
            test_path, json=test_payload, headers={"Content-Type": "application/json"}
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    try:
        await asyncio.wait_for(processing_complete.wait(), timeout=30.0)
    except asyncio.TimeoutError:
        pytest.fail("Event processing timed out")

    assert len(processed_events) == 0
    assert test_state["retry"] is True
    assert test_state["exception"] is True
    mock_upsert.assert_not_called()
    mock_delete.assert_not_called()

    await mock_context.app.webhook_manager.shutdown()


@pytest.mark.asyncio
@patch(
    "port_ocean.core.handlers.entities_state_applier.port.applier.HttpEntitiesStateApplier.upsert"
)
@patch(
    "port_ocean.core.handlers.entities_state_applier.port.applier.HttpEntitiesStateApplier.delete"
)
async def test_integrationTest_postRequestSent_oneProcessorThrowsException_onlySuccessfulResultsProcessed(
    mock_delete: AsyncMock,
    mock_upsert: AsyncMock,
    mock_context: PortOceanContext,
    mock_port_app_config: PortAppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integration test for webhook processing where one processor throws an exception"""

    monkeypatch.setattr(
        "port_ocean.core.integrations.mixins.handler.ocean", mock_context
    )
    monkeypatch.setattr(
        "port_ocean.core.integrations.mixins.live_events.ocean", mock_context
    )
    processed_events: list[WebhookEventRawResults] = []
    mock_upsert.return_value = [entity]

    class SuccessfulProcessor(AbstractWebhookProcessor):
        async def authenticate(
            self, payload: Dict[str, Any], headers: Dict[str, str]
        ) -> bool:
            return True

        async def validate_payload(self, payload: Dict[str, Any]) -> bool:
            return True

        async def handle_event(
            self, payload: EventPayload, resource: ResourceConfig
        ) -> WebhookEventRawResults:
            event_data = WebhookEventRawResults(
                updated_raw_results=[
                    {
                        "name": "repo-one",
                        "links": {"html": {"href": "https://example.com/repo-one"}},
                        "main_branch": "main",
                    }
                ],
                deleted_raw_results=[],
            )
            processed_events.append(event_data)
            return event_data

        async def should_process_event(self, event: WebhookEvent) -> bool:
            return True

        async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
            return ["repository"]

    class FailingProcessor(AbstractWebhookProcessor):
        async def authenticate(
            self, payload: Dict[str, Any], headers: Dict[str, str]
        ) -> bool:
            return True

        async def validate_payload(self, payload: Dict[str, Any]) -> bool:
            return True

        async def handle_event(
            self, payload: EventPayload, resource: ResourceConfig
        ) -> WebhookEventRawResults:
            raise ValueError("Simulated failure in processor")

        async def should_process_event(self, event: WebhookEvent) -> bool:
            return True

        async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
            return ["repository"]

    processing_complete = asyncio.Event()
    original_process_data = LiveEventsMixin.sync_raw_results

    async def patched_export_single_resource(
        self: LiveEventsMixin, webhookEventRawResults: list[WebhookEventRawResults]
    ) -> None:
        try:
            await original_process_data(self, webhookEventRawResults)
        except Exception as e:
            raise e
        finally:
            processing_complete.set()

    monkeypatch.setattr(
        LiveEventsMixin,
        "sync_raw_results",
        patched_export_single_resource,
    )
    monkeypatch.setattr(
        HandlerMixin,
        "port_app_config_handler",
        AsyncMock(return_value=mock_port_app_config),
    )
    monkeypatch.setattr(
        EventContext,
        "port_app_config",
        mock_port_app_config,
    )
    test_path = "/webhook-test"
    mock_context.app.integration = BaseIntegration(ocean)
    mock_context.app.webhook_manager = LiveEventsProcessorManager(
        mock_context.app.integration_router,
        SignalHandler(),
        3,
        3,
    )

    # Register both processors
    mock_context.app.webhook_manager.register_processor(test_path, SuccessfulProcessor)
    mock_context.app.webhook_manager.register_processor(test_path, FailingProcessor)
    await mock_context.app.webhook_manager.start_processing_event_messages()
    mock_context.app.fast_api_app.include_router(
        mock_context.app.webhook_manager._router
    )
    client = TestClient(mock_context.app.fast_api_app)

    test_payload = {"test": "data"}

    async with event_context(EventType.HTTP_REQUEST, trigger_type="request"):
        response = client.post(
            test_path, json=test_payload, headers={"Content-Type": "application/json"}
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    try:
        await asyncio.wait_for(processing_complete.wait(), timeout=10.0)
    except asyncio.TimeoutError:
        pytest.fail("Event processing timed out")

    assert len(processed_events) == 1
    assert mock_upsert.call_count == 1
    mock_delete.assert_not_called()

    await mock_context.app.webhook_manager.shutdown()
