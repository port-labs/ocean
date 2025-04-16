import base64
from typing import Any, Generator
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
    PortAppConfig,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from azure_devops.webhooks.webhook_processors.pull_request_processor import (
    PullRequestWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.push_processor import PushWebhookProcessor
from azure_devops.webhooks.webhook_processors._base_processor import (
    _AzureDevOpsBaseWebhookProcessor,
)
from azure_devops.misc import GitPortAppConfig
from port_ocean.context.event import _event_context_stack, EventContext


class AzureDevOpsWebhookProcessorImpl(_AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return ["test-kind"]

    async def handle_event(self, event: WebhookEvent) -> None:
        pass

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return True


@pytest.fixture
def event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def base_processor(event: WebhookEvent) -> AzureDevOpsWebhookProcessorImpl:
    return AzureDevOpsWebhookProcessorImpl(event)


@pytest.fixture
def pull_request_processor(
    event: WebhookEvent, monkeypatch: pytest.MonkeyPatch
) -> PullRequestWebhookProcessor:
    mock_client = MagicMock()
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.pull_request_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )
    return PullRequestWebhookProcessor(event)


@pytest.fixture
def push_processor(
    event: WebhookEvent, monkeypatch: pytest.MonkeyPatch
) -> PushWebhookProcessor:
    mock_client = MagicMock()
    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.push_processor.AzureDevopsClient.create_from_ocean_config",
        lambda: mock_client,
    )
    return PushWebhookProcessor(event)


@pytest.fixture
def pull_request_config() -> ResourceConfig:
    return ResourceConfig(
        kind="pull_request",
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".pullRequestId",
                    title=".title",
                    blueprint='"pull_request"',
                    properties={
                        "url": ".url",
                        "status": ".status",
                    },
                    relations={},
                )
            )
        ),
    )


@pytest.fixture
def push_config() -> ResourceConfig:
    return ResourceConfig(
        kind="repository",
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".repository.id",
                    title=".repository.name",
                    blueprint='"repository"',
                    properties={
                        "url": ".repository.url",
                        "defaultBranch": ".repository.defaultBranch",
                    },
                    relations={},
                )
            )
        ),
    )


@pytest.fixture
def mock_context(monkeypatch: Any) -> PortOceanContext:
    mock_context = AsyncMock()
    mock_context.port_app_config = GitPortAppConfig(
        spec_path="port.yml", branch="main", use_default_branch=True
    )
    monkeypatch.setattr(PortOceanContext, "app", mock_context)
    return mock_context


@pytest.fixture
def mock_event_context() -> Generator[None, None, None]:
    mock_port_app_config = PortAppConfig(resources=[])

    mock_context = EventContext(
        event_type="WEBHOOK",
        attributes={
            "azure_devops_client": MagicMock(),
            "port_app_config": mock_port_app_config,
        },
    )

    _event_context_stack.push(mock_context)
    yield
    _event_context_stack.pop()


@pytest.fixture
def mock_ocean(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_ocean_instance = MagicMock()
    mock_ocean_instance.integration_config = {"webhook_secret": "test-secret"}
    monkeypatch.setattr("port_ocean.context.ocean.ocean", mock_ocean_instance)


@pytest.mark.asyncio
async def test_base_authenticate_failure_wrong_secret(
    base_processor: AzureDevOpsWebhookProcessorImpl, mock_ocean: None
):
    encoded = base64.b64encode(b":wrong-secret").decode("utf-8")
    headers = {"authorization": f"Basic {encoded}"}
    assert await base_processor.authenticate({}, headers) is False


@pytest.mark.asyncio
async def test_base_authenticate_failure_wrong_auth_type(
    base_processor: AzureDevOpsWebhookProcessorImpl, mock_ocean: None
):
    headers = {"authorization": "Bearer token"}
    assert await base_processor.authenticate({}, headers) is False


@pytest.mark.asyncio
async def test_base_authenticate_failure_malformed(
    base_processor: AzureDevOpsWebhookProcessorImpl, mock_ocean: None
):
    headers = {"authorization": "Basic malformed_token"}
    assert await base_processor.authenticate({}, headers) is False


@pytest.mark.asyncio
async def test_base_authenticate_failure_no_auth(
    base_processor: AzureDevOpsWebhookProcessorImpl, mock_ocean: None
):
    assert await base_processor.authenticate({}, {}) is True


@pytest.mark.asyncio
async def test_base_validate_payload_success(
    base_processor: AzureDevOpsWebhookProcessorImpl,
):
    valid_payload = {
        "eventType": "user.created",
        "publisherId": "tfs",
        "resource": {"id": "123"},
    }
    assert await base_processor.validate_payload(valid_payload) is True


@pytest.mark.asyncio
async def test_base_validate_payload_failure(
    base_processor: AzureDevOpsWebhookProcessorImpl,
):
    invalid_payloads = [
        {"eventType": "user.created"},
        {"publisherId": "tfs", "resource": {}},
        {"eventType": "user.created", "publisherId": "tfs"},
    ]

    for payload in invalid_payloads:
        assert await base_processor.validate_payload(payload) is False


@pytest.mark.asyncio
async def test_pull_request_should_process_event(
    pull_request_processor: PullRequestWebhookProcessor,
    mock_event_context: None,
):
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": "git.pullrequest.updated",
            "publisherId": "tfs",
            "resource": {"pullRequestId": "123"},
        },
        headers={},
    )
    assert await pull_request_processor.should_process_event(event) is True

    event.payload["eventType"] = "wrong.event"
    assert await pull_request_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_pull_request_get_matching_kinds(
    pull_request_processor: PullRequestWebhookProcessor,
    mock_event_context: None,
):
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert await pull_request_processor.get_matching_kinds(event) == ["pull-request"]


@pytest.mark.asyncio
async def test_pull_request_authenticate(
    pull_request_processor: PullRequestWebhookProcessor,
    mock_ocean: None,
    mock_event_context: None,
):
    headers = {
        "authorization": "Basic " + base64.b64encode(b":wrong-secret").decode("utf-8")
    }
    assert await pull_request_processor.authenticate({}, headers) is False


@pytest.mark.asyncio
async def test_pull_request_validate_payload(
    pull_request_processor: PullRequestWebhookProcessor,
    mock_event_context: None,
):
    valid_payload = {
        "eventType": "git.pullrequest.updated",
        "publisherId": "tfs",
        "resource": {"pullRequestId": "123"},
    }
    assert await pull_request_processor.validate_payload(valid_payload) is True

    invalid_payload = {"missing": "fields"}
    assert await pull_request_processor.validate_payload(invalid_payload) is False


@pytest.mark.asyncio
async def test_push_should_process_event(
    push_processor: PushWebhookProcessor,
    mock_event_context: None,
):
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": "git.push",
            "publisherId": "tfs",
            "resource": {"url": "http://example.com"},
        },
        headers={},
    )
    assert await push_processor.should_process_event(event) is True

    event.payload["eventType"] = "wrong.event"
    assert await push_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_push_get_matching_kinds(
    push_processor: PushWebhookProcessor,
    mock_event_context: None,
):
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    kinds = await push_processor.get_matching_kinds(event)
    assert "repository" in kinds
    assert "file" in kinds


@pytest.mark.asyncio
async def test_push_validate_payload(
    push_processor: PushWebhookProcessor,
    mock_event_context: None,
):
    valid_payload = {
        "eventType": "git.push",
        "publisherId": "tfs",
        "resource": {"url": "http://example.com"},
    }
    assert await push_processor.validate_payload(valid_payload) is True

    invalid_payload = {"missing": "fields"}
    assert await push_processor.validate_payload(invalid_payload) is False
