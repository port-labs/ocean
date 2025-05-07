import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Dict, Any, cast
from newrelic_integration.webhook.webhook_manager import NewRelicWebhookManager


@pytest.fixture
def http_client() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def manager(http_client: AsyncMock) -> NewRelicWebhookManager:
    return NewRelicWebhookManager(http_client=http_client)


@pytest.fixture
def integration_config_mock() -> Dict[str, Any]:
    return {"new_relic_account_id": "123456", "webhook_secret": "supersecret"}


@pytest.fixture
def ocean_mock(integration_config_mock: Dict[str, Any]) -> MagicMock:
    mock = MagicMock()
    mock.integration_config = integration_config_mock
    mock.app.base_url = "https://port.app"
    return mock


@pytest.mark.asyncio
async def test_get_existing_webhooks_returns_id_if_found(ocean_mock: MagicMock) -> None:
    mock_http_client = MagicMock()
    manager = NewRelicWebhookManager(http_client=mock_http_client)

    ocean_mock.integration_config = {"new_relic_account_id": "123456"}

    with (
        patch("newrelic_integration.webhook.webhook_manager.ocean", ocean_mock),
        patch(
            "newrelic_integration.webhook.webhook_manager.send_graph_api_request",
            new=AsyncMock(
                return_value={
                    "data": {
                        "actor": {
                            "account": {
                                "aiNotifications": {
                                    "destinations": {
                                        "entities": [
                                            {
                                                "id": "webhook-123",
                                                "type": "WEBHOOK",
                                                "name": "Port - Something",
                                                "active": True,
                                                "properties": [
                                                    {
                                                        "key": "url",
                                                        "value": "https://port.app/integration/webhook",
                                                    }
                                                ],
                                            }
                                        ]
                                    }
                                }
                            }
                        }
                    }
                }
            ),
        ),
    ):
        result = await manager.get_existing_webhooks(
            "https://port.app/integration/webhook"
        )
        assert result == "webhook-123"


@pytest.mark.asyncio
async def test_get_existing_workflows_none(
    manager: NewRelicWebhookManager, ocean_mock: MagicMock
) -> None:
    with (
        patch("newrelic_integration.webhook.webhook_manager.ocean", ocean_mock),
        patch(
            "newrelic_integration.webhook.webhook_manager.render_query", new=AsyncMock()
        ),
        patch(
            "newrelic_integration.webhook.webhook_manager.send_graph_api_request",
            new=AsyncMock(return_value={"data": {}}),
        ),
    ):
        result = await manager.get_existing_workflows("workflow-name")
        assert result is None


@pytest.mark.asyncio
async def test_create_destination_webhook_success(
    manager: NewRelicWebhookManager, ocean_mock: MagicMock
) -> None:
    with (
        patch("newrelic_integration.webhook.webhook_manager.ocean", ocean_mock),
        patch(
            "newrelic_integration.webhook.webhook_manager.render_query",
            new=AsyncMock(return_value="mocked-mutation"),
        ),
        patch(
            "newrelic_integration.webhook.webhook_manager.send_graph_api_request",
            new=AsyncMock(
                return_value={
                    "data": {
                        "aiNotificationsCreateDestination": {
                            "destination": {
                                "id": "webhook-123",
                                "name": "Port - 123456",
                                "type": "WEBHOOK",
                                "properties": [
                                    {
                                        "key": "url",
                                        "value": "https://port.app/integration/webhook",
                                    }
                                ],
                            }
                        }
                    }
                }
            ),
        ),
    ):
        result = cast(
            Dict[str, Any],
            await manager.create_destination_webhook(
                "Port - 123456", "https://port.app/integration/webhook"
            ),
        )
        assert (
            result["data"]["aiNotificationsCreateDestination"]["destination"]["id"]
            == "webhook-123"
        )


@pytest.mark.asyncio
async def test_get_or_create_webhook_create_flow(
    manager: NewRelicWebhookManager, ocean_mock: MagicMock
) -> None:
    with (
        patch("newrelic_integration.webhook.webhook_manager.ocean", ocean_mock),
        patch.object(
            manager, "get_existing_webhooks", new=AsyncMock(return_value=False)
        ),
        patch.object(
            manager,
            "create_destination_webhook",
            new=AsyncMock(
                return_value={
                    "data": {
                        "aiNotificationsCreateDestination": {
                            "destination": {"id": "webhook-xyz"}
                        }
                    }
                }
            ),
        ),
    ):
        webhook_id = await manager.get_or_create_webhook(
            "Port - 123456", "https://port.app/integration/webhook"
        )
        assert webhook_id == "webhook-xyz"


@pytest.mark.asyncio
async def test_create_destination_webhook_failure(
    manager: NewRelicWebhookManager, ocean_mock: MagicMock
) -> None:
    with (
        patch("newrelic_integration.webhook.webhook_manager.ocean", ocean_mock),
        patch(
            "newrelic_integration.webhook.webhook_manager.render_query",
            new=AsyncMock(return_value="mocked-mutation"),
        ),
        patch(
            "newrelic_integration.webhook.webhook_manager.send_graph_api_request",
            new=AsyncMock(
                return_value={
                    "data": {
                        "aiNotificationsCreateDestination": {
                            "error": {
                                "description": "Invalid URL",
                                "details": "URL must be HTTPS",
                                "type": "VALIDATION_ERROR",
                            }
                        }
                    }
                }
            ),
        ),
    ):
        result = cast(
            Dict[str, Any],
            await manager.create_destination_webhook(
                "Port - 123456", "http://insecure.url"
            ),
        )
        assert "error" in result["data"]["aiNotificationsCreateDestination"]


@pytest.mark.asyncio
async def test_create_channel_success(
    manager: NewRelicWebhookManager, ocean_mock: MagicMock
) -> None:
    with (
        patch("newrelic_integration.webhook.webhook_manager.ocean", ocean_mock),
        patch(
            "newrelic_integration.webhook.webhook_manager.render_query",
            new=AsyncMock(return_value="mocked-mutation"),
        ),
        patch(
            "newrelic_integration.webhook.webhook_manager.send_graph_api_request",
            new=AsyncMock(
                return_value={
                    "data": {
                        "aiNotificationsCreateChannel": {
                            "channel": {
                                "id": "new-channel-123",
                                "name": "port-channel",
                                "type": "WEBHOOK",
                            }
                        }
                    }
                }
            ),
        ),
    ):
        result = cast(
            Dict[str, Any],
            await manager.create_channel("123456", "webhook-123", "port-channel"),
        )
        assert (
            result["data"]["aiNotificationsCreateChannel"]["channel"]["id"]
            == "new-channel-123"
        )


@pytest.mark.asyncio
async def test_create_new_channel_success(
    manager: NewRelicWebhookManager, ocean_mock: MagicMock
) -> None:
    with (
        patch("newrelic_integration.webhook.webhook_manager.ocean", ocean_mock),
        patch.object(
            manager,
            "create_channel",
            new=AsyncMock(
                return_value={
                    "data": {
                        "aiNotificationsCreateChannel": {
                            "channel": {"id": "new-channel-id"}
                        }
                    }
                }
            ),
        ),
    ):
        channel_id = await manager.create_new_channel(
            123456, "webhook-123", "port-channel"
        )
        assert channel_id == "new-channel-id"


@pytest.mark.asyncio
async def test_create_workflow_success(
    manager: NewRelicWebhookManager, ocean_mock: MagicMock
) -> None:
    with (
        patch("newrelic_integration.webhook.webhook_manager.ocean", ocean_mock),
        patch(
            "newrelic_integration.webhook.webhook_manager.render_query",
            new=AsyncMock(return_value="mocked-mutation"),
        ),
        patch(
            "newrelic_integration.webhook.webhook_manager.send_graph_api_request",
            new=AsyncMock(
                return_value={
                    "data": {
                        "aiWorkflowsCreateWorkflow": {
                            "workflow": {"id": "workflow-123", "name": "port-workflow"}
                        }
                    }
                }
            ),
        ),
    ):
        result = cast(
            Dict[str, Any],
            await manager.create_workflow(123456, "channel-123", "port-workflow"),
        )
        assert (
            result["data"]["aiWorkflowsCreateWorkflow"]["workflow"]["id"]
            == "workflow-123"
        )


@pytest.mark.asyncio
async def test_get_issue_entity_guids(
    manager: NewRelicWebhookManager, ocean_mock: MagicMock
) -> None:
    with (
        patch("newrelic_integration.webhook.webhook_manager.ocean", ocean_mock),
        patch(
            "newrelic_integration.webhook.webhook_manager.render_query", new=AsyncMock()
        ),
        patch(
            "newrelic_integration.webhook.webhook_manager.send_graph_api_request",
            new=AsyncMock(
                return_value={
                    "data": {
                        "actor": {
                            "account": {
                                "aiIssues": {
                                    "issues": {
                                        "issues": [
                                            {"entityGuids": ["entity1", "entity2"]}
                                        ]
                                    }
                                }
                            }
                        }
                    }
                }
            ),
        ),
    ):
        result = await manager.get_issue_entity_guids("issue-123")
        assert result == ["entity1", "entity2"]


@pytest.mark.asyncio
async def test_create_webhook_full_flow_success(
    manager: NewRelicWebhookManager, ocean_mock: MagicMock
) -> None:
    with (
        patch("newrelic_integration.webhook.webhook_manager.ocean", ocean_mock),
        patch.object(
            manager, "get_existing_webhooks", new=AsyncMock(return_value=False)
        ),
        patch.object(
            manager,
            "create_destination_webhook",
            new=AsyncMock(
                return_value={
                    "data": {
                        "aiNotificationsCreateDestination": {
                            "destination": {"id": "webhook-123"}
                        }
                    }
                }
            ),
        ),
        patch.object(
            manager,
            "create_channel",
            new=AsyncMock(
                return_value={
                    "data": {
                        "aiNotificationsCreateChannel": {
                            "channel": {"id": "channel-123"}
                        }
                    }
                }
            ),
        ),
        patch.object(
            manager, "get_existing_workflows", new=AsyncMock(return_value=None)
        ),
        patch.object(
            manager,
            "create_workflow",
            new=AsyncMock(
                return_value={
                    "data": {
                        "aiWorkflowsCreateWorkflow": {
                            "workflow": {"id": "workflow-123"}
                        }
                    }
                }
            ),
        ),
    ):
        result = await manager.create_webhook()
        assert result is True
