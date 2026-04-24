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
from jira.overrides import JiraBoardSelector
from webhook_processors.board_webhook_processor import BoardWebhookProcessor


MOCK_BOARD: dict[str, Any] = {
    "id": 1,
    "name": "PORT board",
    "type": "scrum",
    "self": "https://exampleorg.atlassian.net/rest/agile/1.0/board/1",
    "location": {
        "projectId": 10000,
        "projectKey": "PORT",
        "projectName": "Port",
        "projectTypeKey": "software",
        "displayName": "Port (PORT)",
    },
    "isPrivate": False,
}

MOCK_BOARD_WITH_ADMINS: dict[str, Any] = {
    **MOCK_BOARD,
    "admins": {
        "users": [
            {"accountId": "abc123", "displayName": "Alice", "active": True},
            {"accountId": "def456", "displayName": "Bob", "active": True},
        ],
        "groups": [
            {"name": "jira-admins", "self": "https://..."},
        ],
    },
}


@pytest.fixture
def event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def board_processor(event: WebhookEvent) -> BoardWebhookProcessor:
    return BoardWebhookProcessor(event)


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind="board",
        selector=JiraBoardSelector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id | tostring",
                    title=".name",
                    blueprint='"jiraBoard"',
                    properties={},
                    relations={},
                )
            )
        ),
    )


class TestBoardWebhookProcessorShouldProcessEvent:
    @pytest.mark.asyncio
    async def test_processes_board_created(
        self, board_processor: BoardWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": "board_created"},
            headers={},
        )
        assert await board_processor.should_process_event(event) is True

    @pytest.mark.asyncio
    async def test_processes_board_updated(
        self, board_processor: BoardWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": "board_updated"},
            headers={},
        )
        assert await board_processor.should_process_event(event) is True

    @pytest.mark.asyncio
    async def test_processes_board_deleted(
        self, board_processor: BoardWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": "board_deleted"},
            headers={},
        )
        assert await board_processor.should_process_event(event) is True

    @pytest.mark.asyncio
    async def test_ignores_issue_event(
        self, board_processor: BoardWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": "jira:issue_created"},
            headers={},
        )
        assert await board_processor.should_process_event(event) is False

    @pytest.mark.asyncio
    async def test_ignores_sprint_event(
        self, board_processor: BoardWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": "sprint_created"},
            headers={},
        )
        assert await board_processor.should_process_event(event) is False

    @pytest.mark.asyncio
    async def test_ignores_project_event(
        self, board_processor: BoardWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": "project_created"},
            headers={},
        )
        assert await board_processor.should_process_event(event) is False


class TestBoardWebhookProcessorGetMatchingKinds:
    @pytest.mark.asyncio
    async def test_returns_board_kind(
        self, board_processor: BoardWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": "board_created"},
            headers={},
        )
        assert await board_processor.get_matching_kinds(event) == ["board"]


class TestBoardWebhookProcessorAuthenticate:
    @pytest.mark.asyncio
    async def test_always_returns_true(
        self, board_processor: BoardWebhookProcessor
    ) -> None:
        assert await board_processor.authenticate({}, {}) is True


class TestBoardWebhookProcessorValidatePayload:
    @pytest.mark.asyncio
    async def test_valid_payload(self, board_processor: BoardWebhookProcessor) -> None:
        assert (
            await board_processor.validate_payload(
                {"webhookEvent": "board_created", "board": {"id": 1}}
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_missing_board_key(
        self, board_processor: BoardWebhookProcessor
    ) -> None:
        assert (
            await board_processor.validate_payload({"webhookEvent": "board_created"})
            is False
        )

    @pytest.mark.asyncio
    async def test_missing_board_id(
        self, board_processor: BoardWebhookProcessor
    ) -> None:
        assert (
            await board_processor.validate_payload(
                {"webhookEvent": "board_created", "board": {"name": "PORT board"}}
            )
            is False
        )

    @pytest.mark.asyncio
    async def test_empty_payload(self, board_processor: BoardWebhookProcessor) -> None:
        assert await board_processor.validate_payload({}) is False

    @pytest.mark.asyncio
    async def test_validate_payload_board_is_none(
        self, board_processor: BoardWebhookProcessor
    ) -> None:
        assert (
            await board_processor.validate_payload(
                {"webhookEvent": "board_created", "board": None}
            )
            is False
        )

    @pytest.mark.asyncio
    async def test_validate_payload_board_is_not_a_dict(
        self, board_processor: BoardWebhookProcessor
    ) -> None:
        assert (
            await board_processor.validate_payload(
                {"webhookEvent": "board_created", "board": "invalid"}
            )
            is False
        )

    @pytest.mark.asyncio
    async def test_validate_payload_board_id_is_none(
        self, board_processor: BoardWebhookProcessor
    ) -> None:
        assert (
            await board_processor.validate_payload(
                {"webhookEvent": "board_created", "board": {"id": None}}
            )
            is False
        )


class TestBoardWebhookProcessorHandleEvent:
    @pytest.mark.asyncio
    async def test_board_deleted_returns_deleted_raw_results(
        self,
        board_processor: BoardWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        payload: dict[str, Any] = {
            "webhookEvent": "board_deleted",
            "board": MOCK_BOARD,
        }

        result = await board_processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == [MOCK_BOARD]

    @pytest.mark.asyncio
    async def test_board_created_fetches_and_returns_updated_raw_results(
        self,
        board_processor: BoardWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        payload: dict[str, Any] = {
            "webhookEvent": "board_created",
            "board": MOCK_BOARD,
        }

        with patch(
            "webhook_processors.board_webhook_processor.get_or_create_jira_client"
        ) as mock_create_client:
            mock_client = AsyncMock()
            mock_client.get_single_board = AsyncMock(return_value=MOCK_BOARD)
            mock_client.enrich_board_with_projects = AsyncMock(return_value=MOCK_BOARD)
            mock_create_client.return_value = mock_client

            result = await board_processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == [MOCK_BOARD]
        assert result.deleted_raw_results == []
        mock_client.get_single_board.assert_called_once_with(MOCK_BOARD["id"])
        mock_client.enrich_board_with_projects.assert_called_once_with(MOCK_BOARD)

    @pytest.mark.asyncio
    async def test_board_updated_fetches_and_returns_updated_raw_results(
        self,
        board_processor: BoardWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        payload: dict[str, Any] = {
            "webhookEvent": "board_updated",
            "board": MOCK_BOARD,
        }

        with patch(
            "webhook_processors.board_webhook_processor.get_or_create_jira_client"
        ) as mock_create_client:
            mock_client = AsyncMock()
            mock_client.get_single_board = AsyncMock(return_value=MOCK_BOARD)
            mock_client.enrich_board_with_projects = AsyncMock(return_value=MOCK_BOARD)
            mock_create_client.return_value = mock_client

            result = await board_processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == [MOCK_BOARD]
        assert result.deleted_raw_results == []
        mock_client.enrich_board_with_projects.assert_called_once_with(MOCK_BOARD)

    @pytest.mark.asyncio
    async def test_board_updated_with_admins_returns_full_board(
        self,
        board_processor: BoardWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        """Single board fetch via webhook includes admins not available in list endpoint."""
        payload: dict[str, Any] = {
            "webhookEvent": "board_updated",
            "board": MOCK_BOARD,
        }
        enriched_board_with_admins = {
            **MOCK_BOARD_WITH_ADMINS,
            "__projectKeys": ["PORT"],
        }

        with patch(
            "webhook_processors.board_webhook_processor.get_or_create_jira_client"
        ) as mock_create_client:
            mock_client = AsyncMock()
            mock_client.get_single_board = AsyncMock(
                return_value=MOCK_BOARD_WITH_ADMINS
            )
            mock_client.enrich_board_with_projects = AsyncMock(
                return_value=enriched_board_with_admins
            )
            mock_create_client.return_value = mock_client

            result = await board_processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == [enriched_board_with_admins]
        assert "admins" in result.updated_raw_results[0]
        assert "__projectKeys" in result.updated_raw_results[0]

    @pytest.mark.asyncio
    async def test_board_not_found_after_create_returns_empty_results(
        self,
        board_processor: BoardWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        """If get_single_board returns None, no update or delete should occur."""
        payload: dict[str, Any] = {
            "webhookEvent": "board_created",
            "board": MOCK_BOARD,
        }

        with patch(
            "webhook_processors.board_webhook_processor.get_or_create_jira_client"
        ) as mock_create_client:
            mock_client = AsyncMock()
            mock_client.get_single_board = AsyncMock(return_value=None)
            mock_create_client.return_value = mock_client

            result = await board_processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_board_created_enriches_board_with_project_keys(
    board_processor: BoardWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    """board_created webhook must enrich board with __projectKeys before upsert
    to prevent project relation from being overwritten with null."""
    payload: dict[str, Any] = {
        "webhookEvent": "board_created",
        "board": MOCK_BOARD,
    }
    enriched_board = {**MOCK_BOARD, "__projectKeys": ["PORT"]}

    with patch(
        "webhook_processors.board_webhook_processor.get_or_create_jira_client"
    ) as mock_create_client:
        mock_client = AsyncMock()
        mock_client.get_single_board = AsyncMock(return_value=MOCK_BOARD)
        mock_client.enrich_board_with_projects = AsyncMock(return_value=enriched_board)
        mock_create_client.return_value = mock_client

        result = await board_processor.handle_event(payload, resource_config)

    assert result.updated_raw_results == [enriched_board]
    assert "__projectKeys" in result.updated_raw_results[0]
    mock_client.enrich_board_with_projects.assert_called_once_with(MOCK_BOARD)


@pytest.mark.asyncio
async def test_board_updated_enriches_board_with_project_keys(
    board_processor: BoardWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    """board_updated webhook must enrich board with __projectKeys before upsert
    to prevent project relation from being overwritten with null."""
    payload: dict[str, Any] = {
        "webhookEvent": "board_updated",
        "board": MOCK_BOARD,
    }
    enriched_board = {**MOCK_BOARD, "__projectKeys": ["PORT", "DEMO"]}

    with patch(
        "webhook_processors.board_webhook_processor.get_or_create_jira_client"
    ) as mock_create_client:
        mock_client = AsyncMock()
        mock_client.get_single_board = AsyncMock(return_value=MOCK_BOARD)
        mock_client.enrich_board_with_projects = AsyncMock(return_value=enriched_board)
        mock_create_client.return_value = mock_client

        result = await board_processor.handle_event(payload, resource_config)

    assert result.updated_raw_results == [enriched_board]
    assert result.updated_raw_results[0]["__projectKeys"] == ["PORT", "DEMO"]
    mock_client.enrich_board_with_projects.assert_called_once_with(MOCK_BOARD)


@pytest.mark.asyncio
async def test_board_deleted_does_not_enrich_board_with_project_keys(
    board_processor: BoardWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    """board_deleted webhook must not call enrich_board_with_projects
    since deleted entities don't need relation data."""
    payload: dict[str, Any] = {
        "webhookEvent": "board_deleted",
        "board": MOCK_BOARD,
    }

    with patch(
        "webhook_processors.board_webhook_processor.get_or_create_jira_client"
    ) as mock_create_client:
        mock_client = AsyncMock()
        mock_create_client.return_value = mock_client

        result = await board_processor.handle_event(payload, resource_config)

    assert result.deleted_raw_results == [MOCK_BOARD]
    mock_client.enrich_board_with_projects.assert_not_called()
