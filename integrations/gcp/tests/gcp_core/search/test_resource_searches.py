from typing import Any
from unittest.mock import patch

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from google.pubsub_v1.types import pubsub


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
async def test_list_all_subscriptions_per_project(integration_config: Any) -> None:
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
@patch(
    "google.pubsub_v1.services.subscriber.SubscriberAsyncClient.get_subscription",
    return_value=pubsub.Subscription({"name": "subscription_name"}),
)
async def test_get_single_subscription(
    integration_config: Any, subscription_mock: Any
) -> None:
    # Arrange
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
