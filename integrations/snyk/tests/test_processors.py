# here we will test the webhook processors

import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from integrations.snyk.webhook_processors.project_webhook_processor import ProjectWebhookProcessor  # type: ignore
from integrations.snyk.webhook_processors.issue_webhook_processor import IssueWebhookProcessor  # type: ignore
from integrations.snyk.webhook_processors.target_webhook_processor import TargetWebhookProcessor  # type: ignore
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


def test_shouldProcessEvent_project(
    projectWebhookProcessor: ProjectWebhookProcessor,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "event": "project.created",
        },
        headers={},
    )
    assert projectWebhookProcessor.should_process_event(event) is True

    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "event": "project.updated",
        },
        headers={},
    )
    assert projectWebhookProcessor.should_process_event(event) is True

    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "event": "org.created",
        },
        headers={},
    )
    assert projectWebhookProcessor.should_process_event(event) is False


def test_getMatchingKinds_project(
    projectWebhookProcessor: ProjectWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert projectWebhookProcessor.get_matching_kinds(event) == ["project"]


@pytest.mark.asyncio
async def test_authenticate_project(
    projectWebhookProcessor: ProjectWebhookProcessor,
) -> None:
    result = await projectWebhookProcessor.authenticate({}, {})
    assert result is True


@pytest.mark.asyncio
async def test_validatePayload_project(
    projectWebhookProcessor: ProjectWebhookProcessor,
) -> None:
    result = await projectWebhookProcessor.validate_payload({})
    assert result is True


@pytest.mark.asyncio
async def test_handleEvent_projectUpdated_projectReturnedFromClient_updatedRawResultsReturnedCorrectly(
    projectWebhookProcessor: ProjectWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    payload: dict[str, Any] = {
        "event": "project.updated",
        "project": {"id": "test-project-id"},
    }
    mock_project: dict[str, Any] = {
        "id": "test-project-id",
        "name": "Test Project",
        "origin": "github",
    }

    with patch(
        "webhook_processors.project_webhook_processor.create_snyk_client"
    ) as mock_create_client:
        mock_client = AsyncMock()

        async def mock_get_project(*args: Any, **kwargs: Any) -> dict[str, Any]:
            assert args[0] == "test-project-id"
            return mock_project

        mock_client.get_project = mock_get_project
        mock_create_client.return_value = mock_client

        result = await projectWebhookProcessor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == mock_project


@pytest.mark.asyncio
async def test_handleEvent_projectDeleted_deletedRawResultsReturnedCorrectly(
    projectWebhookProcessor: ProjectWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    payload = {"event": "project.deleted", "project": {"id": "test-project-id"}}

    with patch(
        "webhook_processors.project_webhook_processor.create_snyk_client"
    ) as mock_create_client:
        mock_client = AsyncMock()
        mock_create_client.return_value = mock_client

        result = await projectWebhookProcessor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0] == payload["project"]


def test_shouldProcessEvent_issue(
    issueWebhookProcessor: IssueWebhookProcessor,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "event": "org.created",
        },
        headers={},
    )
    assert issueWebhookProcessor.should_process_event(event) is True

    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "event": "org.updated",
        },
        headers={},
    )
    assert issueWebhookProcessor.should_process_event(event) is True

    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "event": "project.created",
        },
        headers={},
    )
    assert issueWebhookProcessor.should_process_event(event) is False


def test_shouldProcessEvent_target(
    targetWebhookProcessor: TargetWebhookProcessor,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "event": "vulnerability.disclosed",
        },
        headers={},
    )
    assert targetWebhookProcessor.should_process_event(event) is True

    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "event": "vulnerability.updated",
        },
        headers={},
    )
    assert targetWebhookProcessor.should_process_event(event) is True

    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "event": "project.created",
        },
        headers={},
    )
    assert targetWebhookProcessor.should_process_event(event) is False
