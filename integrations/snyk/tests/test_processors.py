import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from webhook_processors.project_webhook_processor import ProjectWebhookProcessor
from webhook_processors.issue_webhook_processor import IssueWebhookProcessor
from webhook_processors.target_webhook_processor import TargetWebhookProcessor
from typing import Any

from snyk.overrides import ProjectSelector


@pytest.fixture
def event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def projectWebhookProcessor(event: WebhookEvent) -> ProjectWebhookProcessor:
    return ProjectWebhookProcessor(event)


@pytest.fixture
def issueWebhookProcessor(event: WebhookEvent) -> IssueWebhookProcessor:
    return IssueWebhookProcessor(event)


@pytest.fixture
def targetWebhookProcessor(event: WebhookEvent) -> TargetWebhookProcessor:
    return TargetWebhookProcessor(event)


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind="project",
        selector=ProjectSelector(attachIssuesToProject=True, query=""),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".name",
                    blueprint='"service"',
                    properties={
                        "url": ".links.html",
                        "origin": ".origin",
                    },
                    relations={},
                )
            )
        ),
    )


@pytest.fixture
def mock_context(monkeypatch: Any) -> PortOceanContext:
    mock_context = AsyncMock()
    monkeypatch.setattr(PortOceanContext, "app", mock_context)
    return mock_context


@pytest.mark.asyncio
async def test_shouldProcessEvent_project(
    projectWebhookProcessor: ProjectWebhookProcessor,
    mock_context: PortOceanContext,
) -> None:
    with patch("webhook_processors.snyk_base_webhook_processor.hmac") as mock_hmac:
        mock_hmac_obj = mock_hmac.new.return_value
        mock_hmac_obj.hexdigest.return_value = "1234567890"

        mock_request = AsyncMock()
        mock_request.body.return_value = b'{"event":"project.created"}'

        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={
                "event": "project.created",
            },
            headers={"x-hub-signature": "sha256=1234567890"},
        )
        event._original_request = mock_request

        assert await projectWebhookProcessor.should_process_event(event) is True

        mock_hmac_obj.hexdigest.return_value = "1"
        assert await projectWebhookProcessor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_shouldProcessEvent_target(
    targetWebhookProcessor: TargetWebhookProcessor,
    mock_context: PortOceanContext,
) -> None:
    with patch("webhook_processors.snyk_base_webhook_processor.hmac") as mock_hmac:
        mock_hmac_obj = mock_hmac.new.return_value
        mock_hmac_obj.hexdigest.return_value = "1234567890"

        mock_request = AsyncMock()
        mock_request.body.return_value = b'{"event":"project.created"}'

        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={
                "event": "project.created",
            },
            headers={"x-hub-signature": "sha256=1234567890"},
        )
        event._original_request = mock_request
        assert await targetWebhookProcessor.should_process_event(event) is True

        mock_hmac_obj.hexdigest.return_value = "1"
        assert await targetWebhookProcessor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_shouldProcessEvent_issue(
    issueWebhookProcessor: IssueWebhookProcessor,
    mock_context: PortOceanContext,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert await issueWebhookProcessor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_getMatchingKinds_projectReturned(
    projectWebhookProcessor: ProjectWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert await projectWebhookProcessor.get_matching_kinds(event) == ["project"]


@pytest.mark.asyncio
async def test_getMatchingKinds_issueReturned(
    issueWebhookProcessor: IssueWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert await issueWebhookProcessor.get_matching_kinds(event) == ["issue"]


@pytest.mark.asyncio
async def test_getMatchingKinds_targetReturned(
    targetWebhookProcessor: TargetWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert await targetWebhookProcessor.get_matching_kinds(event) == ["target"]


@pytest.mark.asyncio
async def test_authenticate_project(
    projectWebhookProcessor: ProjectWebhookProcessor,
) -> None:
    result = await projectWebhookProcessor.authenticate({}, {})
    assert result is True


@pytest.mark.asyncio
async def test_authenticate_issue(
    issueWebhookProcessor: IssueWebhookProcessor,
) -> None:
    result = await issueWebhookProcessor.authenticate({}, {})
    assert result is True


@pytest.mark.asyncio
async def test_authenticate_target(
    targetWebhookProcessor: TargetWebhookProcessor,
) -> None:
    result = await targetWebhookProcessor.authenticate({}, {})
    assert result is True


@pytest.mark.asyncio
async def test_validatePayload_project(
    projectWebhookProcessor: ProjectWebhookProcessor,
) -> None:
    result = await projectWebhookProcessor.validate_payload({"project": {}})
    assert result is True

    result = await projectWebhookProcessor.validate_payload({})
    assert result is False


@pytest.mark.asyncio
async def test_validatePayload_issue(
    issueWebhookProcessor: IssueWebhookProcessor,
) -> None:
    result = await issueWebhookProcessor.validate_payload({"project": {}})
    assert result is True

    result = await issueWebhookProcessor.validate_payload({})
    assert result is False


@pytest.mark.asyncio
async def test_validatePayload_target(
    targetWebhookProcessor: TargetWebhookProcessor,
) -> None:
    result = await targetWebhookProcessor.validate_payload({"project": {}})
    assert result is True

    result = await targetWebhookProcessor.validate_payload({})
    assert result is False


@pytest.mark.asyncio
async def test_handleEvent_projectUpdated_projectReturnedFromClient_updatedRawResultsReturnedCorrectly(
    projectWebhookProcessor: ProjectWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    payload: dict[str, Any] = {
        "event": "project.updated",
        "project": {"id": "test-project-id"},
        "org": {"id": "test-org-id"},
    }
    mock_project: dict[str, Any] = {
        "id": "test-project-id",
        "name": "Test Project",
        "origin": "github",
    }

    with patch(
        "webhook_processors.project_webhook_processor.init_client"
    ) as mock_create_client:
        mock_client = AsyncMock()

        async def mock_get_project(*args: Any, **kwargs: Any) -> dict[str, Any]:
            assert args[0] == "test-org-id"
            assert args[1] == "test-project-id"
            return mock_project

        mock_client.get_single_project = mock_get_project
        mock_create_client.return_value = mock_client

        result = await projectWebhookProcessor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == mock_project


@pytest.mark.asyncio
async def test_handleEvent_projectUpdated_targetReturnedFromClient_updatedRawResultsReturnedCorrectly(
    targetWebhookProcessor: TargetWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    payload: dict[str, Any] = {
        "event": "project.updated",
        "project": {"id": "test-project-id"},
        "org": {"id": "test-org-id"},
    }
    mock_target: dict[str, Any] = {
        "id": "test-target-id",
        "name": "Test Target",
        "url": "https://example.com",
    }

    with patch(
        "webhook_processors.target_webhook_processor.init_client"
    ) as mock_create_client:
        mock_client = AsyncMock()

        async def mock_get_target(*args: Any, **kwargs: Any) -> dict[str, Any]:
            assert args[0] == "test-org-id"
            assert args[1] == "test-project-id"
            return mock_target

        mock_client.get_single_target_by_project_id = mock_get_target
        mock_create_client.return_value = mock_client

        result = await targetWebhookProcessor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == mock_target


@pytest.mark.asyncio
async def test_handleEvent_projectUpdated_issuesReturnedFromClient_updatedRawResultsReturnedCorrectly(
    issueWebhookProcessor: IssueWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    payload: dict[str, Any] = {
        "event": "project.updated",
        "project": {"id": "test-project-id"},
        "org": {"id": "test-org-id"},
    }
    mock_issues: list[dict[str, Any]] = [
        {
            "id": "test-issue-id",
            "title": "Test Issue",
            "severity": "high",
        }
    ]

    with patch(
        "webhook_processors.issue_webhook_processor.init_client"
    ) as mock_create_client:
        mock_client = AsyncMock()

        async def mock_get_issues(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
            assert args[0] == "test-org-id"
            assert args[1] == "test-project-id"
            return mock_issues

        mock_client.get_issues = mock_get_issues
        mock_create_client.return_value = mock_client

        result = await issueWebhookProcessor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == mock_issues[0]
