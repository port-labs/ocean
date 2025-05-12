import pytest
import json
import hmac
import hashlib
from unittest.mock import MagicMock
from fastapi import Request
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from github.webhook.webhook_processors.github_abstract_webhook_processor import (
    _GithubAbstractWebhookProcessor,
)
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from port_ocean.context.ocean import ocean

# --- Mock Processor ---


class MockGithubAbstractProcessor(_GithubAbstractWebhookProcessor):
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("x-gh-test") == "process"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return ["gh_test_kind"]

    async def handle_event(self, payload: dict, resource_config):
        return {"gh_test": "result"}

    async def validate_payload(self, payload: dict) -> bool:
        return True


# --- Helpers ---


def create_gh_mock_request(body: bytes, headers: dict) -> Request:
    mock_request = MagicMock(spec=Request)
    mock_request.headers = headers

    async def mock_body():
        return body

    mock_request.body = mock_body
    return mock_request


def generate_gh_signature(secret: str, payload: bytes) -> str:
    mac = hmac.new(secret.encode(), msg=payload, digestmod=hashlib.sha256)
    return "sha256=" + mac.hexdigest()


@pytest.fixture
def gh_event():
    return WebhookEvent(trace_id="gh-test-trace", payload={}, headers={})


@pytest.fixture
def gh_processor(gh_event):
    return MockGithubAbstractProcessor(gh_event)


@pytest.fixture(autouse=True)
def mock_ocean_context():
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "webhook_secret": "test-secret",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.mark.asyncio
class TestGitHubAbstractWebhookProcessor:
    async def test_verify_webhook_signature_no_secret(
        self, gh_processor, mock_ocean_context
    ):
        ocean.integration_config["webhook_secret"] = None
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"x-hub-signature-256": "test-signature"}
        result = await gh_processor._verify_webhook_signature(mock_request)
        assert result is True

    async def test_verify_webhook_signature_no_headers(
        self, gh_processor, mock_ocean_context
    ):
        mock_request = create_gh_mock_request(b"{}", {})
        result = await gh_processor._verify_webhook_signature(mock_request)
        assert result is False

    async def test_verify_webhook_signature_valid(
        self, gh_processor, mock_ocean_context
    ):
        payload = {"test": "data"}
        payload_bytes = json.dumps(payload).encode("utf-8")
        valid_signature = generate_gh_signature(
            ocean.integration_config["webhook_secret"], payload_bytes
        )
        headers = {"x-hub-signature-256": valid_signature}
        mock_request = create_gh_mock_request(payload_bytes, headers)
        result = await gh_processor._verify_webhook_signature(mock_request)
        assert result is True

    async def test_verify_webhook_signature_invalid(
        self, gh_processor, mock_ocean_context
    ):
        payload = {"test": "data"}
        payload_bytes = json.dumps(payload).encode("utf-8")
        invalid_signature = "sha256=invalidsignature"
        headers = {"x-hub-signature-256": invalid_signature}
        mock_request = create_gh_mock_request(payload_bytes, headers)
        result = await gh_processor._verify_webhook_signature(mock_request)
        assert result is False

    async def test_should_process_event_no_request(self, gh_processor):
        event = WebhookEvent(
            trace_id="gh-test-trace",
            headers={"x-hub-signature-256": "process"},
            payload={},
        )
        event._original_request = None
        result = await gh_processor.should_process_event(event)
        assert result is False

    async def test_should_process_event_implementation_returns_false(
        self, gh_processor
    ):
        payload = {"test": "data"}
        payload_bytes = json.dumps(payload).encode("utf-8")
        headers = {"x-hub-signature-256": "do-not-process"}
        mock_request = create_gh_mock_request(payload_bytes, headers)
        event = WebhookEvent(
            trace_id="gh-test-trace",
            headers=headers,
            payload=payload,
        )
        event._original_request = mock_request
        result = await gh_processor.should_process_event(event)
        assert result is False
