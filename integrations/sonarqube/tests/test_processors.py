import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from webhook_processors.analysis_webhook_processor import AnalysisWebhookProcessor
from webhook_processors.issue_webhook_processor import IssueWebhookProcessor
from webhook_processors.project_webhook_processor import ProjectWebhookProcessor
from integration import ObjectKind
from typing import Any, AsyncGenerator, Dict, List


from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortResourceConfig,
    MappingsConfig,
    EntityMapping,
    Selector,
)


# Fixtures
@pytest.fixture
def mock_event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def analysis_processor(mock_event: WebhookEvent) -> AnalysisWebhookProcessor:
    return AnalysisWebhookProcessor(mock_event)


@pytest.fixture
def issue_processor(mock_event: WebhookEvent) -> IssueWebhookProcessor:
    return IssueWebhookProcessor(mock_event)


@pytest.fixture
def project_processor(mock_event: WebhookEvent) -> ProjectWebhookProcessor:
    return ProjectWebhookProcessor(mock_event)


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind="project",
        selector=Selector(query="test"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".name",
                    blueprint='"project"',
                    properties={},
                    relations={},
                )
            )
        ),
    )


@pytest.fixture
def mock_context(monkeypatch: Any) -> MagicMock:
    mock_context = MagicMock()
    monkeypatch.setattr("port_ocean.context.ocean.ocean", mock_context)
    return mock_context


# Analysis Processor Tests
@pytest.mark.asyncio
async def test_analysis_get_matching_kinds(
    analysis_processor: AnalysisWebhookProcessor,
) -> None:
    dummy_event = WebhookEvent(trace_id="dummy", payload={}, headers={})
    assert await analysis_processor.get_matching_kinds(dummy_event) == [
        ObjectKind.ANALYSIS,
        ObjectKind.SASS_ANALYSIS,
        ObjectKind.ONPREM_ANALYSIS,
    ]


@pytest.mark.asyncio
async def test_analysis_handle_event_cloud(
    analysis_processor: AnalysisWebhookProcessor,
    resource_config: ResourceConfig,
    mock_context: MagicMock,
) -> None:
    mock_context.integration_config = {"sonar_is_on_premise": False}

    with patch(
        "webhook_processors.analysis_webhook_processor.init_sonar_client"
    ) as mock_init:
        mock_client = AsyncMock()
        mock_client.get_analysis_for_task.return_value = {"analysis": "data"}
        mock_init.return_value = mock_client

        result = await analysis_processor.handle_event(
            {"project": "test", "taskId": "123"}, resource_config
        )

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == {"analysis": "data"}


@pytest.mark.asyncio
async def test_analysis_handle_event_onprem(
    analysis_processor: AnalysisWebhookProcessor,
    resource_config: ResourceConfig,
    mock_context: MagicMock,
) -> None:
    mock_context.integration_config = {"sonar_is_on_premise": True}

    with patch(
        "webhook_processors.analysis_webhook_processor.init_sonar_client"
    ) as mock_init:
        mock_client = AsyncMock()

        mock_analysis_data = {"pr": "data"}
        mock_client.get_analysis_for_task.return_value = mock_analysis_data

        mock_init.return_value = mock_client

        test_payload = {
            "project": {"key": "test-project-key", "name": "Test Project"},
            "taskId": "analysis123",
            "analysisDate": "2025-01-01",
        }

        result = await analysis_processor.handle_event(test_payload, resource_config)

        mock_client.get_analysis_for_task.assert_awaited_once_with(test_payload)

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == {"pr": "data"}


# Issue Processor Tests
@pytest.mark.asyncio
async def test_issue_get_matching_kinds(
    issue_processor: IssueWebhookProcessor,
) -> None:
    dummy_event = WebhookEvent(trace_id="dummy", payload={}, headers={})
    assert await issue_processor.get_matching_kinds(dummy_event) == [ObjectKind.ISSUES]


@pytest.mark.asyncio
async def test_issue_handle_event(
    issue_processor: IssueWebhookProcessor, resource_config: ResourceConfig
) -> None:
    with patch(
        "webhook_processors.issue_webhook_processor.init_sonar_client"
    ) as mock_init:
        mock_client = AsyncMock()

        mock_component = {"key": "test-project"}
        mock_client.get_single_component.return_value = mock_component

        test_issues = [[{"issue": "1"}, {"issue": "2"}], [{"issue": "3"}]]

        async def mock_issues_generator(
            project: Dict[str, Any]
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            assert project == mock_component
            for batch in test_issues:
                yield batch

        mock_client.get_issues_by_component = mock_issues_generator
        mock_init.return_value = mock_client

        result = await issue_processor.handle_event(
            {"project": "test-project-key"}, resource_config
        )

        mock_client.get_single_component.assert_awaited_once_with("test-project-key")

        expected_issues = []
        async for batch in mock_issues_generator(mock_component):
            expected_issues.extend(batch)

        assert len(result.updated_raw_results) == 3
        assert all(issue in expected_issues for issue in result.updated_raw_results)


# Project Processor Tests
@pytest.mark.asyncio
async def test_project_get_matching_kinds(
    project_processor: ProjectWebhookProcessor,
) -> None:
    dummy_event = WebhookEvent(trace_id="dummy", payload={}, headers={})
    assert await project_processor.get_matching_kinds(dummy_event) == [
        ObjectKind.PROJECTS,
        ObjectKind.PROJECTS_GA,
    ]


@pytest.mark.asyncio
async def test_project_handle_event(
    project_processor: ProjectWebhookProcessor, resource_config: ResourceConfig
) -> None:
    with patch(
        "webhook_processors.project_webhook_processor.init_sonar_client"
    ) as mock_init:
        mock_client = AsyncMock()
        mock_client.get_single_component.return_value = {"key": "test"}
        mock_client.get_single_project.return_value = {"project": "data"}
        mock_init.return_value = mock_client

        result = await project_processor.handle_event(
            {"project": "test"}, resource_config
        )

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == {"project": "data"}
