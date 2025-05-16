import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from newrelic_integration.webhook.processors.issue_webhook_processor import (
    IssueWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    ResourceConfig,
    Selector,
    PortResourceConfig,
)
from newrelic_integration.core.entities import EntitiesHandler
from newrelic_integration.core.issues import IssuesHandler
import base64
from port_ocean.context.ocean import (
    initialize_port_ocean_context,
)

from port_ocean.context.ocean import PortOceanContextAlreadyInitializedError  # type: ignore


# Fixtures
@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to initialize the PortOcean context."""
    mock_app = MagicMock()
    mock_app.integration_config = {
        "webhook_secret": "test_secret",
        "new_relic_account_id": "123",
    }
    try:
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        # Context already initialized, ignore
        pass
    return None


@pytest.fixture
def mock_event() -> WebhookEvent:
    return WebhookEvent(
        trace_id="test-trace-id",
        payload={"id": "test-issue-id", "title": "Test Issue", "state": "OPEN"},
        headers={},
    )


@pytest.fixture
def mock_event_with_auth() -> WebhookEvent:
    encoded_secret = base64.b64encode(b":test_secret").decode("utf-8")
    headers = {"authorization": f"Basic {encoded_secret}"}
    return WebhookEvent(trace_id="auth-trace-id", payload={}, headers=headers)


@pytest.fixture
def mock_event_with_guids() -> WebhookEvent:
    payload = {
        "id": "guid-issue-id",
        "title": "Guid Issue",
        "state": "CLOSED",
        "entityGuids": ["guid1", "guid2"],
    }
    return WebhookEvent(trace_id="guid-trace-id", payload=payload, headers={})


@pytest.fixture
def issue_processor(mock_event: WebhookEvent) -> IssueWebhookProcessor:
    return IssueWebhookProcessor(mock_event)


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind="newRelicAlert",
        selector=Selector(query="test"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".title",
                    blueprint='"newRelicAlert"',
                    properties={},
                    relations={},
                )
            )
        ),
    )


@pytest.fixture
def mock_http_client() -> AsyncMock:
    return AsyncMock()


@pytest.mark.asyncio
async def test_issue_get_matching_kinds(issue_processor: IssueWebhookProcessor) -> None:
    dummy_event = WebhookEvent(trace_id="dummy", payload={}, headers={})
    assert await issue_processor.get_matching_kinds(dummy_event) == ["newRelicAlert"]


@pytest.mark.asyncio
async def test_should_process_event_no_secret_no_auth(
    issue_processor: IssueWebhookProcessor, mock_event: WebhookEvent
) -> None:
    """Test processing when no webhook secret is configured."""
    mock_app = MagicMock()
    mock_app.integration_config = {}
    assert await issue_processor.should_process_event(mock_event) is True


@pytest.mark.asyncio
async def test_should_process_event_with_secret_no_auth(
    issue_processor: IssueWebhookProcessor, mock_event: WebhookEvent
) -> None:
    assert await issue_processor.should_process_event(mock_event) is True


@pytest.mark.asyncio
async def test_should_process_event_with_secret_invalid_auth_format(
    issue_processor: IssueWebhookProcessor, mock_event: WebhookEvent
) -> None:
    mock_event.headers = {"authorization": "Invalid Basic test"}
    assert await issue_processor.should_process_event(mock_event) is False


@pytest.mark.asyncio
async def test_should_process_event_with_secret_valid_auth(
    issue_processor: IssueWebhookProcessor, mock_event_with_auth: WebhookEvent
) -> None:
    assert await issue_processor.should_process_event(mock_event_with_auth) is False


@pytest.mark.asyncio
async def test_handle_event_without_existing_guids(
    issue_processor: IssueWebhookProcessor,
    resource_config: ResourceConfig,
    mock_http_client: AsyncMock,
) -> None:
    mock_webhook_manager = AsyncMock(spec=IssuesHandler)
    mock_webhook_manager.get_issue_entity_guids.return_value = ["guid123", "guid456"]

    mock_entities_handler = AsyncMock(spec=EntitiesHandler)
    mock_entities_handler.get_entity.side_effect = [
        {"type": "INFRASTRUCTURE", "name": "Server A"},
        {"type": "APPLICATION", "name": "WebApp B"},
    ]

    with (
        patch(
            "newrelic_integration.webhook.processors.issue_webhook_processor.IssuesHandler",
            return_value=mock_webhook_manager,
        ),
        patch(
            "newrelic_integration.webhook.processors.issue_webhook_processor.EntitiesHandler",
            return_value=mock_entities_handler,
        ),
    ):
        result = await issue_processor.handle_event(
            {"id": "test-issue-id", "title": "Test Issue", "state": "OPEN"},
            resource_config,
        )

        mock_webhook_manager.get_issue_entity_guids.assert_awaited_once_with(
            "test-issue-id"
        )
        assert len(result.updated_raw_results) == 1
        expected_record = {
            "id": "test-issue-id",
            "title": "Test Issue",
            "state": "OPEN",
            "entityGuids": ["guid123", "guid456"],
            "__INFRASTRUCTURE": {"entity_guids": ["guid123"]},
            "__APPLICATION": {"entity_guids": ["guid456"]},
        }
        assert result.updated_raw_results[0] == expected_record
        assert mock_entities_handler.get_entity.call_count == 2


@pytest.mark.asyncio
async def test_handle_event_with_existing_guids(
    issue_processor: IssueWebhookProcessor,
    resource_config: ResourceConfig,
    mock_http_client: AsyncMock,
    mock_event_with_guids: WebhookEvent,
) -> None:
    mock_webhook_manager = AsyncMock(spec=IssuesHandler)
    mock_webhook_manager.get_issue_entity_guids.return_value = [
        "guid123",
        "guid456",
    ]  # Should not be called

    mock_entities_handler = AsyncMock(spec=EntitiesHandler)
    mock_entities_handler.get_entity.side_effect = [
        {"type": "INFRASTRUCTURE", "name": "Server A"},
        {"type": "APPLICATION", "name": "WebApp B"},
    ]

    processor_with_guids = IssueWebhookProcessor(mock_event_with_guids)

    with (
        patch(
            "newrelic_integration.webhook.processors.issue_webhook_processor.IssuesHandler",
            return_value=mock_webhook_manager,
        ),
        patch(
            "newrelic_integration.webhook.processors.issue_webhook_processor.EntitiesHandler",
            return_value=mock_entities_handler,
        ),
    ):
        result = await processor_with_guids.handle_event(
            mock_event_with_guids.payload,
            resource_config,
        )

        mock_webhook_manager.get_issue_entity_guids.assert_not_awaited()
        assert len(result.updated_raw_results) == 1
        expected_record = {
            "id": "guid-issue-id",
            "title": "Guid Issue",
            "state": "CLOSED",
            "entityGuids": ["guid1", "guid2"],
            "__INFRASTRUCTURE": {"entity_guids": ["guid1"]},
            "__APPLICATION": {"entity_guids": ["guid2"]},
        }
        assert result.updated_raw_results[0] == expected_record
        assert mock_entities_handler.get_entity.call_count == 2


@pytest.mark.asyncio
async def test_handle_event_fetch_guids_fails(
    issue_processor: IssueWebhookProcessor,
    resource_config: ResourceConfig,
    mock_http_client: AsyncMock,
) -> None:
    mock_webhook_manager = AsyncMock(spec=IssuesHandler)
    mock_webhook_manager.get_issue_entity_guids.return_value = None

    mock_entities_handler = AsyncMock(spec=EntitiesHandler)

    with (
        patch(
            "newrelic_integration.webhook.processors.issue_webhook_processor.IssuesHandler",
            return_value=mock_webhook_manager,
        ),
        patch(
            "newrelic_integration.webhook.processors.issue_webhook_processor.EntitiesHandler",
            return_value=mock_entities_handler,
        ),
    ):
        result = await issue_processor.handle_event(
            {"id": "test-issue-id", "title": "Test Issue", "state": "OPEN"},
            resource_config,
        )

        mock_webhook_manager.get_issue_entity_guids.assert_awaited_once_with(
            "test-issue-id"
        )
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == {
            "id": "test-issue-id",
            "title": "Test Issue",
            "state": "OPEN",
            "entityGuids": [],
        }
        mock_entities_handler.get_entity.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_event_entity_enrichment_fails(
    issue_processor: IssueWebhookProcessor,
    resource_config: ResourceConfig,
    mock_http_client: AsyncMock,
) -> None:
    mock_webhook_manager = AsyncMock(spec=IssuesHandler)
    mock_webhook_manager.get_issue_entity_guids.return_value = ["guid123"]

    mock_entities_handler = AsyncMock(spec=EntitiesHandler)
    mock_entities_handler.get_entity.side_effect = Exception("Failed to fetch entity")

    with (
        patch(
            "newrelic_integration.webhook.processors.issue_webhook_processor.IssuesHandler",
            return_value=mock_webhook_manager,
        ),
        patch(
            "newrelic_integration.webhook.processors.issue_webhook_processor.EntitiesHandler",
            return_value=mock_entities_handler,
        ),
    ):
        result = await issue_processor.handle_event(
            {"id": "test-issue-id", "title": "Test Issue", "state": "OPEN"},
            resource_config,
        )

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0]["entityGuids"] == ["guid123"]
        assert "__" not in result.updated_raw_results[0]
        mock_entities_handler.get_entity.assert_awaited_once_with("guid123")


@pytest.mark.asyncio
async def test_authenticate(
    issue_processor: IssueWebhookProcessor, mock_event: WebhookEvent
) -> None:
    assert (
        await issue_processor.authenticate(mock_event.payload, mock_event.headers)
        is True
    )


@pytest.mark.asyncio
async def test_validate_payload(
    issue_processor: IssueWebhookProcessor, mock_event: WebhookEvent
) -> None:
    assert await issue_processor.validate_payload(mock_event.payload) is True
