from typing import Any, Generator
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from port_ocean.context.event import event_context
from port_ocean.context.ocean import initialize_port_ocean_context

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from google.pubsub_v1.types import pubsub
from google.cloud.resourcemanager_v3.types import Project
from gcp_core.overrides import (
    ProtoConfig,
)


async def mock_subscription_pages(
    *args: Any, **kwargs: Any
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    yield [{"name": "subscription_1"}, {"name": "subscription_2"}]  # First page
    yield [{"name": "subscription_3"}, {"name": "subscription_4"}]  # Second page


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to initialize the PortOcean context."""
    mock_app = MagicMock()
    mock_app.config.integration.config = {"search_all_resources_per_minute_quota": 100}
    mock_app.cache_provider = AsyncMock()
    mock_app.cache_provider.get.return_value = None
    initialize_port_ocean_context(mock_app)


@pytest.fixture
def integration_config_mock() -> Generator[Any, Any, Any]:
    """Fixture to mock integration configuration."""
    with patch(
        "port_ocean.context.ocean.PortOceanContext.integration_config",
        new_callable=MagicMock,
    ) as mock:
        yield mock


@pytest.mark.asyncio
@patch("gcp_core.search.paginated_query.paginated_query", new=mock_subscription_pages)
@patch("google.pubsub_v1.services.subscriber.SubscriberAsyncClient", new=AsyncMock)
async def test_list_all_subscriptions_per_project(integration_config_mock: Any) -> None:
    # Arrange
    from gcp_core.search.resource_searches import list_all_subscriptions_per_project

    expected_subscriptions = [
        {"__project": {"name": "project_name"}, "name": "subscription_1"},
        {"__project": {"name": "project_name"}, "name": "subscription_2"},
        {"__project": {"name": "project_name"}, "name": "subscription_3"},
        {"__project": {"name": "project_name"}, "name": "subscription_4"},
    ]
    mock_project = {"name": "project_name"}

    # Act
    actual_subscriptions = []
    async for file in list_all_subscriptions_per_project(mock_project):
        actual_subscriptions.extend(file)

    # Assert
    assert len(actual_subscriptions) == 4
    assert actual_subscriptions == expected_subscriptions


@pytest.mark.asyncio
@patch("gcp_core.utils.get_current_resource_config")
async def test_get_single_subscription(
    get_current_resource_config_mock: MagicMock, monkeypatch: Any
) -> None:
    # Arrange
    subscriber_async_client_mock = AsyncMock
    monkeypatch.setattr(
        "google.pubsub_v1.services.subscriber.SubscriberAsyncClient",
        subscriber_async_client_mock,
    )
    subscriber_async_client_mock.get_subscription = AsyncMock()
    subscriber_async_client_mock.get_subscription.return_value = pubsub.Subscription(
        {"name": "subscription_name"}
    )

    # Mock the resource config
    mock_resource_config = MagicMock()
    mock_resource_config.selector = MagicMock(preserve_api_response_case_style=False)
    get_current_resource_config_mock.return_value = mock_resource_config

    from gcp_core.search.resource_searches import get_single_subscription

    expected_subscription = {
        "ack_deadline_seconds": 0,
        "detached": False,
        "enable_exactly_once_delivery": False,
        "enable_message_ordering": False,
        "filter": "",
        "labels": {},
        "name": "subscription_name",
        "retain_acked_messages": False,
        "state": 0,
        "topic": "",
    }

    # Act within event context
    async with event_context("test_event"):
        config = ProtoConfig(
            preserving_proto_field_name=mock_resource_config.selector.preserve_api_response_case_style
        )
        actual_subscription = await get_single_subscription("subscription_name", config)

    # Assert
    assert actual_subscription == expected_subscription


@pytest.mark.asyncio
@patch("gcp_core.utils.get_current_resource_config")
async def test_feed_to_resource(
    get_current_resource_config_mock: MagicMock,
    monkeypatch: Any,
) -> None:
    # Arrange
    projects_async_client_mock = AsyncMock
    monkeypatch.setattr(
        "google.cloud.resourcemanager_v3.ProjectsAsyncClient",
        projects_async_client_mock,
    )
    projects_async_client_mock.get_project = AsyncMock()
    projects_async_client_mock.get_project.return_value = Project(
        {"name": "project_name"}
    )

    publisher_async_client_mock = AsyncMock
    monkeypatch.setattr(
        "google.pubsub_v1.services.publisher.PublisherAsyncClient",
        publisher_async_client_mock,
    )
    publisher_async_client_mock.get_topic = AsyncMock()
    publisher_async_client_mock.get_topic.return_value = pubsub.Topic(
        {"name": "topic_name"}
    )

    # Mock the resource config
    mock_resource_config = MagicMock()
    mock_resource_config.selector = MagicMock(preserve_api_response_case_style=False)
    get_current_resource_config_mock.return_value = mock_resource_config

    from gcp_core.search.resource_searches import feed_event_to_resource

    # Mock resolve_request_controllers
    mock_rate_limiter = AsyncMock()

    mock_asset_name = "projects/project_name/topics/topic_name"
    mock_asset_type = "pubsub.googleapis.com/Topic"
    mock_asset_project_name = "project_name"
    mock_asset_data = {
        "asset": {
            "name": mock_asset_name,
            "asset_type": mock_asset_type,
        },
        "event": "google.cloud.audit.log.v1.written",
        "project": "project_name",
    }

    expected_resource = {
        "__project": {
            "display_name": "",
            "etag": "",
            "labels": {},
            "name": "project_name",
            "parent": "",
            "project_id": "",
            "state": 0,
        },
        "kms_key_name": "",
        "labels": {},
        "name": "topic_name",
        "satisfies_pzs": False,
        "state": 0,
    }

    # Act within event context
    async with event_context("test_event"):
        config = ProtoConfig(
            preserving_proto_field_name=mock_resource_config.selector.preserve_api_response_case_style
        )
        actual_resource = await feed_event_to_resource(
            asset_type=mock_asset_type,
            asset_name=mock_asset_name,
            project_rate_limiter=mock_rate_limiter,
            project_id=mock_asset_project_name,
            asset_data=mock_asset_data,
            config=config,
            project_semaphore=AsyncMock(),
        )

    # Assert
    assert actual_resource == expected_resource


@pytest.mark.asyncio
@patch("gcp_core.utils.get_current_resource_config")
async def test_preserve_case_style_combined(
    get_current_resource_config_mock: MagicMock, monkeypatch: Any
) -> None:
    # Arrange
    subscriber_async_client_mock = AsyncMock
    monkeypatch.setattr(
        "google.pubsub_v1.services.subscriber.SubscriberAsyncClient",
        subscriber_async_client_mock,
    )
    subscriber_async_client_mock.get_subscription = AsyncMock()

    # Mock for preserve_case_style = True
    subscriber_async_client_mock.get_subscription.return_value = pubsub.Subscription(
        {
            "name": "subscription_name",
            "topic": "projects/project_name/topics/topic_name",
            "ack_deadline_seconds": 0,
            "retain_acked_messages": False,
            "labels": {},
            "enable_message_ordering": False,
            "filter": "",
            "detached": False,
            "enable_exactly_once_delivery": False,
            "state": 0,
        }
    )

    # Mock the resource config with preserve_api_response_case_style set to True
    mock_resource_config_true = MagicMock()
    mock_resource_config_true.selector = MagicMock(
        preserve_api_response_case_style=True
    )
    get_current_resource_config_mock.return_value = mock_resource_config_true

    from gcp_core.search.resource_searches import get_single_subscription

    expected_subscription_true = {
        "ackDeadlineSeconds": 0,
        "detached": False,
        "enableExactlyOnceDelivery": False,
        "enableMessageOrdering": False,
        "filter": "",
        "labels": {},
        "name": "subscription_name",
        "retainAckedMessages": False,
        "state": 0,
        "topic": "projects/project_name/topics/topic_name",
    }

    # Act within event context for preserve_case_style = True
    async with event_context("test_event"):
        config = ProtoConfig(
            preserving_proto_field_name=mock_resource_config_true.selector.preserve_api_response_case_style
        )
        actual_subscription_true = await get_single_subscription(
            "subscription_name", config
        )

    # Assert for preserve_case_style = True
    assert actual_subscription_true == expected_subscription_true

    # Mock for preserve_case_style = False
    mock_resource_config_false = MagicMock()
    mock_resource_config_false.selector = MagicMock(
        preserve_api_response_case_style=False
    )
    get_current_resource_config_mock.return_value = mock_resource_config_false

    expected_subscription_false = {
        "ack_deadline_seconds": 0,
        "detached": False,
        "enable_exactly_once_delivery": False,
        "enable_message_ordering": False,
        "filter": "",
        "labels": {},
        "name": "subscription_name",
        "retain_acked_messages": False,
        "state": 0,
        "topic": "projects/project_name/topics/topic_name",
    }

    # Act within event context for preserve_case_style = False
    async with event_context("test_event"):
        config = ProtoConfig(
            preserving_proto_field_name=mock_resource_config_false.selector.preserve_api_response_case_style
        )
        actual_subscription_false = await get_single_subscription(
            "subscription_name", config
        )

    # Assert for preserve_case_style = False
    assert actual_subscription_false == expected_subscription_false
