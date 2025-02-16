#     @pytest.mark.skip(reason="Temporarily ignoring this test")
#     async def test_handler_cancellation(
#         self,
#         processor_manager: TestableWebhookProcessorManager,
#         mock_event: WebhookEvent,
#     ) -> None:
#         """Test processor cancellation during shutdown."""
#         cancelled_events: list[WebhookEvent] = []

#         class CanceledHandler(MockWebhookProcessor):
#             async def handle_event(self, payload: Dict[str, Any]) -> None:
#                 await asyncio.sleep(0.2)

#             async def cancel(self) -> None:
#                 cancelled_events.append(self.event)
#                 self.event.payload["canceled"] = True

#         processor_manager.register_processor("/test", CanceledHandler)
#         await processor_manager.start_processing_event_messages()
#         await processor_manager._event_queues["/test"].put(mock_event)

#         await asyncio.sleep(0.1)

#         # Wait for the event to be processed
#         await processor_manager._cancel_all_tasks()

#         # Verify at least one event was cancelled
#         assert len(cancelled_events) > 0
#         assert any(event.payload.get("canceled") for event in cancelled_events)

#     @pytest.mark.skip(reason="Temporarily ignoring this test")
#     async def test_invalid_handler_registration(self) -> None:
#         """Test registration of invalid processor type."""
#         handler_manager = WebhookProcessorManager(APIRouter(), SignalHandler())

#         with pytest.raises(ValueError):
#             handler_manager.register_processor("/test", object)  # type: ignore

#     async def test_no_matching_handlers(
#         self,
#         processor_manager: TestableWebhookProcessorManager,
#         mock_event: WebhookEvent,
#     ) -> None:
#         """Test behavior when no processors match the event."""
#         processor_manager.register_processor(
#             "/test", MockWebhookProcessor, lambda e: False
#         )

#         await processor_manager.start_processing_event_messages()
#         await processor_manager._event_queues["/test"].put(mock_event)

#         await asyncio.sleep(0.1)

#         assert processor_manager.no_matching_processors
#         assert len(processor_manager.running_processors) == 0

#     @pytest.mark.skip(reason="Temporarily ignoring this test")
#     async def test_multiple_processors(
#         self, processor_manager: TestableWebhookProcessorManager
#     ) -> None:
#         # Test multiple processors for same path
#         processor_manager.register_processor("/test", MockWebhookProcessor)
#         processor_manager.register_processor("/test", MockWebhookProcessor)
#         assert len(processor_manager._processors["/test"]) == 2

#     @pytest.mark.skip(reason="Temporarily ignoring this test")
#     async def test_all_matching_processors_execute(
#         self,
#         processor_manager: TestableWebhookProcessorManager,
#         mock_event: WebhookEvent,
#     ) -> None:
#         """Test that all matching processors are executed even if some fail."""
#         processed_count = 0

#         class SuccessProcessor(MockWebhookProcessor):
#             async def handle_event(self, payload: Dict[str, Any]) -> None:
#                 nonlocal processed_count
#                 processed_count += 1
#                 self.processed = True

#         class FailingProcessor(MockWebhookProcessor):
#             async def handle_event(self, payload: Dict[str, Any]) -> None:
#                 raise Exception("Simulated failure")

#         # Register mix of successful and failing processors
#         processor_manager.register_processor("/test", SuccessProcessor)
#         processor_manager.register_processor("/test", FailingProcessor)
#         processor_manager.register_processor("/test", SuccessProcessor)

#         await processor_manager.start_processing_event_messages()
#         await processor_manager._event_queues["/test"].put(mock_event)

#         # Wait for processing to complete
#         await asyncio.sleep(0.1)

#         # Verify successful processors ran despite failing one
#         assert processed_count == 2

#     @pytest.mark.skip(reason="Temporarily ignoring this test")
#     async def test_retry_mechanism(
#         self,
#         processor_manager: TestableWebhookProcessorManager,
#         mock_event: WebhookEvent,
#     ) -> None:
#         """Test retry mechanism with temporary failures."""
#         processor = MockWebhookProcessor(mock_event)
#         processor.error_to_raise = RetryableError("Temporary failure")

#         # Simulate 2 failures before success
#         async def handle_event(payload: Dict[str, Any]) -> None:
#             if processor.retry_count < 2:
#                 raise RetryableError("Temporary failure")
#             processor.processed = True

#         processor.handle_event = handle_event  # type: ignore

#         await processor_manager._process_webhook_request(processor)

#         assert processor.processed
#         assert processor.retry_count == 2

#     @pytest.mark.skip(reason="Temporarily ignoring this test")
#     async def test_max_retries_exceeded(
#         self,
#         processor_manager: TestableWebhookProcessorManager,
#         mock_event: WebhookEvent,
#     ) -> None:
#         """Test behavior when max retries are exceeded."""
#         processor = MockWebhookProcessor(mock_event)
#         processor.max_retries = 1
#         processor.error_to_raise = RetryableError("Temporary failure")

#         with pytest.raises(RetryableError):
#             await processor_manager._process_webhook_request(processor)

#         assert processor.retry_count == processor.max_retries

import pytest
from port_ocean.core.handlers.webhook.processor_manager import WebhookProcessorManager
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventData,
    EventPayload,
)
from fastapi import APIRouter
from port_ocean.utils.signal import SignalHandler
from typing import Dict, Any
import asyncio
from fastapi.testclient import TestClient
from fastapi import FastAPI
from port_ocean.context.ocean import PortOceanContext
from unittest.mock import AsyncMock
from port_ocean.context.event import event_context, EventType
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
from port_ocean.exceptions.webhook_processor import RetryableError
from port_ocean.core.handlers.queue import LocalQueue


class MockProcessor(AbstractWebhookProcessor):
    async def authenticate(
        self, payload: Dict[str, Any], headers: Dict[str, str]
    ) -> bool:
        return True

    async def validate_payload(self, payload: Dict[str, Any]) -> bool:
        return True

    async def handle_event(self, payload: EventPayload) -> WebhookEventData:
        return WebhookEventData(kind="test", data=[{}])

    def filter_event_data(self, event: WebhookEvent) -> bool:
        return True


class MockProcessorFalse(AbstractWebhookProcessor):
    async def authenticate(
        self, payload: Dict[str, Any], headers: Dict[str, str]
    ) -> bool:
        return True

    async def validate_payload(self, payload: Dict[str, Any]) -> bool:
        return True

    async def handle_event(self, payload: EventPayload) -> WebhookEventData:
        return WebhookEventData(kind="test", data=[{}])

    def filter_event_data(self, event: WebhookEvent) -> bool:
        return False


class MockTimeoutProcessor(AbstractWebhookProcessor):
    async def authenticate(
        self, payload: Dict[str, Any], headers: Dict[str, str]
    ) -> bool:
        return True

    async def validate_payload(self, payload: Dict[str, Any]) -> bool:
        return True

    async def handle_event(self, payload: EventPayload) -> WebhookEventData:
        await asyncio.sleep(5)
        return WebhookEventData(kind="test", data=[{}])

    def filter_event_data(self, event: WebhookEvent) -> bool:
        return True


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

    async def handle_event(self, payload: EventPayload) -> WebhookEventData:
        if self.error_to_raise:
            raise self.error_to_raise
        self.processed = True
        return WebhookEventData(kind="test", data=[{}])

    async def cancel(self) -> None:
        self.cancel_called = True

    def filter_event_data(self, event: WebhookEvent) -> bool:
        return True


class RetryableProcessor(MockWebhookProcessor):
    def __init__(self, event: WebhookEvent) -> None:
        super().__init__(event)
        self.attempt_count = 0

    async def authenticate(
        self, payload: Dict[str, Any], headers: Dict[str, str]
    ) -> bool:
        return True

    async def validate_payload(self, payload: Dict[str, Any]) -> bool:
        return True

    async def handle_event(self, payload: EventPayload) -> WebhookEventData:
        self.attempt_count += 1
        if self.attempt_count < 3:  # Succeed on third attempt
            raise RetryableError("Temporary failure")
        self.processed = True
        return WebhookEventData(kind="test", data=[{}])

    def filter_event_data(self, event: WebhookEvent) -> bool:
        return True


@pytest.fixture
def processor_manager() -> WebhookProcessorManager:
    router = APIRouter()
    signal_handler = SignalHandler()
    return WebhookProcessorManager(
        router, signal_handler, max_event_processing_seconds=3
    )


@pytest.fixture
def webhook_event() -> WebhookEvent:
    return WebhookEvent(payload={}, headers={}, trace_id="test-trace")


def test_extractMatchingProcessors_processorMatch(
    processor_manager: WebhookProcessorManager, webhook_event: WebhookEvent
) -> None:
    test_path = "/test"
    processor_manager.register_processor(test_path, MockProcessor)

    processors = processor_manager._extract_matching_processors(
        webhook_event, test_path
    )

    assert len(processors) == 1
    assert isinstance(processors[0], MockProcessor)
    assert processors[0].event != webhook_event
    assert processors[0].event.payload == webhook_event.payload


def test_extractMatchingProcessors_noMatch(
    processor_manager: WebhookProcessorManager, webhook_event: WebhookEvent
) -> None:
    test_path = "/test"
    processor_manager.register_processor(test_path, MockProcessorFalse)

    with pytest.raises(ValueError, match="No matching processors found"):
        processor_manager._extract_matching_processors(webhook_event, test_path)


def test_extractMatchingProcessors_multipleMatches(
    processor_manager: WebhookProcessorManager, webhook_event: WebhookEvent
) -> None:
    test_path = "/test"
    processor_manager.register_processor(test_path, MockProcessor)
    processor_manager.register_processor(test_path, MockProcessor)

    processors = processor_manager._extract_matching_processors(
        webhook_event, test_path
    )

    assert len(processors) == 2
    assert all(isinstance(p, MockProcessor) for p in processors)
    assert all(p.event != webhook_event for p in processors)


def test_registerHandler_registrationWorks(
    processor_manager: WebhookProcessorManager,
) -> None:
    processor_manager.register_processor("/test", MockWebhookProcessor)
    assert "/test" in processor_manager._processors
    assert len(processor_manager._processors["/test"]) == 1
    assert isinstance(processor_manager._event_queues["/test"], LocalQueue)


def test_register_multiple_handlers_with_filters(
    processor_manager: WebhookProcessorManager,
) -> None:
    processor_manager.register_processor("/test", MockWebhookProcessor)
    processor_manager.register_processor("/test", MockWebhookProcessor)

    assert len(processor_manager._processors["/test"]) == 2


async def test_shutdown_ShutsDownAllTasks(
    processor_manager: WebhookProcessorManager,
    webhook_event: WebhookEvent,
    mock_context: PortOceanContext,
) -> None:
    processor_manager.register_processor("/test", MockWebhookProcessor)
    await processor_manager.start_processing_event_messages()
    async with event_context(EventType.HTTP_REQUEST, trigger_type="request") as event:
        await processor_manager._event_queues["/test"].put((webhook_event, event))

    await processor_manager.shutdown()

    assert len(processor_manager._webhook_processor_tasks) == 0


@pytest.mark.asyncio
async def test_process_queue_handlerReachedTimeout_exceptionThrown(
    processor_manager: WebhookProcessorManager,
    webhook_event: WebhookEvent,
    monkeypatch: pytest.MonkeyPatch,
    mock_context: PortOceanContext,
    mock_port_app_config: PortAppConfig,
) -> None:
    """Test processor timeout behavior."""
    processing_complete = asyncio.Event()
    original_process_data = WebhookProcessorManager._execute_processor
    test_state = {"exception_thrown": None}

    async def patched_export_single_resource(
        self: WebhookProcessorManager, processor: AbstractWebhookProcessor
    ) -> WebhookEventData:
        try:
            await original_process_data(self, processor)
        except Exception as e:
            test_state["exception_thrown"] = e  # type: ignore
        finally:
            processing_complete.set()
            return WebhookEventData(kind="test", data=[{}])

    monkeypatch.setattr(
        WebhookProcessorManager, "_execute_processor", patched_export_single_resource
    )

    async with event_context(EventType.HTTP_REQUEST, trigger_type="request") as event:
        processor_manager.register_processor("/test", MockTimeoutProcessor)
        event.port_app_config = mock_port_app_config
        await processor_manager.start_processing_event_messages()
        await processor_manager._event_queues["/test"].put((webhook_event, event))

    await asyncio.wait_for(processing_complete.wait(), timeout=10.0)
    assert isinstance(test_state["exception_thrown"], asyncio.TimeoutError) is True
    await processor_manager.shutdown()


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
@patch(
    "port_ocean.core.handlers.entities_state_applier.port.applier.HttpEntitiesStateApplier.upsert"
)
@patch(
    "port_ocean.core.handlers.entities_state_applier.port.applier.HttpEntitiesStateApplier.delete"
)
async def test_integrationTest_postRequestSent_webhookEventDataProcessed_entityUpserted(
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
    processed_events: list[WebhookEventData] = []
    mock_upsert.return_value = [entity]

    class TestProcessor(AbstractWebhookProcessor):
        async def authenticate(
            self, payload: Dict[str, Any], headers: Dict[str, str]
        ) -> bool:
            return True

        async def validate_payload(self, payload: Dict[str, Any]) -> bool:
            return True

        async def handle_event(self, payload: EventPayload) -> WebhookEventData:
            event_data = WebhookEventData(
                kind="repository",
                data=[
                    {
                        "name": "repo-one",
                        "links": {"html": {"href": "https://example.com/repo-one"}},
                        "main_branch": "main",
                    }
                ],
            )
            processed_events.append(event_data)
            return event_data

        def filter_event_data(self, event: WebhookEvent) -> bool:
            return True

    processing_complete = asyncio.Event()
    original_process_data = LiveEventsMixin.process_data

    async def patched_export_single_resource(
        self: LiveEventsMixin, webhookEventDatas: list[WebhookEventData]
    ) -> None:
        try:
            await original_process_data(self, webhookEventDatas)
        except Exception as e:
            raise e
        finally:
            processing_complete.set()

    monkeypatch.setattr(LiveEventsMixin, "process_data", patched_export_single_resource)
    test_path = "/webhook-test"
    mock_context.app.integration = BaseIntegration(ocean)
    mock_context.app.webhook_manager = WebhookProcessorManager(
        mock_context.app.integration_router, SignalHandler()
    )

    mock_context.app.webhook_manager.register_processor(test_path, TestProcessor)
    await mock_context.app.webhook_manager.start_processing_event_messages()
    mock_context.app.fast_api_app.include_router(
        mock_context.app.webhook_manager._router
    )
    client = TestClient(mock_context.app.fast_api_app)

    test_payload = {"test": "data"}

    async with event_context(EventType.HTTP_REQUEST, trigger_type="request") as event:
        mock_context.app.webhook_manager.port_app_config_handler.get_port_app_config = AsyncMock(return_value=mock_port_app_config)  # type: ignore
        event.port_app_config = (
            await mock_context.app.webhook_manager.port_app_config_handler.get_port_app_config()
        )

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
    assert processed_events[0].kind == "repository"

    mock_upsert.assert_called_once()
    mock_delete.assert_not_called()

    await mock_context.app.webhook_manager.shutdown()
