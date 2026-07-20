from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from jira.overrides import JiraWorklogSelector
from webhook_processors.worklog_webhook_processor import WorklogWebhookProcessor


MOCK_WORKLOG = {
    "id": "10100",
    "self": "https://example.atlassian.net/rest/api/3/issue/10001/worklog/10100",
    "issueId": "10001",
    "author": {
        "self": "https://example.atlassian.net/rest/api/3/user?accountId=712020:test-account-id",
        "accountId": "712020:test-account-id",
        "emailAddress": "test.user@example.com",
        "avatarUrls": {
            "48x48": "https://example.atlassian.net/avatar/48x48.png",
            "24x24": "https://example.atlassian.net/avatar/24x24.png",
            "16x16": "https://example.atlassian.net/avatar/16x16.png",
            "32x32": "https://example.atlassian.net/avatar/32x32.png",
        },
        "displayName": "Test User",
        "active": True,
        "timeZone": "UTC",
        "accountType": "atlassian",
    },
    "updateAuthor": {
        "self": "https://example.atlassian.net/rest/api/3/user?accountId=712020:test-account-id",
        "accountId": "712020:test-account-id",
        "emailAddress": "test.user@example.com",
        "avatarUrls": {
            "48x48": "https://example.atlassian.net/avatar/48x48.png",
            "24x24": "https://example.atlassian.net/avatar/24x24.png",
            "16x16": "https://example.atlassian.net/avatar/16x16.png",
            "32x32": "https://example.atlassian.net/avatar/32x32.png",
        },
        "displayName": "Test User",
        "active": True,
        "timeZone": "UTC",
        "accountType": "atlassian",
    },
    "comment": {"type": "doc", "version": 1, "content": []},
    "created": "2024-01-15T10:00:00.000+0000",
    "updated": "2024-01-15T10:00:00.000+0000",
    "started": "2024-01-15T09:00:00.000+0000",
    "timeSpent": "1d",
    "timeSpentSeconds": 28800,
}

MOCK_WORKLOG_DELETED = {
    "id": "10100",
    "issueId": "10001",
}

MOCK_ISSUE = {
    "expand": "renderedFields,names,schema,operations,editmeta,changelog,versionedRepresentations",
    "id": "10001",
    "self": "https://example.atlassian.net/rest/api/3/issue/10001",
    "key": "TEST-1",
}


@pytest.fixture
def event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def worklog_processor(event: WebhookEvent) -> WorklogWebhookProcessor:
    return WorklogWebhookProcessor(event)


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind="worklog",
        selector=JiraWorklogSelector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title='.author.displayName + " - " + .started',
                    blueprint='"jiraWorklog"',
                    properties={},
                    relations={},
                )
            )
        ),
    )


class TestWorklogWebhookProcessorShouldProcessEvent:
    @pytest.mark.asyncio
    async def test_processes_worklog_created(
        self, worklog_processor: WorklogWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": "worklog_created"},
            headers={},
        )
        assert await worklog_processor.should_process_event(event) is True

    @pytest.mark.asyncio
    async def test_processes_worklog_updated(
        self, worklog_processor: WorklogWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": "worklog_updated"},
            headers={},
        )
        assert await worklog_processor.should_process_event(event) is True

    @pytest.mark.asyncio
    async def test_processes_worklog_deleted(
        self, worklog_processor: WorklogWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": "worklog_deleted"},
            headers={},
        )
        assert await worklog_processor.should_process_event(event) is True

    @pytest.mark.asyncio
    async def test_ignores_issue_created_event(
        self, worklog_processor: WorklogWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": "jira:issue_created"},
            headers={},
        )
        assert await worklog_processor.should_process_event(event) is False

    @pytest.mark.asyncio
    async def test_ignores_board_event(
        self, worklog_processor: WorklogWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": "board_created"},
            headers={},
        )
        assert await worklog_processor.should_process_event(event) is False

    @pytest.mark.asyncio
    async def test_ignores_sprint_event(
        self, worklog_processor: WorklogWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": "sprint_started"},
            headers={},
        )
        assert await worklog_processor.should_process_event(event) is False

    @pytest.mark.asyncio
    async def test_ignores_comment_event(
        self, worklog_processor: WorklogWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": "comment_created"},
            headers={},
        )
        assert await worklog_processor.should_process_event(event) is False


class TestWorklogWebhookProcessorGetMatchingKinds:
    @pytest.mark.asyncio
    async def test_returns_worklog_kind(
        self, worklog_processor: WorklogWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": "worklog_created"},
            headers={},
        )
        assert await worklog_processor.get_matching_kinds(event) == ["worklog"]


class TestWorklogWebhookProcessorAuthenticate:
    @pytest.mark.asyncio
    async def test_always_returns_true(
        self, worklog_processor: WorklogWebhookProcessor
    ) -> None:
        assert await worklog_processor.authenticate({}, {}) is True


class TestWorklogWebhookProcessorValidatePayload:
    @pytest.mark.asyncio
    async def test_valid_payload(
        self, worklog_processor: WorklogWebhookProcessor
    ) -> None:
        assert (
            await worklog_processor.validate_payload(
                {"webhookEvent": "worklog_created", "worklog": MOCK_WORKLOG}
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_valid_deleted_payload_with_minimal_worklog(
        self, worklog_processor: WorklogWebhookProcessor
    ) -> None:
        assert (
            await worklog_processor.validate_payload(
                {"webhookEvent": "worklog_deleted", "worklog": MOCK_WORKLOG_DELETED}
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_missing_worklog_key(
        self, worklog_processor: WorklogWebhookProcessor
    ) -> None:
        assert (
            await worklog_processor.validate_payload(
                {"webhookEvent": "worklog_created"}
            )
            is False
        )

    @pytest.mark.asyncio
    async def test_worklog_is_none(
        self, worklog_processor: WorklogWebhookProcessor
    ) -> None:
        assert (
            await worklog_processor.validate_payload(
                {"webhookEvent": "worklog_created", "worklog": None}
            )
            is False
        )

    @pytest.mark.asyncio
    async def test_worklog_is_not_a_dict(
        self, worklog_processor: WorklogWebhookProcessor
    ) -> None:
        assert (
            await worklog_processor.validate_payload(
                {"webhookEvent": "worklog_created", "worklog": "invalid"}
            )
            is False
        )

    @pytest.mark.asyncio
    async def test_worklog_missing_id(
        self, worklog_processor: WorklogWebhookProcessor
    ) -> None:
        assert (
            await worklog_processor.validate_payload(
                {
                    "webhookEvent": "worklog_created",
                    "worklog": {"issueId": "10001"},
                }
            )
            is False
        )

    @pytest.mark.asyncio
    async def test_worklog_id_is_none(
        self, worklog_processor: WorklogWebhookProcessor
    ) -> None:
        assert (
            await worklog_processor.validate_payload(
                {
                    "webhookEvent": "worklog_created",
                    "worklog": {"id": None, "issueId": "10001"},
                }
            )
            is False
        )

    @pytest.mark.asyncio
    async def test_empty_payload(
        self, worklog_processor: WorklogWebhookProcessor
    ) -> None:
        assert await worklog_processor.validate_payload({}) is False


class TestWorklogWebhookProcessorHandleEvent:
    @pytest.mark.asyncio
    async def test_worklog_deleted_returns_deleted_raw_results(
        self,
        worklog_processor: WorklogWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        payload: dict[str, Any] = {
            "webhookEvent": "worklog_deleted",
            "worklog": MOCK_WORKLOG_DELETED,
        }

        result = await worklog_processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == [MOCK_WORKLOG_DELETED]

    @pytest.mark.asyncio
    async def test_worklog_deleted_does_not_call_jira_api(
        self,
        worklog_processor: WorklogWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        payload: dict[str, Any] = {
            "webhookEvent": "worklog_deleted",
            "worklog": MOCK_WORKLOG_DELETED,
        }

        with patch(
            "webhook_processors.worklog_webhook_processor.get_or_create_jira_client"
        ) as mock_create_client:
            await worklog_processor.handle_event(payload, resource_config)

        mock_create_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_worklog_created_fetches_issue_and_enriches_with_issue_key(
        self,
        worklog_processor: WorklogWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        payload: dict[str, Any] = {
            "webhookEvent": "worklog_created",
            "worklog": MOCK_WORKLOG,
        }

        with patch(
            "webhook_processors.worklog_webhook_processor.get_or_create_jira_client"
        ) as mock_create_client:
            mock_client = AsyncMock()
            mock_client.get_single_issue = AsyncMock(return_value=MOCK_ISSUE)
            mock_create_client.return_value = mock_client

            result = await worklog_processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == [{**MOCK_WORKLOG, "__issueKey": "TEST-1"}]
        assert result.deleted_raw_results == []
        mock_client.get_single_issue.assert_called_once_with("10001")

    @pytest.mark.asyncio
    async def test_worklog_updated_fetches_issue_and_enriches_with_issue_key(
        self,
        worklog_processor: WorklogWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        payload: dict[str, Any] = {
            "webhookEvent": "worklog_updated",
            "worklog": MOCK_WORKLOG,
        }

        with patch(
            "webhook_processors.worklog_webhook_processor.get_or_create_jira_client"
        ) as mock_create_client:
            mock_client = AsyncMock()
            mock_client.get_single_issue = AsyncMock(return_value=MOCK_ISSUE)
            mock_create_client.return_value = mock_client

            result = await worklog_processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == [{**MOCK_WORKLOG, "__issueKey": "TEST-1"}]
        assert result.deleted_raw_results == []

    @pytest.mark.asyncio
    async def test_worklog_created_preserves_all_original_worklog_fields(
        self,
        worklog_processor: WorklogWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        payload: dict[str, Any] = {
            "webhookEvent": "worklog_created",
            "worklog": MOCK_WORKLOG,
        }

        with patch(
            "webhook_processors.worklog_webhook_processor.get_or_create_jira_client"
        ) as mock_create_client:
            mock_client = AsyncMock()
            mock_client.get_single_issue = AsyncMock(return_value=MOCK_ISSUE)
            mock_create_client.return_value = mock_client

            result = await worklog_processor.handle_event(payload, resource_config)

        enriched = result.updated_raw_results[0]
        assert enriched["id"] == "10100"
        assert enriched["issueId"] == "10001"
        assert enriched["timeSpent"] == "1d"
        assert enriched["timeSpentSeconds"] == 28800
        assert enriched["author"]["accountId"] == "712020:test-account-id"
        assert enriched["__issueKey"] == "TEST-1"

    @pytest.mark.asyncio
    async def test_worklog_created_without_issue_id_returns_empty_results(
        self,
        worklog_processor: WorklogWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        worklog_without_issue_id = {**MOCK_WORKLOG}
        del worklog_without_issue_id["issueId"]

        payload: dict[str, Any] = {
            "webhookEvent": "worklog_created",
            "worklog": worklog_without_issue_id,
        }

        with patch(
            "webhook_processors.worklog_webhook_processor.get_or_create_jira_client"
        ) as mock_create_client:
            result = await worklog_processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
        mock_create_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_worklog_created_when_issue_not_found_returns_empty_results(
        self,
        worklog_processor: WorklogWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        payload: dict[str, Any] = {
            "webhookEvent": "worklog_created",
            "worklog": MOCK_WORKLOG,
        }

        with patch(
            "webhook_processors.worklog_webhook_processor.get_or_create_jira_client"
        ) as mock_create_client:
            mock_client = AsyncMock()
            mock_client.get_single_issue = AsyncMock(return_value=None)
            mock_create_client.return_value = mock_client

            result = await worklog_processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_worklog_created_calls_get_single_issue_with_string_issue_id(
    worklog_processor: WorklogWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    """issueId is numeric in the payload — must be cast to str before the API call."""
    worklog_with_numeric_issue_id = {**MOCK_WORKLOG, "issueId": 10001}

    payload: dict[str, Any] = {
        "webhookEvent": "worklog_created",
        "worklog": worklog_with_numeric_issue_id,
    }

    with patch(
        "webhook_processors.worklog_webhook_processor.get_or_create_jira_client"
    ) as mock_create_client:
        mock_client = AsyncMock()
        mock_client.get_single_issue = AsyncMock(return_value=MOCK_ISSUE)
        mock_create_client.return_value = mock_client

        await worklog_processor.handle_event(payload, resource_config)

    mock_client.get_single_issue.assert_called_once_with("10001")


@pytest.mark.asyncio
async def test_worklog_updated_does_not_affect_deleted_results(
    worklog_processor: WorklogWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    payload: dict[str, Any] = {
        "webhookEvent": "worklog_updated",
        "worklog": MOCK_WORKLOG,
    }

    with patch(
        "webhook_processors.worklog_webhook_processor.get_or_create_jira_client"
    ) as mock_create_client:
        mock_client = AsyncMock()
        mock_client.get_single_issue = AsyncMock(return_value=MOCK_ISSUE)
        mock_create_client.return_value = mock_client

        result = await worklog_processor.handle_event(payload, resource_config)

    assert result.deleted_raw_results == []
