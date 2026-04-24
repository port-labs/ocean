from unittest.mock import AsyncMock, patch

import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from jira_server.webhook_processors.events import JiraDeletedUserEvent
from jira_server.webhook_processors.processors.user_webhook_processor import (
    UserWebhookProcessor,
)


@pytest.fixture
def webhook_event() -> WebhookEvent:
    return WebhookEvent(
        payload={
            "webhookEvent": "user_created",
            "user": {
                "self": "https://jira.atlassian.com/rest/api/2/user?username=brollins",
                "name": "brollins",
                "key": "brollins",
                "emailAddress": "bryansemail at atlassian dot com",
                "avatarUrls": {
                    "16x16": "https://jira.atlassian.com/secure/useravatar?size=small&avatarId=10605",
                    "48x48": "https://jira.atlassian.com/secure/useravatar?avatarId=10605",
                },
                "displayName": "Bryan Rollins [Atlassian]",
                "active": "true",
            },
        },
        headers={},
        trace_id="test-trace-id",
    )


@pytest.fixture
def user_webhook_processor(webhook_event: WebhookEvent) -> UserWebhookProcessor:
    return UserWebhookProcessor(webhook_event)


@pytest.mark.asyncio
class TestUserWebhookProcessor:
    async def test_should_process_event_true(
        self, user_webhook_processor: UserWebhookProcessor, webhook_event: WebhookEvent
    ) -> None:
        assert await user_webhook_processor.should_process_event(webhook_event) is True

    async def test_should_process_event_false(
        self, user_webhook_processor: UserWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            payload={"webhookEvent": "some:other_event"},
            headers={},
            trace_id="test-trace-id",
        )
        assert await user_webhook_processor.should_process_event(event) is False

    async def test_validate_payload_valid(
        self, user_webhook_processor: UserWebhookProcessor
    ) -> None:
        payload = {"webhookEvent": "user_created", "user": {}}
        assert await user_webhook_processor.validate_payload(payload) is True

    async def test_validate_payload_invalid(
        self, user_webhook_processor: UserWebhookProcessor
    ) -> None:
        assert await user_webhook_processor.validate_payload({}) is False
        assert (
            await user_webhook_processor.validate_payload({"webhookEvent": "event"})
            is False
        )
        assert await user_webhook_processor.validate_payload({"user": {}}) is False

    async def test_handle_event_user_created(
        self, user_webhook_processor: UserWebhookProcessor
    ) -> None:
        payload = {
            "webhookEvent": "user_created",
            "user": {
                "self": "https://jira.atlassian.com/rest/api/2/user?username=brollins",
                "name": "brollins",
                "key": "brollins",
                "emailAddress": "bryansemail at atlassian dot com",
                "avatarUrls": {
                    "16x16": "https://jira.atlassian.com/secure/useravatar?size=small&avatarId=10605",
                    "48x48": "https://jira.atlassian.com/secure/useravatar?avatarId=10605",
                },
                "displayName": "Bryan Rollins [Atlassian]",
                "active": "true",
            },
        }
        resource_config = AsyncMock()

        mock_client = AsyncMock()
        mock_client.get_single_user.return_value = payload["user"]

        with patch(
            "jira_server.webhook_processors.processors.user_webhook_processor.init_webhook_client",
            return_value=mock_client,
        ):
            results = await user_webhook_processor.handle_event(
                payload, resource_config
            )

        assert len(results.updated_raw_results) == 1
        assert (
            results.updated_raw_results[0]["displayName"] == "Bryan Rollins [Atlassian]"
        )
        assert len(results.deleted_raw_results) == 0
        mock_client.get_single_user.assert_called_once_with("brollins")

    async def test_handle_event_user_not_found(
        self, user_webhook_processor: UserWebhookProcessor
    ) -> None:
        payload = {
            "webhookEvent": "user_created",
            "user": {
                "self": "https://jira.atlassian.com/rest/api/2/user?username=brollins",
                "name": "brollins",
                "key": "brollins",
                "emailAddress": "bryansemail at atlassian dot com",
                "avatarUrls": {
                    "16x16": "https://jira.atlassian.com/secure/useravatar?size=small&avatarId=10605",
                    "48x48": "https://jira.atlassian.com/secure/useravatar?avatarId=10605",
                },
                "displayName": "Bryan Rollins [Atlassian]",
                "active": "true",
            },
        }
        resource_config = AsyncMock()

        mock_client = AsyncMock()
        mock_client.get_single_user.return_value = None

        with patch(
            "jira_server.webhook_processors.processors.user_webhook_processor.init_webhook_client",
            return_value=mock_client,
        ):
            results = await user_webhook_processor.handle_event(
                payload, resource_config
            )

        assert len(results.updated_raw_results) == 0
        assert len(results.deleted_raw_results) == 0
        mock_client.get_single_user.assert_called_once_with("brollins")

    async def test_handle_event_user_deleted(
        self, user_webhook_processor: UserWebhookProcessor
    ) -> None:
        payload = {
            "webhookEvent": JiraDeletedUserEvent,
            "user": {
                "self": "https://jira.atlassian.com/rest/api/2/user?username=brollins",
                "name": "brollins",
                "key": "brollins",
                "emailAddress": "bryansemail at atlassian dot com",
                "avatarUrls": {
                    "16x16": "https://jira.atlassian.com/secure/useravatar?size=small&avatarId=10605",
                    "48x48": "https://jira.atlassian.com/secure/useravatar?avatarId=10605",
                },
                "displayName": "Bryan Rollins [Atlassian]",
                "active": "true",
            },
        }
        resource_config = AsyncMock()
        mock_client = AsyncMock()
        mock_client.get_single_user.return_value = payload["user"]
        with patch(
            "jira_server.webhook_processors.processors.user_webhook_processor.init_webhook_client",
            return_value=mock_client,
        ):
            results = await user_webhook_processor.handle_event(
                payload, resource_config
            )

        assert len(results.updated_raw_results) == 0
        assert len(results.deleted_raw_results) == 1
        assert results.deleted_raw_results[0]["key"] == "brollins"
