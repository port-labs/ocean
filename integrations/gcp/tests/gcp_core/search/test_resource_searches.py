from typing import Any
from unittest.mock import AsyncMock, patch

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from google.pubsub_v1.types import pubsub
from google.cloud.resourcemanager_v3.types import Project


async def mock_subscription_pages(
    *args: Any, **kwargs: Any
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    yield [{"name": "subscription_1"}, {"name": "subscription_2"}]  # First page
    yield [{"name": "subscription_3"}, {"name": "subscription_4"}]  # Second page


@patch(
    "port_ocean.context.ocean.PortOceanContext.integration_config",
    return_value={"search_all_resources_per_minute_quota": 100},
)
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


@patch(
    "port_ocean.context.ocean.PortOceanContext.integration_config",
    return_value={"search_all_resources_per_minute_quota": 100},
)
async def test_get_single_subscription(
    integration_config: Any, monkeypatch: Any
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
    mock_project = "project_name"

    # Act
    actual_subscription = await get_single_subscription(
        mock_project, "subscription_name"
    )

    # Assert
    assert actual_subscription == expected_subscription


@patch(
    "port_ocean.context.ocean.PortOceanContext.integration_config",
    return_value={"search_all_resources_per_minute_quota": 100},
)
async def test_feed_to_resource(integration_config: Any, monkeypatch: Any) -> None:
    # Arrange

    ## Mock project client
    projects_async_client_mock = AsyncMock
    monkeypatch.setattr(
        "google.cloud.resourcemanager_v3.ProjectsAsyncClient",
        projects_async_client_mock,
    )
    projects_async_client_mock.get_project = AsyncMock()
    projects_async_client_mock.get_project.return_value = Project(
        {"name": "project_name"}
    )

    ## Mock publisher client
    publisher_async_client_mock = AsyncMock
    monkeypatch.setattr(
        "google.pubsub_v1.services.publisher.PublisherAsyncClient",
        publisher_async_client_mock,
    )
    publisher_async_client_mock.get_topic = AsyncMock()
    publisher_async_client_mock.get_topic.return_value = pubsub.Topic(
        {"name": "topic_name"}
    )

    from gcp_core.search.resource_searches import feed_event_to_resource

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

    # Act
    actual_resource = await feed_event_to_resource(
        asset_type=mock_asset_type,
        asset_name=mock_asset_name,
        project_id=mock_asset_project_name,
        asset_data=mock_asset_data,
    )

    # Assert
    assert actual_resource == expected_resource
