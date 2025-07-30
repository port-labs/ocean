import pytest
import hmac
import hashlib
import time
import json
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Any
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from integration import ObjectKind
from _pytest.monkeypatch import MonkeyPatch

with patch("initialize_client.init_aikido_client"):
    from webhook_processors.issue_webhook_processor import IssueWebhookProcessor
    from webhook_processors.repository_webhook_processor import (
        RepositoryWebhookProcessor,
    )


@pytest.fixture
def event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def issue_webhook_processor(event: WebhookEvent) -> IssueWebhookProcessor:
    return IssueWebhookProcessor(event)


@pytest.fixture
def repo_webhook_processor(event: WebhookEvent) -> RepositoryWebhookProcessor:
    return RepositoryWebhookProcessor(event)


class TestIssueWebhookProcessor:
    @pytest.mark.asyncio
    async def test_should_process_event_valid_signature_and_timestamp(
        self, issue_webhook_processor: IssueWebhookProcessor, monkeypatch: MonkeyPatch
    ) -> None:
        secret = "testsecret"
        payload = {"dispatched_at": int(time.time())}
        body = json.dumps(payload).encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

        monkeypatch.setattr(
            "port_ocean.context.ocean.ocean.integration_config.get",
            lambda *args, **kwargs: secret,
        )

        event = MagicMock()
        event._original_request = MagicMock()
        event._original_request.body = AsyncMock(return_value=body)
        event.headers = {"x-aikido-webhook-signature": signature}

        result = await issue_webhook_processor.should_process_event(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_process_event_invalid_signature(
        self, issue_webhook_processor: IssueWebhookProcessor, monkeypatch: MonkeyPatch
    ) -> None:
        secret = "testsecret"
        payload = {"dispatched_at": int(time.time())}
        body = json.dumps(payload).encode("utf-8")
        signature = "invalidsignature"

        monkeypatch.setattr(
            "port_ocean.context.ocean.ocean.integration_config.get",
            lambda *args, **kwargs: secret,
        )

        event = MagicMock()
        event._original_request = MagicMock()
        event._original_request.body = AsyncMock(return_value=body)
        event.headers = {"x-aikido-webhook-signature": signature}

        result = await issue_webhook_processor.should_process_event(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_matching_kinds(
        self, issue_webhook_processor: IssueWebhookProcessor
    ) -> None:
        event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
        result = await issue_webhook_processor.get_matching_kinds(event)
        assert result == [ObjectKind.ISSUES]

    @pytest.mark.asyncio
    async def test_handle_event_valid(
        self, issue_webhook_processor: IssueWebhookProcessor, monkeypatch: MonkeyPatch
    ) -> None:
        payload = {"payload": {"issue_id": "123"}}
        mock_issue_data = {
            "id": "123",
            "status": "open",
            "title": "Test Issue",
            "severity": "high",
        }

        monkeypatch.setattr(
            issue_webhook_processor._webhook_client,
            "get_issue",
            AsyncMock(return_value=mock_issue_data),
        )

        resource_config: ResourceConfig = MagicMock(spec=ResourceConfig)
        result = await issue_webhook_processor.handle_event(payload, resource_config)

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == mock_issue_data
        assert len(result.deleted_raw_results) == 0

    @pytest.mark.parametrize(
        "payload, expected",
        [
            ({"event_type": "issue_created", "payload": {"issue_id": "123"}}, True),
            ({"event_type": "issue_updated", "payload": {"issue_id": "456"}}, True),
            ({}, False),
            ({"event_type": "repo_created"}, False),
            ({"event_type": "issue_created", "payload": {}}, False),
            ({"event_type": "issue_created"}, False),
            ({"payload": {"issue_id": "123"}}, False),
        ],
    )
    @pytest.mark.asyncio
    async def test_validate_payload(
        self,
        issue_webhook_processor: IssueWebhookProcessor,
        payload: dict[str, Any],
        expected: bool,
    ) -> None:
        result = await issue_webhook_processor.validate_payload(payload)
        assert result == expected


class TestRepositoryWebhookProcessor:
    @pytest.mark.asyncio
    async def test_get_matching_kinds(
        self, repo_webhook_processor: RepositoryWebhookProcessor
    ) -> None:
        event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
        result = await repo_webhook_processor.get_matching_kinds(event)
        assert result == [ObjectKind.REPOSITORY]

    @pytest.mark.asyncio
    async def test_handle_event_valid(
        self,
        repo_webhook_processor: RepositoryWebhookProcessor,
        monkeypatch: MonkeyPatch,
    ) -> None:
        payload = {"payload": {"issue_id": "123"}}
        mock_issue_data = {"id": "123", "code_repo_id": "repo-456", "status": "open"}
        mock_repo_data = {
            "id": "repo-456",
            "name": "test-repo",
            "url": "https://example.com/repo",
        }

        monkeypatch.setattr(
            repo_webhook_processor._webhook_client,
            "get_issue",
            AsyncMock(return_value=mock_issue_data),
        )

        monkeypatch.setattr(
            repo_webhook_processor._webhook_client,
            "get_repository",
            AsyncMock(return_value=mock_repo_data),
        )

        resource_config: ResourceConfig = MagicMock(spec=ResourceConfig)
        result = await repo_webhook_processor.handle_event(payload, resource_config)

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == mock_repo_data
        assert len(result.deleted_raw_results) == 0
