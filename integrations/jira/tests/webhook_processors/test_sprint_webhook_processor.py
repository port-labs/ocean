import pytest
from typing import Any
from unittest.mock import AsyncMock, patch

from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from jira.overrides import JiraSprintSelector
from webhook_processors.sprint_webhook_processor import SprintWebhookProcessor


MOCK_SPRINT: dict[str, Any] = {
    "id": 1,
    "self": "https://example.atlassian.net/rest/agile/latest/sprint/1",
    "state": "active",
    "name": "Sprint 1",
    "startDate": "2026-03-01T00:00:00.000Z",
    "endDate": "2026-03-15T00:00:00.000Z",
    "completeDate": None,
    "createdDate": "2026-02-28T00:00:00.000Z",
    "originBoardId": 1,
    "goal": "Ship board kind",
}

MOCK_SPRINT_CLOSED: dict[str, Any] = {
    **MOCK_SPRINT,
    "id": 2,
    "name": "Sprint 2",
    "state": "closed",
    "completeDate": "2026-03-16T00:00:00.000Z",
}


@pytest.fixture
def event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def sprint_processor(event: WebhookEvent) -> SprintWebhookProcessor:
    return SprintWebhookProcessor(event)


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind="sprint",
        selector=JiraSprintSelector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id | tostring",
                    title=".name",
                    blueprint='"jiraSprint"',
                    properties={},
                    relations={},
                )
            )
        ),
    )


class TestSprintWebhookProcessorShouldProcessEvent:
    @pytest.mark.asyncio
    async def test_processes_sprint_created(
        self, sprint_processor: SprintWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": "sprint_created"},
            headers={},
        )
        assert await sprint_processor.should_process_event(event) is True

    @pytest.mark.asyncio
    async def test_processes_sprint_updated(
        self, sprint_processor: SprintWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": "sprint_updated"},
            headers={},
        )
        assert await sprint_processor.should_process_event(event) is True

    @pytest.mark.asyncio
    async def test_processes_sprint_deleted(
        self, sprint_processor: SprintWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": "sprint_deleted"},
            headers={},
        )
        assert await sprint_processor.should_process_event(event) is True

    @pytest.mark.asyncio
    async def test_processes_sprint_closed(
        self, sprint_processor: SprintWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": "sprint_closed"},
            headers={},
        )
        assert await sprint_processor.should_process_event(event) is True

    @pytest.mark.asyncio
    async def test_ignores_board_event(
        self, sprint_processor: SprintWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": "board_created"},
            headers={},
        )
        assert await sprint_processor.should_process_event(event) is False

    @pytest.mark.asyncio
    async def test_ignores_issue_event(
        self, sprint_processor: SprintWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": "jira:issue_created"},
            headers={},
        )
        assert await sprint_processor.should_process_event(event) is False

    @pytest.mark.asyncio
    async def test_ignores_project_event(
        self, sprint_processor: SprintWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": "project_created"},
            headers={},
        )
        assert await sprint_processor.should_process_event(event) is False


class TestSprintWebhookProcessorGetMatchingKinds:
    @pytest.mark.asyncio
    async def test_returns_sprint_kind(
        self, sprint_processor: SprintWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": "sprint_created"},
            headers={},
        )
        assert await sprint_processor.get_matching_kinds(event) == ["sprint"]


class TestSprintWebhookProcessorAuthenticate:
    @pytest.mark.asyncio
    async def test_always_returns_true(
        self, sprint_processor: SprintWebhookProcessor
    ) -> None:
        assert await sprint_processor.authenticate({}, {}) is True


class TestSprintWebhookProcessorValidatePayload:
    @pytest.mark.asyncio
    async def test_valid_payload(
        self, sprint_processor: SprintWebhookProcessor
    ) -> None:
        assert (
            await sprint_processor.validate_payload(
                {"webhookEvent": "sprint_created", "sprint": {"id": 1}}
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_returns_false_when_sprint_key_is_missing(
        self, sprint_processor: SprintWebhookProcessor
    ) -> None:
        assert (
            await sprint_processor.validate_payload({"webhookEvent": "sprint_created"})
            is False
        )

    @pytest.mark.asyncio
    async def test_returns_false_when_sprint_is_not_a_dict(
        self, sprint_processor: SprintWebhookProcessor
    ) -> None:
        assert (
            await sprint_processor.validate_payload(
                {"webhookEvent": "sprint_created", "sprint": "invalid"}
            )
            is False
        )

    @pytest.mark.asyncio
    async def test_returns_false_when_sprint_id_is_missing(
        self, sprint_processor: SprintWebhookProcessor
    ) -> None:
        assert (
            await sprint_processor.validate_payload(
                {"webhookEvent": "sprint_created", "sprint": {"name": "Sprint 1"}}
            )
            is False
        )

    @pytest.mark.asyncio
    async def test_returns_false_when_sprint_id_is_none(
        self, sprint_processor: SprintWebhookProcessor
    ) -> None:
        assert (
            await sprint_processor.validate_payload(
                {"webhookEvent": "sprint_created", "sprint": {"id": None}}
            )
            is False
        )

    @pytest.mark.asyncio
    async def test_returns_false_when_payload_is_empty(
        self, sprint_processor: SprintWebhookProcessor
    ) -> None:
        assert await sprint_processor.validate_payload({}) is False


class TestSprintWebhookProcessorHandleEvent:
    @pytest.mark.asyncio
    async def test_sprint_deleted_returns_deleted_raw_results(
        self,
        sprint_processor: SprintWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        payload: dict[str, Any] = {
            "webhookEvent": "sprint_deleted",
            "sprint": MOCK_SPRINT,
        }

        result = await sprint_processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == [MOCK_SPRINT]

    @pytest.mark.asyncio
    async def test_sprint_created_fetches_and_returns_updated_raw_results(
        self,
        sprint_processor: SprintWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        payload: dict[str, Any] = {
            "webhookEvent": "sprint_created",
            "sprint": MOCK_SPRINT,
        }

        with patch(
            "webhook_processors.sprint_webhook_processor.get_or_create_jira_client"
        ) as mock_create_client:
            mock_client = AsyncMock()
            mock_client.get_single_sprint = AsyncMock(return_value=MOCK_SPRINT)
            mock_create_client.return_value = mock_client

            result = await sprint_processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == [MOCK_SPRINT]
        assert result.deleted_raw_results == []
        mock_client.get_single_sprint.assert_called_once_with(
            sprint_id=MOCK_SPRINT["id"]
        )

    @pytest.mark.asyncio
    async def test_sprint_updated_fetches_and_returns_updated_raw_results(
        self,
        sprint_processor: SprintWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        payload: dict[str, Any] = {
            "webhookEvent": "sprint_updated",
            "sprint": MOCK_SPRINT,
        }

        with patch(
            "webhook_processors.sprint_webhook_processor.get_or_create_jira_client"
        ) as mock_create_client:
            mock_client = AsyncMock()
            mock_client.get_single_sprint = AsyncMock(return_value=MOCK_SPRINT)
            mock_create_client.return_value = mock_client

            result = await sprint_processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == [MOCK_SPRINT]
        assert result.deleted_raw_results == []

    @pytest.mark.asyncio
    async def test_sprint_closed_upserts_sprint_with_closed_state(
        self,
        sprint_processor: SprintWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        """sprint_closed is an upsert — state transitions to closed, not a delete."""
        payload: dict[str, Any] = {
            "webhookEvent": "sprint_closed",
            "sprint": MOCK_SPRINT_CLOSED,
        }

        with patch(
            "webhook_processors.sprint_webhook_processor.get_or_create_jira_client"
        ) as mock_create_client:
            mock_client = AsyncMock()
            mock_client.get_single_sprint = AsyncMock(return_value=MOCK_SPRINT_CLOSED)
            mock_create_client.return_value = mock_client

            result = await sprint_processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == [MOCK_SPRINT_CLOSED]
        assert result.deleted_raw_results == []
        assert result.updated_raw_results[0]["state"] == "closed"

    @pytest.mark.asyncio
    async def test_sprint_not_found_after_create_returns_empty_results(
        self,
        sprint_processor: SprintWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        """If get_single_sprint returns None, no update or delete should occur."""
        payload: dict[str, Any] = {
            "webhookEvent": "sprint_created",
            "sprint": MOCK_SPRINT,
        }

        with patch(
            "webhook_processors.sprint_webhook_processor.get_or_create_jira_client"
        ) as mock_create_client:
            mock_client = AsyncMock()
            mock_client.get_single_sprint = AsyncMock(return_value=None)
            mock_create_client.return_value = mock_client

            result = await sprint_processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
