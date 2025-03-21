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
from webhook_processors.analysis_webhook_processor import AnalysisWebhookProcessor
from typing import Any
from integration import ObjectKind


@pytest.fixture
def event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def project_webhook_processor(event: WebhookEvent) -> ProjectWebhookProcessor:
    return ProjectWebhookProcessor(event)


@pytest.fixture
def issue_webhook_processor(event: WebhookEvent) -> IssueWebhookProcessor:
    return IssueWebhookProcessor(event)


@pytest.fixture
def analysis_webhook_processor(event: WebhookEvent) -> AnalysisWebhookProcessor:
    return AnalysisWebhookProcessor(event)


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind="project",
        selector={"query": {}},
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".key",
                    title=".name",
                    blueprint='"project"',
                    properties={
                        "url": ".__link",
                        "organization": ".organization",
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
async def test_should_process_event_project(
    project_webhook_processor: ProjectWebhookProcessor,
    mock_context: PortOceanContext,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={"project": {"key": "test-project-key"}},
        headers={},
    )
    assert await project_webhook_processor.should_process_event(event) is True

    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert await project_webhook_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_should_process_event_issue(
    issue_webhook_processor: IssueWebhookProcessor,
    mock_context: PortOceanContext,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={"eventType": "issues"},
        headers={},
    )
    assert await issue_webhook_processor.should_process_event(event) is True

    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert await issue_webhook_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_should_process_event_analysis(
    analysis_webhook_processor: AnalysisWebhookProcessor,
    mock_context: PortOceanContext,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={"eventType": "analysis"},
        headers={},
    )
    assert await analysis_webhook_processor.should_process_event(event) is True

    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert await analysis_webhook_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_get_matching_kinds_project(
    project_webhook_processor: ProjectWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert await project_webhook_processor.get_matching_kinds(event) == [
        ObjectKind.PROJECTS,
        ObjectKind.PROJECTS_GA,
    ]


@pytest.mark.asyncio
async def test_get_matching_kinds_issue(
    issue_webhook_processor: IssueWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert await issue_webhook_processor.get_matching_kinds(event) == [
        ObjectKind.ISSUES
    ]


@pytest.mark.asyncio
async def test_get_matching_kinds_analysis(
    analysis_webhook_processor: AnalysisWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert await analysis_webhook_processor.get_matching_kinds(event) == [
        ObjectKind.ANALYSIS,
        ObjectKind.SASS_ANALYSIS,
        ObjectKind.ONPREM_ANALYSIS,
    ]


@pytest.mark.asyncio
async def test_authenticate_project(
    project_webhook_processor: ProjectWebhookProcessor,
) -> None:
    result = await project_webhook_processor.authenticate({}, {})
    assert result is True


@pytest.mark.asyncio
async def test_authenticate_issue(
    issue_webhook_processor: IssueWebhookProcessor,
) -> None:
    result = await issue_webhook_processor.authenticate({}, {})
    assert result is True


@pytest.mark.asyncio
async def test_authenticate_analysis(
    analysis_webhook_processor: AnalysisWebhookProcessor,
) -> None:
    result = await analysis_webhook_processor.authenticate({}, {})
    assert result is True


@pytest.mark.asyncio
async def test_validate_payload_project(
    project_webhook_processor: ProjectWebhookProcessor,
) -> None:
    result = await project_webhook_processor.validate_payload({"project": {}})
    assert result is True

    result = await project_webhook_processor.validate_payload({})
    assert result is False


@pytest.mark.asyncio
async def test_validate_payload_issue(
    issue_webhook_processor: IssueWebhookProcessor,
) -> None:
    result = await issue_webhook_processor.validate_payload({"eventType": "issues"})
    assert result is True

    result = await issue_webhook_processor.validate_payload({})
    assert result is False


@pytest.mark.asyncio
async def test_validate_payload_analysis(
    analysis_webhook_processor: AnalysisWebhookProcessor,
) -> None:
    result = await analysis_webhook_processor.validate_payload(
        {"eventType": "analysis"}
    )
    assert result is True

    result = await analysis_webhook_processor.validate_payload({})
    assert result is False


@pytest.mark.asyncio
async def test_handle_event_project_updated(
    project_webhook_processor: ProjectWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    payload: dict[str, Any] = {
        "project": {"key": "test-project-key"},
    }
    mock_project: dict[str, Any] = {
        "key": "test-project-key",
        "name": "Test Project",
        "__link": "https://sonarqube.example.com",
    }

    with patch(
        "webhook_processors.project_webhook_processor.SonarQubeClient"
    ) as mock_client:
        mock_client_instance = AsyncMock()
        mock_client_instance.get_single_component.return_value = {
            "key": "test-project-key"
        }
        mock_client_instance.get_single_project.return_value = mock_project
        mock_client.return_value = mock_client_instance

        result = await project_webhook_processor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == mock_project


@pytest.mark.asyncio
async def test_handle_event_issue_updated(
    issue_webhook_processor: IssueWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    payload: dict[str, Any] = {
        "project": {"key": "test-project-key"},
    }
    mock_issues: list[dict[str, Any]] = [
        {
            "key": "test-issue-key",
            "message": "Test Issue",
            "__link": "https://sonarqube.example.com",
        }
    ]

    with patch(
        "webhook_processors.issue_webhook_processor.SonarQubeClient"
    ) as mock_client:
        mock_client_instance = AsyncMock()
        mock_client_instance.get_single_component.return_value = {
            "key": "test-project-key"
        }
        mock_client_instance.get_issues_by_component.return_value = mock_issues
        mock_client.return_value = mock_client_instance

        result = await issue_webhook_processor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == mock_issues[0]


@pytest.mark.asyncio
async def test_handle_event_analysis_updated(
    analysis_webhook_processor: AnalysisWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    payload: dict[str, Any] = {
        "serverUrl": "http://localhost:9000",
        "taskId": "AVh21JS2JepAEhwQ-b3u",
        "status": "SUCCESS",
        "analysedAt": "2016-11-18T10:46:28+0100",
        "revision": "c739069ec7105e01303e8b3065a81141aad9f129",
        "project": {
            "key": "myproject",
            "name": "My Project",
            "url": "https://mycompany.com/sonarqube/dashboard?id=myproject",
        },
        "properties": {},
        "qualityGate": {
            "conditions": [
                {
                    "errorThreshold": "1",
                    "metric": "new_security_rating",
                    "onLeakPeriod": True,
                    "operator": "GREATER_THAN",
                    "status": "OK",
                    "value": "1",
                },
                {
                    "errorThreshold": "1",
                    "metric": "new_reliability_rating",
                    "onLeakPeriod": True,
                    "operator": "GREATER_THAN",
                    "status": "OK",
                    "value": "1",
                },
                {
                    "errorThreshold": "1",
                    "metric": "new_maintainability_rating",
                    "onLeakPeriod": True,
                    "operator": "GREATER_THAN",
                    "status": "OK",
                    "value": "1",
                },
                {
                    "errorThreshold": "80",
                    "metric": "new_coverage",
                    "onLeakPeriod": True,
                    "operator": "LESS_THAN",
                    "status": "NO_VALUE",
                },
            ],
            "name": "SonarQube way",
            "status": "OK",
        },
    }

    mock_analysis: dict[str, Any] = {
        "analysisId": "test-analysis-id",
        "date": "2023-10-01T12:34:56Z",
    }

    # Mock the external SonarQubeClient
    with patch(
        "webhook_processors.analysis_webhook_processor.SonarQubeClient"
    ) as mock_client:
        mock_client_instance = AsyncMock()
        mock_client_instance.get_single_component.return_value = {
            "key": "test-project-key"
        }
        mock_client_instance.get_analysis_for_task.return_value = mock_analysis
        mock_client.return_value = mock_client_instance

        result = await analysis_webhook_processor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == mock_analysis
