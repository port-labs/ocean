import pytest
import json
import hmac
import hashlib
from unittest.mock import MagicMock
from fastapi import Request
from typing import Any, Dict, List
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from github.webhook.webhook_processors.github_abstract_webhook_processor import (
    _GithubAbstractWebhookProcessor,
)
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults


class MockGithubAbstractProcessor(_GithubAbstractWebhookProcessor):
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("x-gh-test") == "process"

    async def get_matching_kinds(self, event: WebhookEvent) -> List[str]:
        return ["gh_test_kind"]

    async def handle_event(
        self, payload: Dict[str, str], resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        return WebhookEventRawResults(
            updated_raw_results=[{"gh_test": "result"}], deleted_raw_results=[]
        )

    async def validate_payload(self, payload: Dict[str, Any]) -> bool:
        return True


def create_gh_mock_request(body: bytes, headers: Dict[str, str]) -> Request:
    mock_request = MagicMock(spec=Request)
    mock_request.headers = headers

    async def mock_body() -> bytes:
        return body

    mock_request.body = mock_body
    return mock_request


def generate_gh_signature(secret: str, payload: bytes) -> str:
    mac = hmac.new(secret.encode(), msg=payload, digestmod=hashlib.sha256)
    return "sha256=" + mac.hexdigest()


@pytest.fixture
def gh_event() -> WebhookEvent:
    return WebhookEvent(trace_id="gh-test-trace", payload={}, headers={})


@pytest.fixture
def gh_processor(gh_event: WebhookEvent) -> MockGithubAbstractProcessor:
    return MockGithubAbstractProcessor(gh_event)


@pytest.mark.asyncio
class TestGitHubAbstractWebhookProcessor:
    async def test_verify_webhook_signature_no_secret(
        self, gh_processor: MockGithubAbstractProcessor, mock_ocean_context: Any
    ) -> None:
        ocean.integration_config["webhook_secret"] = None

        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"x-hub-signature-256": "test-signature"}

        result: bool = await gh_processor._verify_webhook_signature(mock_request)
        assert result is True

    async def test_verify_webhook_signature_invalid_headers(
        self, gh_processor: MockGithubAbstractProcessor, mock_ocean_context: Any
    ) -> None:
        mock_request: Request = create_gh_mock_request(b"{}", {})
        result: bool = await gh_processor._verify_webhook_signature(mock_request)
        assert result is False

    async def test_verify_webhook_signature_valid(
        self, gh_processor: MockGithubAbstractProcessor, mock_ocean_context: Any
    ) -> None:
        payload: Dict[str, Any] = {"test": "data"}
        payload_bytes: bytes = json.dumps(payload).encode("utf-8")
        valid_signature: str = generate_gh_signature(
            ocean.integration_config["webhook_secret"], payload_bytes
        )
        headers: Dict[str, str] = {"x-hub-signature-256": valid_signature}
        mock_request: Request = create_gh_mock_request(payload_bytes, headers)
        result: bool = await gh_processor._verify_webhook_signature(mock_request)
        assert result is True

    async def test_verify_webhook_signature_invalid(
        self, gh_processor: MockGithubAbstractProcessor, mock_ocean_context: Any
    ) -> None:
        payload: Dict[str, Any] = {"test": "data"}
        payload_bytes: bytes = json.dumps(payload).encode("utf-8")
        invalid_signature: str = "sha256=invalidsignature"
        headers: Dict[str, str] = {"x-hub-signature-256": invalid_signature}
        mock_request: Request = create_gh_mock_request(payload_bytes, headers)
        result: bool = await gh_processor._verify_webhook_signature(mock_request)
        assert result is False

    async def test_should_process_event_no_request(
        self, gh_processor: MockGithubAbstractProcessor
    ) -> None:
        event: WebhookEvent = WebhookEvent(
            trace_id="gh-test-trace",
            headers={"x-hub-signature-256": "process"},
            payload={},
        )
        event._original_request = None
        result: bool = await gh_processor.should_process_event(event)
        assert result is False

    async def test_should_process_event_implementation_returns_false(
        self, gh_processor: MockGithubAbstractProcessor
    ) -> None:
        payload: Dict[str, Any] = {"test": "data"}
        payload_bytes: bytes = json.dumps(payload).encode("utf-8")
        headers: Dict[str, str] = {"x-hub-signature-256": "do-not-process"}
        mock_request: Request = create_gh_mock_request(payload_bytes, headers)
        event: WebhookEvent = WebhookEvent(
            trace_id="gh-test-trace",
            headers=headers,
            payload=payload,
        )
        event._original_request = mock_request
        result: bool = await gh_processor.should_process_event(event)
        assert result is False
